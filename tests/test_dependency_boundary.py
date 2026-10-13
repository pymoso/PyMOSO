"""
The dependency boundary: the core package needs nothing but the
standard library, and the optional dependencies stay optional.

pyproject.toml declares `dependencies = []`. Three things keep that
true rather than merely intended:

1. A static check (this module): no file under `pymoso/` outside
   `pymoso/backends/` imports anything at module scope except the
   standard library and pymoso itself, and none of them imports a
   backend module at module scope either -- so importing the core can
   never pull an optional dependency in, directly or through a backend.
   It is written against "not the standard library", not against a list
   of three names, so a fourth optional dependency is caught too.
2. A runtime check (this module): a solve() and a testsolve() run in a
   fresh interpreter in which numpy, cloudpickle and pyspark cannot be
   imported at all. It holds in a development environment that has the
   extras installed, which is where the static check's blind spot (an
   import inside a function on the default path) would otherwise hide.
3. CI: the `test` matrix and the `clean-clone` job install `.[test]`
   and nothing else, so the whole suite runs there with the extras
   really absent; the `spark` job installs them and refuses to let its
   tests skip (.github/workflows/ci.yml).

An import of an optional dependency *inside a function* is allowed in
the core -- that is how an optional feature is reached -- but each one
is listed in LAZY_OPTIONAL_IMPORTS below, so adding one is a decision
and not an accident.
"""
import ast
import pathlib
import subprocess
import sys
import textwrap

import pytest

PACKAGE = pathlib.Path(__file__).resolve().parent.parent / "pymoso"
BACKENDS = "pymoso.backends"
OPTIONAL = ("numpy", "cloudpickle", "pyspark")

# (file relative to pymoso/, top-level module) for every import of
# something outside the standard library and pymoso that sits inside a
# function in the core. Empty means the core has none.
LAZY_OPTIONAL_IMPORTS = set()

SUBPROCESS_TIMEOUT = 120


def _core_files():
    """Every module of the installed package except the backends.
    pymoso/examples/ holds user-facing example files, which are not
    part of the package (pyproject.toml's `packages`)."""
    for path in sorted(PACKAGE.rglob("*.py")):
        relative = path.relative_to(PACKAGE)
        if relative.parts[0] in ("examples", "backends"):
            continue
        yield path, relative


def _module_name(relative):
    parts = ("pymoso",) + relative.with_suffix("").parts
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts), relative.name == "__init__.py"


def _imports(tree, module, is_package):
    """Yield (absolute module name, at module scope?) for every import
    in `tree`. A `from a import b` yields both `a` and `a.b`: `b` may
    be a submodule."""
    package = module if is_package else module.rpartition(".")[0]

    def visit(node, in_function):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.Import):
                for alias in child.names:
                    yield alias.name, not in_function
            elif isinstance(child, ast.ImportFrom):
                if child.level:
                    base = package.split(".")
                    base = base[:len(base) - (child.level - 1)]
                    base = ".".join(base + ([child.module] if child.module else []))
                else:
                    base = child.module
                yield base, not in_function
                for alias in child.names:
                    yield base + "." + alias.name, not in_function
            nested = in_function or isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda))
            yield from visit(child, nested)

    yield from visit(tree, False)


def _scan(files):
    """(module-scope violations, lazy third-party imports) for `files`,
    an iterable of (path, path relative to pymoso/)."""
    violations, lazy = [], set()
    for path, relative in files:
        module, is_package = _module_name(relative)
        tree = ast.parse(path.read_text(), filename=str(path))
        for name, at_module_scope in _imports(tree, module, is_package):
            top = name.split(".")[0]
            in_backends = name == BACKENDS or name.startswith(BACKENDS + ".")
            third_party = top != "pymoso" and top not in sys.stdlib_module_names
            if at_module_scope and (third_party or in_backends):
                violations.append("{0}: imports {1} at module scope".format(relative, name))
            elif third_party:
                lazy.add((str(relative.as_posix()), top))
    return violations, lazy


def test_the_core_imports_only_the_standard_library_and_itself_at_module_scope():
    violations, _ = _scan(_core_files())
    assert not violations, "\n".join(violations)


def test_every_lazy_import_of_an_optional_dependency_in_the_core_is_a_listed_one():
    _, lazy = _scan(_core_files())
    assert lazy == LAZY_OPTIONAL_IMPORTS


