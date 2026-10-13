"""
Transport correctness for multi-file custom problems under --simpar
(KNOWN_ISSUES.md issue 7, docs/forkserver-hang.md): the actual
regression test for the forkserver hang, using a real multi-file
fixture (the one from KNOWN_ISSUES.md issue 9 / tests/test_cli.py --
requires that loading bug fixed first, or this test can't even get to
the transport question) run under real --simpar, not a synthetic
reproduction.

"Same result as serial execution" is checked two ways, not one:
end seed (the existing --simpar convention, per docs/upstream-simpar.md
-- seed assignment is deterministic and identical regardless of
simpar) AND the actual returned solution set, read back from each
run's saved output file. End seed alone is not enough evidence here --
see docs/end-seed-scope.md: it fingerprints the stream-allocation
schedule, not what any stream actually computed, so a transport bug
that silently reconstructs the wrong thing could still land on the
right end seed by coincidence. The solution set is the thing that
would actually catch that.

Confirmed failing before the fix landed (Python 3.14, forkserver
default): timed out, caught by pytest-timeout, not a clean assertion
failure -- exactly the hang docs/forkserver-hang.md diagnosed via
py-spy. A detector never observed detecting isn't proven to work.
"""
import ast
import re
import subprocess
import sys

import pytest

from _pymoso_cli import pymoso_argv

pytestmark = pytest.mark.timeout(90)

# Comfortably above the ~1-3s a real small --simpar run takes when it
# isn't hanging, well below the module-level pytest-timeout backstop --
# see tests/test_simpar_worker_lifecycle.py for the same convention.
SUBPROCESS_TIMEOUT = 30

SEED = ["1", "2", "3", "4", "5", "6"]

HELPER_SRC = '''\
PENALTY = 3.0

def noisy_quadratic(x0, rng):
    z = rng.normalvariate(0, 1)
    return x0**2 + PENALTY*z
'''

PROBLEM_SRC = '''\
from pymoso.chnbase import Oracle
from helper import noisy_quadratic, PENALTY

class MyProblem(Oracle):
    def __init__(self, rng):
        self.num_obj = 2
        self.dim = 1
        super().__init__(rng)

    def g(self, x, rng):
        feas_range = range(-100, 101)
        obj = []
        is_feas = False
        if len(x) == self.dim:
            is_feas = True
            for i in x:
                if not i in feas_range:
                    is_feas = False
        if is_feas:
            obj1 = noisy_quadratic(x[0], rng)
            z1 = rng.normalvariate(0, 1)
            obj2 = (x[0] - 2)**2 + z1 + 0*PENALTY
            obj = (obj1, obj2)
        return is_feas, obj
'''

SEED_RE = re.compile(r"^--\s+(?:next|ending) seed:\s+(.+)$", re.M)


def run_solve(tmp_path, odir, extra_args):
    cmd = ["pymoso", "solve", "--budget=200", f"--odir={odir}", "--seed", ",".join(SEED),
           *extra_args, "myproblem.py", "RPERLE", "40"]
    try:
        return subprocess.run(pymoso_argv(cmd), cwd=tmp_path, capture_output=True, text=True,
                               timeout=SUBPROCESS_TIMEOUT)
    except subprocess.TimeoutExpired:
        pytest.fail(
            f"{' '.join(cmd)} did not complete within {SUBPROCESS_TIMEOUT}s -- "
            "the forkserver hang (KNOWN_ISSUES.md issue 7, docs/forkserver-hang.md) "
            "has regressed, or the transport fix isn't landed yet."
        )


def end_seed(proc):
    match = SEED_RE.search(proc.stdout)
    assert match, f"no seed line found in:\n{proc.stdout}"
    return tuple(int(v) for v in match.group(1).split())


def solution_set(tmp_path, odir):
    rundata = tmp_path / odir / f"rundata_{odir}.txt"
    assert rundata.is_file(), f"{rundata} was not written"
    lines = [l for l in rundata.read_text().splitlines() if l.strip()]
    return {ast.literal_eval(l) for l in lines}


