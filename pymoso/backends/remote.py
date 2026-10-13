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
from collections import OrderedDict

from .. import __version__
from ..pool import _describe, _rebuild


class VersionMismatch(RuntimeError):
    """The pymoso that ran a task is not the pymoso that sent it."""


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
        Pickle of `('ok', result)` or `('error', description)`, where
        `description` is what `pool._rebuild` takes.
    """
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
        return pickle.dumps(message)
    except Exception as e:
        # The result itself would not pickle.
        return pickle.dumps(('error', _describe(e)))


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
        answers = self._backend.dispatch(self._init_payload, payloads)
        results = []
        failure = None
        for answer in answers:
            kind, value = pickle.loads(answer)
            if kind == 'ok':
                results.append(value)
            elif failure is None:
                failure = _rebuild(value)
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

    A backend does not time what it dispatches or pass judgement on
    whether dispatching was worth it. Whether a cluster pays for a
    given simulation is the user's question to ask, deliberately.
    """
    remote = True

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
