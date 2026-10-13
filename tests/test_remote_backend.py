"""
A remote backend without a cluster.

`backends.remote.RemoteBackend` asks one thing of wherever its work
runs: call `run_task` on these bytes and return what it returns. The
backend used here does that in a fresh interpreter, started in
isolated mode in another directory, which shares with this process
only the installed packages -- no modules of this process, no working
directory, no path entries. That is the part of "another machine" that
decides whether a payload is self-contained, and it needs no JVM, so
these tests run in every CI cell. What they cannot show is anything
about Spark itself; tests/test_spark_backend.py does that.

The standing requirement is that a backend computes the same numbers
as no backend. Each identity test here compares whole results --
every iteration's solution set, every path, and the end seed -- and
`test_identity_is_broken_by_a_backend_that_answers_out_of_order` shows
the comparison failing when it should.
"""
import pathlib
import pickle
import subprocess
import sys
import warnings

import pytest

import _remote_tasks
from _extras import need
import pymoso
from pymoso.backends.remote import RemoteBackend, SlowDispatchWarning, VersionMismatch
from pymoso.chnutils import par_diff, solve, testsolve
from pymoso.commands.basecomm import load_user_module
from pymoso.pool import RemoteTraceback, WorkerError
from pymoso.problems.probtpa import ProbTPA
from pymoso.solvers.rperle import RPERLE
from pymoso.testers.tpatester import TPATester

pytestmark = [
    pytest.mark.timeout(180),
    # Every workload here is far too cheap to be worth dispatching, and
    # the backend says so. The tests of that warning ask for it.
    pytest.mark.filterwarnings("ignore::pymoso.backends.remote.SlowDispatchWarning"),
]

SUBPROCESS_TIMEOUT = 120
SEED = (12345,) * 6
TESTS = str(pathlib.Path(__file__).resolve().parent)

WORKER = """
import pickle, sys
{path}
from pymoso.backends.remote import run_task
init_payload, payloads, version, order = pickle.load(sys.stdin.buffer)
answers = {{}}
for index in order:
    answers[index] = run_task(init_payload, payloads[index], version)
sys.stdout.buffer.write(pickle.dumps([answers[index] for index in range(len(payloads))]))
"""


class FreshInterpreterBackend(RemoteBackend):
    """Each dispatch runs in a new interpreter, tasks in reverse order
    (nothing may depend on the order they run in).

    Parameters
    ----------
    cwd : path
        Where the interpreter starts: somewhere unrelated.
    path : str or None
        One directory to put on its path, for tests of the pool
        contract itself, whose tasks live in tests/_remote_tasks.py.
        The identity tests leave it out.
    version : str
        What to claim as the sender's pymoso version.
    """

    def __init__(self, cwd, path=None, version=pymoso.__version__):
        super().__init__()
        self.cwd = cwd
        self.path = path
        self.version = version

    def dispatch(self, init_payload, payloads):
        script = WORKER.format(path="sys.path.insert(0, {0!r})".format(self.path) if self.path else "")
        order = list(reversed(range(len(payloads))))
        result = subprocess.run(
            [sys.executable, "-I", "-c", script], input=pickle.dumps((init_payload, payloads, self.version, order)),
            capture_output=True, cwd=self.cwd, timeout=SUBPROCESS_TIMEOUT,
        )
        assert result.returncode == 0, result.stderr.decode()
        return pickle.loads(result.stdout)


class OutOfOrderBackend(FreshInterpreterBackend):
    """A defective backend: right answers, wrong order."""

    def dispatch(self, init_payload, payloads):
        return list(reversed(super().dispatch(init_payload, payloads)))


USER_PROBLEM = """
from pymoso.chnbase import Oracle
from helper import penalty

class UserProblem(Oracle):
    def __init__(self, rng):
        self.num_obj = 2
        self.dim = 2
        super().__init__(rng)
    def g(self, x, rng):
        if not all(-50 <= xi <= 50 for xi in x):
            return False, ()
        z = rng.normalvariate(0, 1)
        return True, (x[0] ** 2 + x[1] ** 2 + z, penalty(x) + z)

class UserTester:
    def __init__(self):
        self.ranorc = UserProblem
    def metric(self, eles):
        return len(eles)

class RaisingProblem(UserProblem):
    def g(self, x, rng):
        raise ZeroDivisionError('g() failed at x={0}'.format(x))
"""
USER_HELPER = "def penalty(x):\n    return (x[0] - 10) ** 2 + (x[1] - 10) ** 2\n"


