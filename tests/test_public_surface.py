"""
The public import surface, and every module importable on its own.

Two detectors for the decomposition of chnbase.py and chnutils.py
(Phase 5), written before anything moved.

1. `pymoso.chnbase` and `pymoso.chnutils` are the documented import
   paths, and stay so: the README names them, user problem files
   travel to workers as source text that imports from them, and the
   example files are byte-compared against the README. SURFACE lists
   every name each of them promises and the module that defines it.
   A move edits the home; a name that stops being importable from its
   facade, or becomes a copy rather than the same object, fails here.

   INCIDENTAL lists every other public-looking name the two modules
   happen to bind -- imports they need, promised to nobody. The two
   lists together must account for the module exactly, so a name
   cannot appear on, or disappear from, either facade without a line
   of this file changing. That is what makes a removal deliberate.

2. Every module imports in a fresh interpreter in which it is the
   first pymoso module asked for. A worker under forkserver or spawn,
   and a Spark executor, import the module a task function lives in
   and nothing before it, so an import cycle that is harmless when
   the package is entered through `pymoso.chnutils` can fail there
   and nowhere else. The suite's other fresh-interpreter test
   (test_dependency_boundary.py) imports the modules one after
   another in one interpreter, which only tries one order.
"""
import importlib
import pathlib
import subprocess
import sys
import textwrap
import types

import pytest

PACKAGE = pathlib.Path(__file__).resolve().parent.parent / "pymoso"
SUBPROCESS_TIMEOUT = 120

# facade -> {name: the module that defines it}
SURFACE = {
    "pymoso.chnbase": {
        "Oracle": "pymoso.oracle",
        "MOSOSolver": "pymoso.chnbase",
        "RASolver": "pymoso.chnbase",
        "RLESolver": "pymoso.chnbase",
        "accepted_params": "pymoso.chnbase",
        "reject_unknown_params": "pymoso.chnbase",
        # The helpers the solver bases use. `chnbase.get_nbors` is the
        # binding RASolver reads, and test_get_nbors_equivalence.py
        # patches it by this name.
        "argsort": "pymoso.moso",
        "does_dominate": "pymoso.moso",
        "does_strict_dominate": "pymoso.moso",
        "does_weak_dominate": "pymoso.moso",
        "enorm": "pymoso.moso",
        "get_nbors": "pymoso.moso",
        "get_nondom": "pymoso.moso",
        "get_setnbors": "pymoso.moso",
        "is_lwep": "pymoso.moso",
        "perturb": "pymoso.moso",
    },
    "pymoso.chnutils": {
        "solve": "pymoso.chnutils",
        "testsolve": "pymoso.chnutils",
        "starting_point": "pymoso.chnutils",
        "solver_params": "pymoso.chnutils",
        "DEFAULT_BUDGET": "pymoso.chnutils",
        "DEFAULT_CRN": "pymoso.chnutils",
        "DEFAULT_GENERATOR": "pymoso.chnutils",
        "DEFAULT_ISP": "pymoso.chnutils",
        "DEFAULT_PROC": "pymoso.chnutils",
        "DEFAULT_RANX0": "pymoso.chnutils",
        "DEFAULT_SEED": "pymoso.chnutils",
        "DEFAULT_SIMPAR": "pymoso.chnutils",
        # stream layout
        "get_testsolve_prnstreams": "pymoso.layout",
        "get_path_prnstreams": "pymoso.layout",
        "get_solv_prnstreams": "pymoso.layout",
        "check_role_draws": "pymoso.layout",
        # sample paths and metrics
        "PathJob": "pymoso.paths",
        "run_path": "pymoso.paths",
        "run_paths": "pymoso.paths",
        "isp_run": "pymoso.paths",
        "combine_runs": "pymoso.paths",
        "gen_metric": "pymoso.paths",
        "par_diff": "pymoso.paths",
        # dominance, neighbourhoods, distances
        "does_weak_dominate": "pymoso.moso",
        "does_dominate": "pymoso.moso",
        "does_strict_dominate": "pymoso.moso",
        "is_lep": "pymoso.moso",
        "is_lwep": "pymoso.moso",
        "get_biparetos": "pymoso.moso",
        "front": "pymoso.moso",
        "get_nondom": "pymoso.moso",
        "get_nbors": "pymoso.moso",
        "argsort": "pymoso.moso",
        "get_setnbors": "pymoso.moso",
        "enorm": "pymoso.moso",
        "perturb": "pymoso.moso",
        "edist": "pymoso.moso",
        "dxB": "pymoso.moso",
        "dAB": "pymoso.moso",
        "dh": "pymoso.moso",
    },
}

