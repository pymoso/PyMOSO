"""
A backend whose workers are reached only by sending them bytes.

`pool.WorkerPool` starts its own processes, hands each an initializer,
and talks to them over pipes. A cluster offers none of that: there is
no process to start, no per-worker hook, and no channel but "run this
function on that input and give me what it returns". `RemoteBackend`
is the pool contract (`pool.LocalBackend`) rebuilt on that one
primitive, with everything that is not the primitive itself kept here,
where it needs no cluster to run or to test:

- `run_task` is what runs on a worker: bytes in, bytes out. It builds
  the worker's state from the initializer the first time that worker
  sees it and keeps it for later tasks, which is what a pool's
  initializer does. It catches whatever the task raises and returns it
  as data, so the caller can raise the exception itself, as itself --
  and so a cluster that retries failed tasks does not re-run a long
  sample path four times to reach the same error.
- `RemotePool` pickles the initializer and the tasks, hands the bytes
  to the backend's `dispatch`, and turns the answers back into results
  in order, or into the earliest task's exception.
- A subclass supplies `dispatch` and nothing else
  (`backends.spark.SparkBackend`).

Every task is a function of its bytes alone: a replication block or a
sample path computes its streams from coordinates it carries. So a
task run twice (a retry, a speculative copy) or on any worker gives
the same answer, and a backend needs no ordering or exactly-once
guarantee from its cluster.
"""
import hashlib
import pickle
import time
import warnings
from collections import OrderedDict

from .. import __version__
from ..pool import _describe, _rebuild


class VersionMismatch(RuntimeError):
    """The pymoso that ran a task is not the pymoso that sent it."""


class SlowDispatchWarning(RuntimeWarning):
    """Dispatching to this backend is costing more time than the work
    it carries."""


# Worker-side: the state each initializer produced in this process,
# newest last. A run uses one initializer; a few are kept so that a
# worker process shared by consecutive runs does not thrash.
_STATES = OrderedDict()
_STATE_LIMIT = 4


def run_task(init_payload, task_payload, version):
    """
    Run one task. Called on a worker, in whatever process the cluster
    provides.

    Parameters
    ----------
    init_payload : bytes
        Pickle of `(initializer, initargs)`.
    task_payload : bytes
        Pickle of `(function, args)`; run as `function(state, *args)`.
    version : str
        The sender's `pymoso.__version__`.

    Returns
    -------
    bytes
        Pickle of `('ok', result, seconds)` or
        `('error', description, seconds)`, where `description` is what
        `pool._rebuild` takes and `seconds` is how long this call
        took here.
    """
    started = time.perf_counter()
    try:
        if version != __version__:
            raise VersionMismatch(
                'this task was sent by pymoso {0} and is running under pymoso {1}. '
                'The two must be the same version: a different one may compute '
                'different numbers without any error. Install the same pymoso '
                'on the workers as on the machine that started the run.'.format(version, __version__)
            )
        key = hashlib.sha256(init_payload).digest()
        if key in _STATES:
            _STATES.move_to_end(key)
            state = _STATES[key]
        else:
            initializer, initargs = pickle.loads(init_payload)
            state = initializer(*initargs) if initializer is not None else None
            _STATES[key] = state
            if len(_STATES) > _STATE_LIMIT:
                _STATES.popitem(last=False)
        func, args = pickle.loads(task_payload)
        message = ('ok', func(state, *args))
    except Exception as e:
        message = ('error', _describe(e))
    try:
        return pickle.dumps(message + (time.perf_counter() - started,))
    except Exception as e:
        # The result itself would not pickle.
        return pickle.dumps(('error', _describe(e), time.perf_counter() - started))