@pytest.fixture
def user_module(tmp_path):
    """A problem and a tester in a user's own two files, loaded the way
    the CLI loads them -- the source-bundle case."""
    directory = tmp_path / "userfiles"
    directory.mkdir()
    (directory / "userproblem.py").write_text(USER_PROBLEM)
    (directory / "helper.py").write_text(USER_HELPER)
    return load_user_module("pymoso.problems.userproblem", str(directory / "userproblem.py"))


@pytest.fixture
def elsewhere(tmp_path):
    directory = tmp_path / "elsewhere"
    directory.mkdir()
    return directory


# ---------------------------------------------------------------------------
# Identity: a backend computes what no backend computes
# ---------------------------------------------------------------------------

def test_sample_paths_on_a_remote_backend_are_identical_to_serial(elsewhere):
    backend = FreshInterpreterBackend(elsewhere)
    kwargs = dict(budget=300, seed=SEED, isp=4)
    assert testsolve(TPATester, RPERLE, (40, 40), backend=backend, **kwargs) == testsolve(TPATester, RPERLE, (40, 40), **kwargs)
    assert backend.jobs == 1


@pytest.mark.parametrize("crn", [False, True])
def test_replications_on_a_remote_backend_are_identical_to_serial(elsewhere, crn):
    backend = FreshInterpreterBackend(elsewhere)
    kwargs = dict(budget=150, seed=SEED, crn=crn)
    assert solve(ProbTPA, RPERLE, (40, 40), simpar=3, backend=backend, **kwargs) == solve(ProbTPA, RPERLE, (40, 40), **kwargs)
    assert backend.jobs > 1                                # one dispatch per request the solver made


def test_a_users_own_files_reach_a_remote_backend_as_their_text(user_module, elsewhere):
    """The source bundle carries the files' text, so it needs no
    filesystem in common with the worker: the worker here starts in
    another directory and is given no path to the user's."""
    backend = FreshInterpreterBackend(elsewhere)
    kwargs = dict(budget=300, seed=SEED, isp=3)
    expected = testsolve(user_module.UserTester, RPERLE, (20, 20), **kwargs)
    assert testsolve(user_module.UserTester, RPERLE, (20, 20), backend=backend, **kwargs) == expected
    kwargs = dict(budget=120, seed=SEED)
    expected = solve(user_module.UserProblem, RPERLE, (20, 20), **kwargs)
    assert solve(user_module.UserProblem, RPERLE, (20, 20), simpar=2, backend=backend, **kwargs) == expected


def test_metrics_on_a_remote_backend_are_identical_to_local(elsewhere):
    res, _ = testsolve(TPATester, RPERLE, (40, 40), budget=300, seed=SEED, isp=3)
    tester = TPATester()
    backend = FreshInterpreterBackend(elsewhere)
    assert par_diff(res, tester, 1, backend=backend) == par_diff(res, tester, 1)
    assert backend.jobs == 1


def test_classes_from_a_module_only_this_process_can_import_run_on_a_remote_backend(elsewhere):
    need("cloudpickle")
    import _by_value_classes as mine
    backend = FreshInterpreterBackend(elsewhere)
    kwargs = dict(budget=300, seed=SEED, isp=3)
    expected = testsolve(mine.DriverOnlyTester, mine.DriverOnlySolver, (20, 20), **kwargs)
    assert testsolve(mine.DriverOnlyTester, mine.DriverOnlySolver, (20, 20), backend=backend, **kwargs) == expected
    kwargs = dict(budget=120, seed=SEED)
    expected = solve(mine.DriverOnlyProblem, mine.DriverOnlySolver, (20, 20), **kwargs)
    assert solve(mine.DriverOnlyProblem, mine.DriverOnlySolver, (20, 20), simpar=2, backend=backend, **kwargs) == expected