# Bound by the module, promised to nobody.
INCIDENTAL = {
    "pymoso.chnbase": {
        # To be removed deliberately (Phase 5, step 6): two transport
        # functions that belong to pymoso.executor and were never
        # documented here, and an import nothing in the module uses.
        "build_transport_descriptor", "reconstruct_transport_descriptor", "get_biparetos",
        # What the solver bases need.
        "ceil", "floor",
    },
    "pymoso.chnutils": {
        "registry", "numbers", "random",
    },
}


def _public(module):
    return {name for name in vars(module) if not name.startswith("_")}


@pytest.mark.parametrize("facade", sorted(SURFACE))
def test_every_promised_name_is_the_object_its_home_defines(facade):
    module = importlib.import_module(facade)
    for name, home in SURFACE[facade].items():
        assert hasattr(module, name), "{0}.{1} is gone".format(facade, name)
        obj = getattr(module, name)
        assert obj is getattr(importlib.import_module(home), name), (facade, name)
        if isinstance(obj, (type, types.FunctionType)):
            assert obj.__module__ == home, (facade, name, obj.__module__)


@pytest.mark.parametrize("facade", sorted(SURFACE))
def test_no_name_comes_or_goes_unrecorded(facade):
    promised, incidental = set(SURFACE[facade]), INCIDENTAL[facade]
    assert not promised & incidental
    found = _public(importlib.import_module(facade))
    assert found - promised - incidental == set(), "bound and not listed"
    assert (promised | incidental) - found == set(), "listed and not bound"


def _modules():
    """Every module of the package but `__main__` (importing it runs
    the CLI). pymoso/examples/ is not part of the package."""
    names = []
    for path in sorted(PACKAGE.rglob("*.py")):
        parts = ("pymoso",) + path.relative_to(PACKAGE).with_suffix("").parts
        if parts[1] == "examples" or parts[-1] == "__main__":
            continue
        names.append(".".join(parts[:-1] if parts[-1] == "__init__" else parts))
    return names


def _import_each_alone(names, path=None):
    """Import each of `names` in an interpreter of its own, all at
    once. Returns {name: stderr} for those that failed."""
    prefix = "import sys; sys.path.insert(0, {0!r}); ".format(str(path)) if path else ""
    running = {
        name: subprocess.Popen(
            [sys.executable, "-I", "-c", prefix + "import " + name],
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
        )
        for name in names
    }
    failed = {}
    for name, process in running.items():
        try:
            _, stderr = process.communicate(timeout=SUBPROCESS_TIMEOUT)
        except subprocess.TimeoutExpired:
            process.kill()
            _, stderr = process.communicate()
            stderr = "timed out\n" + stderr
        if process.returncode != 0:
            failed[name] = stderr
    return failed


def test_every_module_imports_first():
    names = _modules()
    assert "pymoso.chnutils" in names and "pymoso.prng.base" in names and "pymoso.backends.spark" in names
    failed = _import_each_alone(names)
    assert not failed, "\n".join("{0}:\n{1}".format(*item) for item in failed.items())


def test_a_cycle_that_bites_in_one_order_only_is_caught(tmp_path):
    """The detector, shown detecting. `facade` binds a name and then
    imports `moved`, which imports that name back: entering through
    `facade` works, and a process that imports `moved` first -- as a
    worker handed a task defined there does -- fails."""
    package = tmp_path / "cyclic"
    package.mkdir()
    (package / "__init__.py").write_text("")
    (package / "facade.py").write_text(textwrap.dedent("""
        DEFAULT = 1
        from .moved import task
    """))
    (package / "moved.py").write_text(textwrap.dedent("""
        from .facade import DEFAULT
        def task():
            return DEFAULT
    """))
    failed = _import_each_alone(["cyclic", "cyclic.facade", "cyclic.moved"], path=tmp_path)
    assert set(failed) == {"cyclic.moved"}
    assert "ImportError" in failed["cyclic.moved"]