class RemotePool:
    """What `RemoteBackend.pool` returns: `pool.WorkerPool`'s shape,
    with no processes of its own."""

    def __init__(self, backend, initializer, initargs):
        self._backend = backend
        self._initializer = initializer
        self._initargs = tuple(initargs)
        self._init_payload = None

    def open(self):
        if self._init_payload is not None:
            raise RuntimeError('this pool is already open; close() it first')
        self._init_payload = pickle.dumps((self._initializer, self._initargs))
        return self

    def run(self, tasks):
        """
        As `pool.WorkerPool.run`, with two differences that follow
        from having no workers of its own: an initializer that fails
        is reported here, by the first task that needed it, not by
        `open()`; and when a task fails, the others of the same call
        still run to completion before the failure is raised.
        """
        if self._init_payload is None:
            raise RuntimeError('this pool is not open')
        payloads = [pickle.dumps(task) for task in tasks]
        if not payloads:
            return []
        started = time.perf_counter()
        answers = self._backend.dispatch(self._init_payload, payloads)
        elapsed = time.perf_counter() - started
        results, worked = [], 0.0
        failure = None
        for answer in answers:
            kind, value, seconds = pickle.loads(answer)
            worked += seconds
            if kind == 'ok':
                results.append(value)
            elif failure is None:
                failure = _rebuild(value)
        self._backend.account(elapsed, worked)
        if failure is not None:
            raise failure
        return results

    def close(self):
        self._init_payload = None

    def __enter__(self):
        if self._init_payload is None:
            self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


class RemoteBackend:
    """
    A backend (`pool.LocalBackend` describes the protocol) for workers
    that may share nothing with this process but an installed pymoso
    of the same version. Subclasses implement `dispatch`.

    Attributes
    ----------
    remote : bool
        True: classes from outside pymoso are sent by value
        (`executor.ClassRef`).
    jobs : int
        How many times `dispatch` has been called.
    dispatch_seconds : float
        Wall time spent in those calls, as seen from here.
    work_seconds : float
        Time the tasks themselves took, summed over tasks, as measured
        where they ran.
    """
    remote = True

    # Dispatches to look at before judging whether dispatch pays. One
    # call says little: the first also pays for starting the workers.
    WARN_AFTER = 20

    def __init__(self):
        self.jobs = 0
        self.dispatch_seconds = 0.0
        self.work_seconds = 0.0
        self._warned = False

    def pool(self, workers, initializer=None, initargs=()):
        """`workers` is not used: the cluster decides how many tasks
        run at once."""
        return RemotePool(self, initializer, initargs)

    def dispatch(self, init_payload, payloads):
        """
        Run `run_task(init_payload, payload, pymoso.__version__)` for
        every payload, anywhere, in any order, each at least once.

        Parameters
        ----------
        init_payload : bytes
        payloads : list of bytes

        Returns
        -------
        list of bytes
            What each call returned, in the order of `payloads`.
        """
        raise NotImplementedError

    def account(self, dispatch_seconds, work_seconds):
        """
        Record one dispatch, and say so -- once -- if dispatching is
        losing time.

        The tasks of a dispatch run concurrently, so a dispatch that
        pays takes less wall time here than its tasks took in total.
        When the wall time is *more* than that total, the same work
        run in this process, one task after another, would have
        finished sooner. That is the usual outcome of sending cheap
        replications to a cluster (docs/spark-backend.md), and nothing
        else would tell the user.
        """
        self.jobs += 1
        self.dispatch_seconds += dispatch_seconds
        self.work_seconds += work_seconds
        if self._warned or self.jobs < self.WARN_AFTER or self.dispatch_seconds <= self.work_seconds:
            return
        self._warned = True
        warnings.warn(
            'this backend is slower than no backend at all for this run so far: '
            '{0} dispatches took {1:.1f} s here to do {2:.1f} s of work ({3:.0f} ms '
            'of overhead per dispatch against {4:.0f} ms of work). Running without '
            'backend= would be faster. Sending replications to a cluster pays only '
            'when one replication costs roughly 100 ms or more, and then by a few '
            'times at most; see docs/spark-backend.md.'.format(
                self.jobs, self.dispatch_seconds, self.work_seconds,
                (self.dispatch_seconds - self.work_seconds) / self.jobs * 1e3,
                self.work_seconds / self.jobs * 1e3,
            ),
            SlowDispatchWarning, stacklevel=2,
        )