def test_identity_is_broken_by_a_backend_that_answers_out_of_order(elsewhere):
    """The detector, shown detecting. Without this the identity tests
    above could be comparing a thing with itself."""
    kwargs = dict(budget=300, seed=SEED, isp=4)
    expected = testsolve(TPATester, RPERLE, (40, 40), **kwargs)
    assert testsolve(TPATester, RPERLE, (40, 40), backend=OutOfOrderBackend(elsewhere), **kwargs) != expected
    kwargs = dict(budget=150, seed=SEED)
    expected = solve(ProbTPA, RPERLE, (40, 40), **kwargs)
    try:
        wrong = solve(ProbTPA, RPERLE, (40, 40), simpar=3, backend=OutOfOrderBackend(elsewhere), **kwargs)
    except Exception:
        return                                              # replications credited to the wrong point: any failure will do
    assert wrong != expected


# ---------------------------------------------------------------------------
# How solve() and testsolve() treat a remote backend
# ---------------------------------------------------------------------------

def test_a_single_path_still_goes_to_a_remote_backend(elsewhere):
    """Locally one path means no pool. A user who passed a cluster
    asked for the work to run there."""
    backend = FreshInterpreterBackend(elsewhere)
    kwargs = dict(budget=200, seed=SEED, isp=1)
    assert testsolve(TPATester, RPERLE, (40, 40), backend=backend, **kwargs) == testsolve(TPATester, RPERLE, (40, 40), **kwargs)
    assert backend.jobs == 1


def test_proc_is_refused_with_a_remote_backend(elsewhere):
    with pytest.raises(ValueError, match="Leave proc out"):
        testsolve(TPATester, RPERLE, (40, 40), budget=100, isp=2, proc=2, backend=FreshInterpreterBackend(elsewhere))


def test_solve_refuses_a_remote_backend_without_a_simpar_and_says_when_it_pays(elsewhere):
    backend = FreshInterpreterBackend(elsewhere)
    with pytest.raises(ValueError, match="roughly 100 ms") as refused:
        solve(ProbTPA, RPERLE, (40, 40), budget=100, backend=backend)
    assert "simpar" in str(refused.value) and backend.jobs == 0


# ---------------------------------------------------------------------------
# The pool contract, on bytes
# ---------------------------------------------------------------------------

def test_results_come_back_in_order_and_the_initializer_runs_once_per_worker(elsewhere):
    backend = FreshInterpreterBackend(elsewhere, path=TESTS)
    with backend.pool(99, _remote_tasks.counting_state, ('here',)) as pool:
        assert pool.run([(_remote_tasks.report, (n,)) for n in range(5)]) == [('here', 1, n) for n in range(5)]
        assert pool.run([]) == []
    assert backend.jobs == 1                                # nothing is dispatched for no tasks


def test_a_task_that_raises_is_raised_here_as_itself_and_the_earliest_wins(elsewhere):
    backend = FreshInterpreterBackend(elsewhere, path=TESTS)
    with backend.pool(1, _remote_tasks.counting_state, ('here',)) as pool:
        with pytest.raises(KeyError, match="task 3 failed") as raised:
            pool.run([(_remote_tasks.fail_on_odd, (n,)) for n in (2, 3, 4, 5)])
        assert isinstance(raised.value.__cause__, RemoteTraceback) and "fail_on_odd" in raised.value.__cause__.text
        assert pool.run([(_remote_tasks.fail_on_odd, (n,)) for n in (2, 4)]) == [2, 4]      # still usable


def test_a_failing_initializer_is_reported_by_the_task_that_needed_it(elsewhere):
    backend = FreshInterpreterBackend(elsewhere, path=TESTS)
    with backend.pool(1, _remote_tasks.failing_initializer) as pool:
        with pytest.raises(OSError, match="the initializer failed"):
            pool.run([(_remote_tasks.report, (1,))])


def test_a_result_that_cannot_travel_is_reported_not_lost(elsewhere):
    backend = FreshInterpreterBackend(elsewhere, path=TESTS)
    with backend.pool(1, _remote_tasks.counting_state, ('here',)) as pool:
        with pytest.raises(Exception) as raised:
            pool.run([(_remote_tasks.unpicklable_result, (1,))])
    assert isinstance(raised.value.__cause__, RemoteTraceback)