def test_multifile_problem_under_simpar_matches_serial(tmp_path):
    (tmp_path / 'helper.py').write_text(HELPER_SRC)
    (tmp_path / 'myproblem.py').write_text(PROBLEM_SRC)

    serial = run_solve(tmp_path, "serial_run", [])
    assert serial.returncode == 0, serial.stderr

    parallel = run_solve(tmp_path, "parallel_run", ["--simpar=4"])
    assert parallel.returncode == 0, parallel.stderr

    assert end_seed(parallel) == end_seed(serial)
    assert solution_set(tmp_path, "parallel_run") == solution_set(tmp_path, "serial_run")


# ---------------------------------------------------------------------------
# testsolve()'s --proc path (KNOWN_ISSUES.md issue 7). It used to send
# each worker a fully-constructed, already-seeded Oracle instance
# through a multiprocessing.Pool, which a worker started by forkserver
# or spawn could not unpickle (the instance's class lives in a module
# only this process loaded) -- and the dead worker left the parent
# waiting forever. A path is now sent as data (chnutils.PathJob) and
# the tester and solver classes as source bundles, once per worker.
#
# Observed failing first, against the code before that change, on
# Python 3.14 (forkserver): `ModuleNotFoundError: No module named
# 'myproblem'` in the worker, then a hang until the timeout. It was a
# strict xfail on non-fork start methods until then.
# ---------------------------------------------------------------------------

MYTESTER_SRC = '''\
from myproblem import MyProblem

def true_g(x):
    return (x[0]**2, (x[0] - 2)**2)

def get_ranx0(rng):
    return (rng.choice(range(-100, 101)),)

class MyTester(object):
    def __init__(self):
        self.ranorc = MyProblem
        self.true_g = true_g
        self.soln = [(0,), (2,)]
        self.get_ranx0 = get_ranx0

    def metric(self, eles):
        return float(sum(abs(x[0]) for x in eles))
'''


MYSOLVER_SRC = '''\
from pymoso.chnbase import RLESolver
from solverhelper import same

class MySolver(RLESolver):
    def accel(self, warm_start):
        return same(warm_start)
'''

SOLVERHELPER_SRC = '''\
def same(points):
    return points
'''


def run_testsolve(tmp_path, odir, extra_args, solver="RPERLE"):
    cmd = ["pymoso", "testsolve", "--budget=200", "--isp=2", "--metric", f"--odir={odir}",
           "--seed", ",".join(SEED), *extra_args, "mytester.py", solver, "40"]
    try:
        proc = subprocess.run(pymoso_argv(cmd), cwd=tmp_path, capture_output=True, text=True,
                               timeout=SUBPROCESS_TIMEOUT)
    except subprocess.TimeoutExpired:
        pytest.fail(
            f"{' '.join(cmd)} did not complete within {SUBPROCESS_TIMEOUT}s -- "
            "KNOWN_ISSUES.md issue 7's --proc hang has regressed."
        )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "Error" not in proc.stdout, proc.stdout
    # Per-path results and metrics, by file name with the run's own
    # name removed. The summary file is left out: it records run times.
    files = {f.name.replace(odir, ""): f.read_text()
             for f in (tmp_path / odir).iterdir() if f.name != f"{odir}.txt"}
    assert sorted(files) == ["ispdata_0_.txt", "ispdata_1_.txt", "metrics_0_.txt", "metrics_1_.txt"]
    return end_seed(proc), files


def write_fixture(tmp_path):
    (tmp_path / 'helper.py').write_text(HELPER_SRC)
    (tmp_path / 'myproblem.py').write_text(PROBLEM_SRC)
    (tmp_path / 'mytester.py').write_text(MYTESTER_SRC)


def test_multifile_problem_under_proc_matches_serial(tmp_path):
    """Two paths on two workers, so paths and metrics both really cross
    a process boundary (with one path, or --proc=1, nothing does)."""
    write_fixture(tmp_path)
    serial = run_testsolve(tmp_path, "serial_run", ["--proc=1"])
    parallel = run_testsolve(tmp_path, "parallel_run", ["--proc=2"])
    assert parallel == serial


