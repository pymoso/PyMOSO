"""
pymoso/pool.py: the one worker-process lifecycle, and the three
failures it exists to handle -- a task that raises (KNOWN_ISSUES.md
issue 15), a worker that dies, and a parent that is killed (issue 8).

Every test runs under each start method the platform has. The
lifecycle bugs this project has had were each invisible under one
start method and a hang under another.
"""
import multiprocessing
import os
import pathlib
import pickle
import subprocess
import sys
import time

import pytest

import _pool_tasks as tasks
from pymoso.pool import RemoteTraceback, WorkerCrashed, WorkerError, WorkerPool

pytestmark = pytest.mark.timeout(120)

METHODS = multiprocessing.get_all_start_methods()
methods = pytest.mark.parametrize("method", METHODS)

# What pickle raises for something it cannot pickle, by type. Which of
# the three, and with what message, depends on the CPython version;
# these are the types pymoso/pool.py itself handles. Never match on the
# message of one of these.
CANNOT_PICKLE = (pickle.PicklingError, TypeError, AttributeError)


def pool(method, workers=2, initializer=None, initargs=()):
    return WorkerPool(workers, initializer, initargs, context=multiprocessing.get_context(method))


def alive(pid):
    if sys.platform.startswith("linux"):
        try:
            stat = pathlib.Path("/proc/{0}/stat".format(pid)).read_text()
        except OSError:
            return False
        return stat.rsplit(")", 1)[1].split()[0] != "Z"
    if os.name == "nt":
        import ctypes
        handle = ctypes.windll.kernel32.OpenProcess(0x00100000, False, pid)     # SYNCHRONIZE
        if not handle:
            return False
        try:
            return ctypes.windll.kernel32.WaitForSingleObject(handle, 0) == 0x102   # WAIT_TIMEOUT
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def wait_until_dead(pids, seconds):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if not any(alive(p) for p in pids):
            return []
        time.sleep(0.05)
    return [p for p in pids if alive(p)]


# ---------------------------------------------------------------------------
# Running work
# ---------------------------------------------------------------------------

@methods
def test_results_come_back_in_task_order_from_initialised_workers(method):
    with pool(method, 3, tasks.make_state, ("abc",)) as p:
        out = p.run([(tasks.slow_echo, (i, 0.05 * (5 - i))) for i in range(5)])
        assert out == [0, 1, 2, 3, 4]
        assert p.run([(tasks.echo, (7,))]) == [(7, "abc")]
        assert p.run([]) == []
        assert len(set(p.run([(tasks.pid, ())] * 12))) <= 3


@methods
def test_more_tasks_than_workers_and_more_workers_than_tasks(method):
    with pool(method, 2) as p:
        assert p.run([(tasks.slow_echo, (i, 0.0)) for i in range(25)]) == list(range(25))
    with pool(method, 4) as p:
        assert p.run([(tasks.slow_echo, (1, 0.0))]) == [1]


def test_lifecycle_open_run_close():
    p = WorkerPool(1)
    with pytest.raises(RuntimeError):
        p.run([(tasks.pid, ())])
    p.close()                                       # closing a pool that is not open is fine
    assert p.open() is p
    with pytest.raises(RuntimeError):
        p.open()
    (worker_pid,) = p.run([(tasks.pid, ())])
    p.close()
    p.close()
    assert wait_until_dead([worker_pid], 10) == []
    with pytest.raises(RuntimeError):
        p.run([(tasks.pid, ())])
    with p.open():                                  # reusable, and open() works as the with-target
        assert p.run([(tasks.pid, ())]) != [worker_pid]


def test_a_pool_needs_a_worker():
    with pytest.raises(ValueError):
        WorkerPool(0)


@methods
def test_leaving_the_block_on_an_exception_stops_workers_mid_task(method):
    """Teardown does not wait for a long task: this would take a minute."""
    start = time.monotonic()
    with pytest.raises(KeyError):
        with pool(method, 2) as p:
            pids = p.run([(tasks.pid, ())] * 2)
            for worker in p._workers:
                worker.conn.send((tasks.slow_echo, (0, 60.0)))
            pids = [w.process.pid for w in p._workers]
            raise KeyError("leaving")
    assert wait_until_dead(pids, 10) == []
    assert time.monotonic() - start < 30


# ---------------------------------------------------------------------------
# A task that raises
# ---------------------------------------------------------------------------

@methods
def test_a_task_exception_is_raised_in_the_caller_as_itself_with_its_traceback(method):
    with pool(method, 2) as p:
        with pytest.raises(ZeroDivisionError, match="boom at 3") as info:
            p.run([(tasks.raise_after, (3, 0.0))])
        assert isinstance(info.value.__cause__, RemoteTraceback)
        assert "raise_after" in str(info.value.__cause__)
        # and the pool still works
        assert p.run([(tasks.slow_echo, (1, 0.0))]) == [1]