def test_an_exception_from_g_reaches_the_caller_from_a_remote_backend(user_module, elsewhere):
    backend = FreshInterpreterBackend(elsewhere)
    with pytest.raises(Exception, match=r"g\(\) failed at x=\(20, 20\)") as remote:
        solve(user_module.RaisingProblem, RPERLE, (20, 20), budget=100, seed=SEED, simpar=2, backend=backend)
    with pytest.raises(Exception, match=r"g\(\) failed at x=\(20, 20\)") as serial:
        solve(user_module.RaisingProblem, RPERLE, (20, 20), budget=100, seed=SEED)
    assert type(remote.value) is type(serial.value) and not isinstance(remote.value, WorkerError)


def test_a_worker_running_another_pymoso_is_an_error_not_a_different_answer(elsewhere):
    backend = FreshInterpreterBackend(elsewhere, version="0.0.0-not-this-one")
    with pytest.raises(VersionMismatch, match="0.0.0-not-this-one"):
        testsolve(TPATester, RPERLE, (40, 40), budget=100, seed=SEED, isp=2, backend=backend)


def test_a_pool_must_be_open_and_only_once(elsewhere):
    pool = FreshInterpreterBackend(elsewhere).pool(1)
    with pytest.raises(RuntimeError, match="not open"):
        pool.run([(_remote_tasks.report, (1,))])
    pool.open()
    with pytest.raises(RuntimeError, match="already open"):
        pool.open()
    pool.close()
    pool.close()


# ---------------------------------------------------------------------------
# Saying so when dispatch is losing time
# ---------------------------------------------------------------------------

def test_a_backend_warns_once_when_dispatch_costs_more_than_the_work():
    backend = RemoteBackend()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        for _ in range(RemoteBackend.WARN_AFTER - 1):
            backend.account(0.080, 0.020)
        assert caught == []                                 # too early to judge
        backend.account(0.080, 0.020)
        backend.account(0.080, 0.020)
    assert [w.category for w in caught] == [SlowDispatchWarning]
    message = str(caught[0].message)
    assert "100 ms" in message and "docs/spark-backend.md" in message
    assert backend.jobs == RemoteBackend.WARN_AFTER + 1


def test_a_backend_that_pays_does_not_warn():
    backend = RemoteBackend()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        for _ in range(3 * RemoteBackend.WARN_AFTER):
            backend.account(0.25, 1.2)                      # six tasks of 200 ms, done in 250 ms
    assert caught == []


def test_cheap_replications_on_a_remote_backend_warn(elsewhere):
    """End to end: ProbTPA costs microseconds a replication, and a
    fresh interpreter per dispatch costs tens of milliseconds."""
    backend = FreshInterpreterBackend(elsewhere)
    with pytest.warns(SlowDispatchWarning, match="Running without backend= would be faster"):
        solve(ProbTPA, RPERLE, (40, 40), budget=150, seed=SEED, simpar=3, backend=backend)


# ---------------------------------------------------------------------------
# The Spark module without Spark
# ---------------------------------------------------------------------------

def test_the_spark_backend_module_imports_without_pyspark(tmp_path):
    """pyspark is imported when a job is dispatched, not before, so
    the module's own documentation and the class are reachable -- and
    this file's subject, RemoteBackend, testable -- where pyspark is
    not installed."""
    script = (
        "import sys\n"
        "sys.modules['pyspark'] = None\n"
        "from pymoso.backends.spark import SparkBackend\n"
        "backend = SparkBackend(object())\n"
        "assert backend.remote is True\n"
        "try:\n"
        "    backend.dispatch(b'', [b''])\n"
        "except ImportError:\n"
        "    print('needs pyspark only to dispatch')\n"
    )
    result = subprocess.run([sys.executable, "-I", "-c", script], capture_output=True, text=True, cwd=tmp_path, timeout=SUBPROCESS_TIMEOUT)
    assert result.returncode == 0, result.stderr
    assert "needs pyspark only to dispatch" in result.stdout