def test_custom_solver_file_under_proc_matches_serial(tmp_path):
    """A solver can be a user-supplied file too, with imports of its
    own, and reaches a worker the same way a problem does."""
    write_fixture(tmp_path)
    (tmp_path / 'mysolver.py').write_text(MYSOLVER_SRC)
    (tmp_path / 'solverhelper.py').write_text(SOLVERHELPER_SRC)
    serial = run_testsolve(tmp_path, "serial_run", ["--proc=1"], solver="mysolver.py")
    parallel = run_testsolve(tmp_path, "parallel_run", ["--proc=2"], solver="mysolver.py")
    assert parallel == serial


# ---------------------------------------------------------------------------
# Unit-level pins on chnbase's transport helpers directly, no subprocess
# needed for these two.
# ---------------------------------------------------------------------------

def test_build_transport_descriptor_passes_builtin_classes_through_unchanged():
    """A real, installed problem class already pickles by reference
    correctly regardless of start method -- no bundling needed, and
    bundling it would be wasted work (and, for a package directory,
    would ship unrelated sibling files for no reason)."""
    from pymoso.chnbase import build_transport_descriptor
    from pymoso.problems.probtpa import ProbTPA
    assert build_transport_descriptor(ProbTPA) is ProbTPA


def test_build_transport_descriptor_raises_clear_error_for_interactive_class(monkeypatch):
    """A class with no locatable source (defined interactively -- a
    REPL or notebook, not loaded from a .py file) must raise a clear
    error naming the limitation, not silently attempt transport and
    hang once a --simpar job is actually dispatched to it. That is
    the behaviour without cloudpickle; with it the class travels by
    value (test_by_value_transport.py)."""
    monkeypatch.setitem(sys.modules, 'cloudpickle', None)       # as where the `notebook` extra is not installed
    from pymoso.chnbase import build_transport_descriptor, Oracle

    ns = {}
    exec(
        "class Interactive(Oracle):\n"
        "    def __init__(self, rng):\n"
        "        self.num_obj = 1\n"
        "        self.dim = 1\n"
        "        super().__init__(rng)\n"
        "    def g(self, x, rng):\n"
        "        return True, (0.0,)\n",
        {'Oracle': Oracle}, ns,
    )
    Interactive = ns['Interactive']
    # A module name that exists nowhere in sys.modules -- simulates
    # "no locatable source" robustly across host processes. Using
    # '__main__' here instead would be host-dependent: under plain
    # `python -c`, '__main__' has no __file__ (correctly triggers the
    # error), but under pytest, '__main__' is pytest's own launcher
    # module, which *does* have a real __file__ -- inspect.getfile
    # would find that (unrelated) file instead of raising, so the test
    # would pass under one host and silently not exercise the error
    # path under another.
    Interactive.__module__ = 'a_module_that_is_not_in_sys_modules'

    with pytest.raises(ValueError) as exc_info:
        build_transport_descriptor(Interactive)
    msg = str(exc_info.value)
    assert 'Interactive' in msg
    assert 'no locatable source' in msg
    assert 'pymoso[notebook]' in msg


def test_reconstruct_transport_descriptor_resolves_cross_file_dependency():
    """Pins the actual bug found while implementing this: a naive
    "non-entry files first, entry last" execution order breaks when a
    NON-entry file in the bundle imports the entry file (confirmed
    directly -- pymoso/examples/mytester.py imports
    pymoso/examples/myproblem.py, and a real fixture built from that
    directory bundles both even when only myproblem.py is the entry
    point, since build_transport_descriptor ships every .py file in
    the directory). reconstruct_transport_descriptor must resolve this
    regardless of which name sorts first."""
    from pymoso.chnbase import reconstruct_transport_descriptor

    descriptor = {
        'files': {
            'entry_point': 'X = 1\n',
            'unrelated_sibling': 'from entry_point import X\nY = X + 1\n',
        },
        'entry': 'entry_point',
        'class_name': 'X',
    }
    # A naive "every non-entry file first, then the entry file last"
    # order (what this used to do) would try 'unrelated_sibling' before
    # 'entry_point' unconditionally -- entry_point is always excluded
    # from that first pass by construction -- and 'unrelated_sibling'
    # needs entry_point already populated, so that order always fails
    # here regardless of name sorting. The fixed-point retry resolves
    # it by trying again once entry_point succeeds.
    assert reconstruct_transport_descriptor(descriptor) == 1