@methods
def test_the_earliest_failing_task_wins_even_if_a_later_one_fails_first(method):
    with pool(method, 2) as p:
        with pytest.raises(ZeroDivisionError, match="boom at first"):
            p.run([(tasks.raise_after, ("first", 0.5)), (tasks.raise_after, ("second", 0.0))])
        assert p.run([(tasks.slow_echo, (1, 0.0))]) == [1]


@methods
def test_tasks_after_a_failure_are_not_started(method):
    with pool(method, 1, tasks.make_state, ("s",)) as p:
        with pytest.raises(ZeroDivisionError):
            p.run([(tasks.raise_after, (0, 0.0))] + [(tasks.echo, (i,)) for i in range(5)])
        # echo counts its calls in the worker's state: this is the first
        assert p.run([(tasks.echo, (9,))]) == [(9, "s")]


@methods
def test_an_exception_or_result_that_cannot_travel_is_still_reported(method):
    """The result that will not pickle is asserted on by exception type
    and by where it came from, not by its message: the message is
    CPython's and its wording differs by version ("Can't pickle local
    object ..." on 3.10, 3.11 and 3.14, "Can't get local object ..." on
    3.12 and 3.13 -- a `match="pickle"` here passed on three versions
    and failed on two). The first half matches a message because that
    one is ours.

    Not asserted: that the error names the task. It does today, but
    only because CPython's message quotes the lambda's qualified name.
    Follow-up recorded in CLAUDE.md: have pool.py name the task
    itself, and then assert on that here."""
    with pool(method, 1) as p:
        with pytest.raises(WorkerError, match="Unpicklable: cannot travel") as info:
            p.run([(tasks.raise_unpicklable, ())])
        assert "raise_unpicklable" in str(info.value.__cause__)
        with pytest.raises(CANNOT_PICKLE) as info:
            p.run([(tasks.return_unpicklable, ())])
        # it failed in the worker, sending the result, and came back
        assert isinstance(info.value.__cause__, RemoteTraceback)
        assert p.run([(tasks.slow_echo, (1, 0.0))]) == [1]


@methods
def test_a_task_that_cannot_be_sent_fails_in_the_caller_and_leaves_the_pool_usable(method):
    with pool(method, 1) as p:
        with pytest.raises(CANNOT_PICKLE) as info:
            p.run([(tasks.echo, (lambda: None,))])
        assert info.value.__cause__ is None        # raised here; no worker was involved
        assert p.run([(tasks.slow_echo, (1, 0.0))]) == [1]


# ---------------------------------------------------------------------------
# Start-up failures surface in open(), not as a hang later
# ---------------------------------------------------------------------------

@methods
def test_an_initializer_that_raises_fails_open_and_leaves_no_workers(method):
    p = pool(method, 3, tasks.failing_initializer)
    with pytest.raises(LookupError, match="no such thing"):
        p.open()
    assert p._workers == []
    with pytest.raises(RuntimeError):
        p.run([(tasks.pid, ())])


@methods
def test_an_unpicklable_initializer_fails_open_under_every_start_method(method):
    """fork would carry a lambda across; the pool must not let it."""
    for p in (pool(method, 1, lambda: None), pool(method, 1, tasks.make_state, (lambda: None,))):
        with pytest.raises(CANNOT_PICKLE):
            p.open()
        assert p._workers == []


# ---------------------------------------------------------------------------
# A worker that dies
# ---------------------------------------------------------------------------

@methods
def test_a_worker_that_dies_mid_task_raises_instead_of_hanging(method):
    with pool(method, 2) as p:
        pids = p.run([(tasks.pid, ())] * 2)
        with pytest.raises(WorkerCrashed, match="exit code 7"):
            p.run([(tasks.slow_echo, (1, 0.2)), (tasks.die, (7,))])
        with pytest.raises(RuntimeError, match="a worker died"):
            p.run([(tasks.pid, ())])
    assert wait_until_dead(pids, 10) == []


# ---------------------------------------------------------------------------
# A parent that is killed
# ---------------------------------------------------------------------------

@methods
@pytest.mark.parametrize("mode", ["idle", "busy"])
def test_workers_exit_when_the_parent_is_killed(method, mode):
    """KNOWN_ISSUES.md issue 8. The parent gets no chance to clean up
    (SIGKILL; TerminateProcess on Windows), so the workers have to
    notice on their own. 'busy' workers are each two seconds into
    nothing when it happens; they finish that and then exit."""
    script = pathlib.Path(__file__).with_name("_pool_parent_kill.py")
    parent = subprocess.Popen([sys.executable, str(script), method, mode],
                              stdout=subprocess.PIPE, text=True)
    try:
        pids = [int(p) for p in parent.stdout.readline().split()]
        assert len(pids) == 3 and all(alive(p) for p in pids)
        if mode == "busy":
            time.sleep(0.5)
    finally:
        parent.kill()
        parent.wait()
        parent.stdout.close()
    assert wait_until_dead(pids, 20) == [], "workers outlived their parent"