def test_the_static_check_sees_what_it_is_for(tmp_path):
    """The detector, shown detecting: each kind of import it must
    refuse, and each kind it must let through."""
    def scan(source, name="chnbase.py"):
        path = tmp_path / name
        path.parent.mkdir(exist_ok=True)
        path.write_text(textwrap.dedent(source))
        return _scan([(path, pathlib.PurePosixPath(name))])

    assert scan("import numpy\n")[0]
    assert scan("from numpy import array\n")[0]
    assert scan("try:\n    import cloudpickle\nexcept ImportError:\n    cloudpickle = None\n")[0]
    assert scan("class A:\n    import pyspark\n")[0]
    assert scan("from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    import numpy\n")[0]
    assert scan("from .backends import spark\n")[0]
    assert scan("from . import backends\n")[0]
    assert scan("from .backends.spark import SparkBackend\n")[0]
    assert scan("import pymoso.backends.spark\n")[0]
    assert scan("from ..backends import spark\n", name="commands/solve.py")[0]

    assert scan("import os\nfrom math import sqrt\nfrom .pool import WorkerPool\nfrom . import prng\n") == ([], set())
    assert scan("from ..chnutils import solve\n", name="commands/solve.py") == ([], set())
    violations, lazy = scan("def f():\n    import cloudpickle\n    from .backends import spark\n")
    assert violations == [] and lazy == {("chnbase.py", "cloudpickle")}


BLOCKED_RUN = """
import importlib.abc, pkgutil, sys

OPTIONAL = {optional!r}


class Blocker(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        if name.split('.')[0] in OPTIONAL:
            raise ImportError('blocked by the dependency-boundary test: ' + name)
        return None


for name in list(sys.modules):
    assert name.split('.')[0] not in OPTIONAL, name
sys.meta_path.insert(0, Blocker())

import pymoso
for info in pkgutil.walk_packages(pymoso.__path__, 'pymoso.'):
    if info.name == {backends!r} or info.name.startswith({backends!r} + '.'):
        continue
    if info.name.endswith('.__main__'):
        continue                    # importing it runs the CLI
    __import__(info.name)

from pymoso.chnutils import solve, testsolve
from pymoso.problems.probtpa import ProbTPA
from pymoso.solvers.rperle import RPERLE
from pymoso.testers.tpatester import TPATester


def main():
    for simpar in (1, 2):
        solve(ProbTPA, RPERLE, (40, 40), budget=200, simpar=simpar)
    for proc in (1, 2):
        testsolve(TPATester, RPERLE, (40, 40), budget=100, isp=2, proc=proc)
    loaded = sorted(name for name in sys.modules if name.split('.')[0] in OPTIONAL)
    assert not loaded, loaded
    print('ran without optional dependencies')


if __name__ == '__main__':
    main()
"""


def test_the_core_runs_where_the_optional_dependencies_cannot_be_imported(tmp_path):
    """Every core module imports, and solve()/testsolve() run serially
    and on worker processes, in an interpreter that refuses to import
    numpy, cloudpickle or pyspark -- whether or not this environment
    has them installed."""
    script = tmp_path / "blocked_run.py"
    script.write_text(BLOCKED_RUN.format(optional=set(OPTIONAL), backends=BACKENDS))
    result = subprocess.run(
        [sys.executable, "-I", str(script)], capture_output=True, text=True, timeout=SUBPROCESS_TIMEOUT,
    )
    assert result.returncode == 0, result.stderr
    assert "ran without optional dependencies" in result.stdout


@pytest.mark.parametrize("name", OPTIONAL)
def test_the_blocker_blocks(tmp_path, name):
    """The runtime check's own detector, shown detecting: the same
    script with one import of an optional dependency added fails."""
    script = tmp_path / "blocked_run.py"
    source = BLOCKED_RUN.format(optional=set(OPTIONAL), backends=BACKENDS)
    script.write_text(source.replace("def main():", "def main():\n    import {0}".format(name), 1))
    result = subprocess.run(
        [sys.executable, "-I", str(script)], capture_output=True, text=True, timeout=SUBPROCESS_TIMEOUT,
    )
    assert result.returncode != 0
    assert "blocked by the dependency-boundary test: " + name in result.stderr
