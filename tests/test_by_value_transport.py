"""
Sending a class that has no source file to a worker, by value.

A class defined in a notebook cell or a REPL has nothing a worker can
import and no file to bundle. With cloudpickle installed (the
`notebook` extra) `executor.ClassRef` carries it by value: the class's
own code travels in the payload. Without cloudpickle such a class is
refused, as before, with an error that now names the extra.

For a *remote* backend the same mechanism covers a second case, the
one that actually bites on a cluster: a class in a module this process
can import and the worker's machine cannot.

The no-cloudpickle half of this is tested where the suite has always
tested it (test_executor.py, test_multifile_transport.py,
test_path_jobs.py), with cloudpickle blocked so that it holds in an
environment that has it.
"""
import multiprocessing
import os
import pickle
import subprocess
import sys
import textwrap

import pytest

import _by_value_classes
from _extras import need
from pymoso.chnutils import solve, testsolve
from pymoso.commands.basecomm import load_user_module
from pymoso.executor import ClassHandle, ClassRef, build_transport_descriptor, reconstruct_transport_descriptor
from pymoso.prng import mrg32k3a
from pymoso.problems.probtpa import ProbTPA
from pymoso.solvers.rperle import RPERLE
from pymoso.testers.tpatester import TPATester

cloudpickle = need("cloudpickle")

pytestmark = pytest.mark.timeout(120)

SUBPROCESS_TIMEOUT = 90
SEED = (12345,) * 6
START_METHODS = multiprocessing.get_all_start_methods()

CELL = """
from pymoso.chnbase import Oracle
SCALE = 3
def helper(x):
    return SCALE * x[0] ** 2
class Interactive(Oracle):
    def __init__(self, rng):
        self.num_obj = 1
        self.dim = 1
        super().__init__(rng)
    def g(self, x, rng):
        return True, (helper(x) + rng.normalvariate(0, 1),)
"""


def interactive_class():
    """A class as a notebook cell leaves it: no source file, and a
    module name no process can import."""
    namespace = {'__name__': 'a_module_that_is_not_in_sys_modules'}
    exec(CELL, namespace)
    return namespace['Interactive']


def one_replication(cls, x=(4,)):
    stream = mrg32k3a.stream_at(mrg32k3a.DEFAULT_SEED, 2, 5)
    return cls(stream).g(x, stream)


def in_a_fresh_interpreter(payload, tmp_path, body):
    """Run `body` in a new interpreter that shares nothing with this
    one but the installed packages: isolated mode, another working
    directory, tests/ not on its path. `body` sees `ref`, the unpickled
    payload, and prints its result."""
    script = "import pickle, sys\nref = pickle.loads(sys.stdin.buffer.read())\n" + textwrap.dedent(body)
    result = subprocess.run(
        [sys.executable, "-I", "-c", script], input=payload, capture_output=True, cwd=tmp_path, timeout=SUBPROCESS_TIMEOUT,
    )
    assert result.returncode == 0, result.stderr.decode()
    return result.stdout.decode().strip()


REPLICATE = """
    from pymoso.prng import mrg32k3a
    stream = mrg32k3a.stream_at(mrg32k3a.DEFAULT_SEED, 2, 5)
    cls = ref.load()
    print(cls.__name__, cls(stream).g({x!r}, stream))
"""


def test_a_class_with_no_source_file_travels_by_value(tmp_path):
    cls = interactive_class()
    ref = ClassRef(cls)
    assert set(ref.descriptor) == {'by_value', 'class_name'} and ref.name == 'Interactive'
    expected = "Interactive {0}".format(one_replication(cls))
    assert in_a_fresh_interpreter(pickle.dumps(ref), tmp_path, REPLICATE.format(x=(4,))) == expected


def test_a_class_defined_inside_a_function_travels_by_value(tmp_path):
    def make():
        class Local(ProbTPA):
            pass
        return Local

    cls = make()
    ref = ClassRef(cls)
    assert 'by_value' in ref.descriptor
    expected = "Local {0}".format(one_replication(cls, (3, 4)))
    assert in_a_fresh_interpreter(pickle.dumps(ref), tmp_path, REPLICATE.format(x=(3, 4))) == expected


def test_a_problem_handle_built_from_such_a_class_is_transportable():
    handle = pickle.loads(pickle.dumps(ClassHandle(interactive_class())))
    assert handle.transportable is True and handle.load().__name__ == 'Interactive'


def test_having_cloudpickle_changes_nothing_for_a_class_that_already_travelled(tmp_path):
    """By reference where a worker can import it, as a source bundle
    where it came from a user's file: cloudpickle is the last resort,
    not the new default."""
    for cls in (ProbTPA, RPERLE, TPATester, _by_value_classes.DriverOnlyProblem):
        assert build_transport_descriptor(cls) is cls
    (tmp_path / "userprob.py").write_text(CELL)
    module = load_user_module("pymoso.problems.userprob", str(tmp_path / "userprob.py"))
    assert set(build_transport_descriptor(module.Interactive)) == {'files', 'entry', 'class_name'}


def test_for_a_remote_backend_only_pymoso_itself_travels_by_reference(tmp_path):
    for cls in (ProbTPA, RPERLE, TPATester):
        assert build_transport_descriptor(cls, remote=True) is cls
    (tmp_path / "userprob.py").write_text(CELL)
    module = load_user_module("pymoso.problems.userprob", str(tmp_path / "userprob.py"))
    assert 'files' in build_transport_descriptor(module.Interactive, remote=True)
    assert 'by_value' in build_transport_descriptor(_by_value_classes.DriverOnlyProblem, remote=True)


def test_a_class_only_this_process_can_import_reaches_a_remote_worker_by_value(tmp_path):
    """The gap a parent-side check cannot see: `pickle.dumps(cls)`
    succeeds here, and proves nothing about another machine. By
    reference the fresh interpreter cannot load it; sent as for a
    remote backend it can, module-level helpers and constants
    included."""
    cls = _by_value_classes.DriverOnlyProblem
    local = pickle.dumps(ClassRef(cls))
    result = subprocess.run(
        [sys.executable, "-I", "-c", "import pickle, sys\npickle.loads(sys.stdin.buffer.read()).load()"],
        input=local, capture_output=True, cwd=tmp_path, timeout=SUBPROCESS_TIMEOUT,
    )
    assert result.returncode != 0 and b"_by_value_classes" in result.stderr

    remote = pickle.dumps(ClassRef(cls, remote=True))
    expected = "DriverOnlyProblem {0}".format(one_replication(cls, (3, 4)))
    assert in_a_fresh_interpreter(remote, tmp_path, REPLICATE.format(x=(3, 4))) == expected


def test_sending_a_module_by_value_leaves_cloudpickles_registry_as_it_was():
    module = _by_value_classes
    assert module.__name__ not in cloudpickle.list_registry_pickle_by_value()
    ClassRef(module.DriverOnlyProblem, remote=True)
    assert module.__name__ not in cloudpickle.list_registry_pickle_by_value()
    cloudpickle.register_pickle_by_value(module)
    try:
        ClassRef(module.DriverOnlyProblem, remote=True)
        assert module.__name__ in cloudpickle.list_registry_pickle_by_value()      # the user's own registration survives
    finally:
        cloudpickle.unregister_pickle_by_value(module)


def test_a_class_that_cannot_be_pickled_by_value_is_refused_by_name():
    import threading
    namespace = {'__name__': 'a_module_that_is_not_in_sys_modules', 'LOCK': threading.Lock()}
    exec("from pymoso.chnbase import Oracle\nclass Holding(Oracle):\n    def g(self, x, rng):\n        return LOCK, ()\n", namespace)
    with pytest.raises(ValueError, match="Holding cannot be sent to a worker process"):
        ClassRef(namespace['Holding'])


def test_a_remote_backend_without_cloudpickle_refuses_a_class_from_outside_pymoso(monkeypatch):
    monkeypatch.setitem(sys.modules, 'cloudpickle', None)
    assert build_transport_descriptor(ProbTPA, remote=True) is ProbTPA
    with pytest.raises(ValueError, match=r"pymoso\[notebook\]"):
        ClassRef(_by_value_classes.DriverOnlyProblem, remote=True)


def test_reconstructing_a_by_value_descriptor_gives_the_same_class_each_time():
    """A worker loads its classes once, but nothing should depend on
    that: a tester's `ranorc` and a second load must agree."""
    descriptor = pickle.loads(pickle.dumps(build_transport_descriptor(interactive_class())))
    assert reconstruct_transport_descriptor(descriptor) is reconstruct_transport_descriptor(descriptor)


NOTEBOOK = """
import multiprocessing, sys
multiprocessing.set_start_method({method!r})
assert not hasattr(sys.modules['__main__'], '__file__')

from pymoso.chnbase import Oracle
from pymoso.chnutils import par_diff, solve, testsolve
from pymoso.solvers.rperle import RPERLE

LIMIT = 50

class CellProblem(Oracle):
    def __init__(self, rng):
        self.num_obj = 2
        self.dim = 2
        super().__init__(rng)
    def g(self, x, rng):
        if not all(-LIMIT <= xi <= LIMIT for xi in x):
            return False, ()
        z = rng.normalvariate(0, 1)
        return True, (x[0] ** 2 + x[1] ** 2 + z, (x[0] - 10) ** 2 + (x[1] - 10) ** 2 + z)

class CellTester:
    def __init__(self):
        self.ranorc = CellProblem
    def metric(self, eles):
        return len(eles)

class CellSolver(RPERLE):
    pass

if __name__ == '__main__':
    seed = (12345,) * 6
    assert solve(CellProblem, CellSolver, (20, 20), budget=600, seed=seed, simpar=2) == \\
        solve(CellProblem, CellSolver, (20, 20), budget=600, seed=seed)
    serial = testsolve(CellTester, CellSolver, (20, 20), budget=300, seed=seed, isp=3)
    assert testsolve(CellTester, CellSolver, (20, 20), budget=300, seed=seed, isp=3, proc=2) == serial
    assert par_diff(serial[0], CellTester(), 2) == par_diff(serial[0], CellTester(), 1)
    print('notebook classes ran on worker processes')
"""


@pytest.mark.parametrize("method", START_METHODS)
def test_classes_defined_interactively_run_on_worker_processes(method, tmp_path):
    """The notebook case end to end: the program is given with -c, so
    `__main__` has no file, as in a Jupyter kernel (the script asserts
    it). A problem, a tester and a solver defined there run under
    simpar=2 and proc=2 and give the serial results."""
    result = subprocess.run(
        [sys.executable, "-I", "-c", NOTEBOOK.format(method=method)],
        capture_output=True, cwd=tmp_path, timeout=SUBPROCESS_TIMEOUT,
    )
    assert result.returncode == 0, result.stderr.decode()
    assert b"notebook classes ran on worker processes" in result.stdout
