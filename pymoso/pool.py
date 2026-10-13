"""
The one worker-process lifecycle PyMOSO has.

`WorkerPool` owns a fixed set of worker processes for the duration of a
`with` block and runs tasks on them. Both parallel features sit on it:
`--simpar` (replication blocks, through `executor.PoolExecutor`) and
`--proc` (whole sample paths and metric computations,
`chnutils.testsolve`/`par_diff`). It replaces three older mechanisms --
a raw `Process`/`Queue` pair in `Oracle.set_simpar`, and two
`multiprocessing.Pool`s in `chnutils` -- each of which had its own
teardown and its own way of hanging.

What crosses the process boundary is data. A worker is started with an
`initializer` and its arguments, runs it once, and keeps what it
returns as its *state*; a task is `(function, args)` and runs as
`function(state, *args)`. The initializer, its arguments, every task
and every result are pickled -- always, under every start method, so a
payload that would only work by `fork` inheritance fails on Linux the
same way it would on macOS or Windows, and fails in `open()` rather
than later.

Built on `multiprocessing.Process` with one pipe per worker, not on
`concurrent.futures.ProcessPoolExecutor` or `multiprocessing.Pool`:
tearing down while a worker is in the middle of a long `g()` means
killing that worker, which `ProcessPoolExecutor` has no public way to
do before Python 3.14; and `multiprocessing.Pool` waits forever on a
worker that died.

The three failures, each of which has been a hang in this project:

- **A task raises** (KNOWN_ISSUES.md issue 15). The worker catches the
  exception and sends it back; `run` raises it in the caller, as that
  exception, with the worker's traceback attached as its cause. If
  several tasks of one `run` call raise, the earliest in submission
  order is the one raised, so a parallel run reports the same error a
  serial one would.
- **A worker dies** (killed, segfault, `os._exit`). Its process
  sentinel fires; `run` raises `WorkerCrashed` naming the task, and
  the pool refuses further work.
- **The parent is killed** (KNOWN_ISSUES.md issue 8). No parent-side
  cleanup can run. Each worker blocks reading its own pipe, and reads
  end-of-file once every copy of the parent's end is closed -- that
  is, once the parent is gone -- and exits. A worker that is in the
  middle of a task at that moment finishes the task first and exits
  when it fails to send the result. Under the `fork` start method a
  child inherits the parent's ends of every pipe that exists when it
  is forked, its own included, which would keep them all open after
  the parent's death; `_worker_main` closes them first thing
  (`_PARENT_ENDS`).
"""
import multiprocessing
import pickle
import signal
import traceback
from collections import deque
from multiprocessing import connection


class WorkerError(Exception):
    """A task raised an exception in a worker that could not be brought
    back to the caller as itself (it does not pickle, or its class does
    not exist here under the same name). The message carries the
    original type name and text; the cause carries its traceback."""


class WorkerCrashed(Exception):
    """A worker process died without reporting a result."""


class RemoteTraceback(Exception):
    """The traceback text of an exception raised in a worker, attached
    as the `__cause__` of what `WorkerPool.run` raises."""

    def __init__(self, text):
        super().__init__(text)
        self.text = text

    def __str__(self):
        return '\n"""\n{0}"""'.format(self.text)


# The parent's end of every live pool's pipes, in this process. In a
# forked child this is an inherited copy naming descriptors the child
# must not hold open; in a spawned or forkserver child it is empty.
_PARENT_ENDS = set()

_JOIN_TIMEOUT = 5.0


def _describe(exc):
    """An exception as something that always pickles: its own pickle
    when it has one, plus enough text to stand in for it when it does
    not or when the caller cannot load it."""
    try:
        payload = pickle.dumps(exc)
    except Exception:
        payload = None
    text = ''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    return payload, type(exc).__name__, str(exc), text


def _rebuild(description):
    payload, name, message, text = description
    exc = None
    if payload is not None:
        try:
            exc = pickle.loads(payload)
        except Exception:
            exc = None
    if not isinstance(exc, BaseException):
        exc = WorkerError('{0}: {1}'.format(name, message))
    exc.__cause__ = RemoteTraceback(text)
    return exc


def _worker_main(conn, payload):
    for other in list(_PARENT_ENDS):
        try:
            other.close()
        except OSError:
            pass
    _PARENT_ENDS.clear()
    # Ctrl-C reaches every process in the terminal's foreground group.
    # The parent handles it, by tearing the pool down; a worker that
    # also raised KeyboardInterrupt would only add noise.
    try:
        signal.signal(signal.SIGINT, signal.SIG_IGN)
    except (ValueError, OSError):
        pass
    try:
        try:
            initializer, initargs = pickle.loads(payload)
            state = initializer(*initargs) if initializer is not None else None
        except BaseException as e:
            conn.send(('init_error', _describe(e)))
            return
        conn.send(('ready', None))
        while True:
            task = conn.recv()
            if task is None:
                return
            func, args = task
            try:
                message = ('ok', func(state, *args))
            except Exception as e:
                message = ('error', _describe(e))
            try:
                conn.send(message)
            except (pickle.PicklingError, TypeError, AttributeError) as e:
                # The result itself would not pickle. Nothing was
                # written to the pipe; report that instead.
                conn.send(('error', _describe(e)))
    except (EOFError, OSError):
        # The parent's end is closed: the pool was torn down, or the
        # parent is gone. Either way there is nobody to work for.
        return
    finally:
        conn.close()


class _Worker:
    def __init__(self, process, conn):
        self.process = process
        self.conn = conn


class WorkerPool:
    """
    A fixed set of worker processes, owned by whoever opens it.

    `with WorkerPool(4, initializer, initargs) as pool:` starts the
    workers and waits until each has run its initializer; leaving the
    block -- by returning, by an exception, by KeyboardInterrupt --
    stops them. `open()`/`close()` are the same thing spelled out;
    `close()` is safe on a pool that is not open.

    Parameters
    ----------
    workers : int
        At least 1.
    initializer : callable or None
        Top-level, importable function. Run once in each worker; its
        return value is that worker's state.
    initargs : tuple
    context : multiprocessing context or None
        Defaults to the platform's default start method.
    """

    def __init__(self, workers, initializer=None, initargs=(), context=None):
        if workers < 1:
            raise ValueError('a pool needs at least one worker, got {0}'.format(workers))
        self.workers = workers
        self._initializer = initializer
        self._initargs = tuple(initargs)
        self._context = context
        self._workers = []
        self._open = False
        self._broken = None

    def open(self):
        """
        Start the workers and wait for every one to finish its
        initializer.

        Returns
        -------
        WorkerPool
            self.

        Raises
        ------
        Exception
            Whatever the initializer raised in a worker, or pickling
            the initializer and its arguments raised here. No workers
            are left running.
        WorkerCrashed
            A worker died during start-up.
        """
        if self._open:
            raise RuntimeError('this pool is already open; close() it first')
        # Pickled here whatever the start method: under fork nothing
        # else would check that this payload can reach a worker.
        payload = pickle.dumps((self._initializer, self._initargs))
        ctx = self._context if self._context is not None else multiprocessing.get_context()
        self._open = True
        self._broken = None
        try:
            for _ in range(self.workers):
                parent_end, child_end = ctx.Pipe(duplex=True)
                _PARENT_ENDS.add(parent_end)
                process = ctx.Process(target=_worker_main, args=(child_end, payload), daemon=True)
                self._workers.append(_Worker(process, parent_end))
                try:
                    process.start()
                finally:
                    child_end.close()
            for index, worker in enumerate(self._workers):
                kind, value = self._receive(worker, 'starting up')
                if kind == 'init_error':
                    raise _rebuild(value)
        except BaseException:
            self._broken = 'it failed to start'
            self.close()
            raise
        return self

    def _receive(self, worker, doing):
        """One message from `worker`, or WorkerCrashed if it died."""
        while True:
            ready = connection.wait([worker.conn, worker.process.sentinel])
            if worker.conn in ready:
                try:
                    return worker.conn.recv()
                except (EOFError, OSError):
                    pass
            elif worker.process.sentinel not in ready:
                continue
            raise self._crashed(worker, doing)

    def _crashed(self, worker, doing):
        worker.process.join(_JOIN_TIMEOUT)
        return WorkerCrashed(
            'a worker process (pid {0}) died with exit code {1} while {2}. '
            'Nothing it was working on can be reported; a crash in the '
            'simulation itself (a segfault in an extension, the process '
            'being killed for memory) is the usual cause.'.format(
                worker.process.pid, worker.process.exitcode, doing
            )
        )

    def run(self, tasks):
        """
        Run every task and return their results in order.

        Parameters
        ----------
        tasks : sequence of (callable, tuple)
            Each runs in a worker as `callable(state, *args)`. The
            callable must be a top-level, importable function.

        Returns
        -------
        list

        Raises
        ------
        Exception
            What the earliest failing task raised. Tasks after the
            first failure seen are not started; ones already running
            are waited for and their results discarded, so the pool
            is still usable afterwards.
        WorkerCrashed
            A worker died. The pool is unusable afterwards.
        """
        if not self._open:
            raise RuntimeError('this pool is not open')
        if self._broken is not None:
            raise RuntimeError('this pool cannot run anything more: {0}'.format(self._broken))
        tasks = list(tasks)
        results = [None] * len(tasks)
        errors = {}
        pending = deque(enumerate(tasks))
        idle = list(self._workers)
        busy = {}
        # Anything that leaves this method early -- a crash, Ctrl-C --
        # leaves workers mid-task with results nobody will read.
        self._broken = 'an earlier run() was interrupted'
        while pending or busy:
            while pending and idle and not errors:
                index, task = pending.popleft()
                worker = idle.pop()
                try:
                    worker.conn.send(task)
                except (pickle.PicklingError, TypeError, AttributeError) as e:
                    idle.append(worker)
                    errors[index] = e
                    break
                except OSError:
                    self._broken = 'a worker died'
                    raise self._crashed(worker, 'being sent task {0}'.format(index))
                busy[worker.conn] = (worker, index)
            if errors:
                pending.clear()
            if not busy:
                break
            waiting = list(busy) + [worker.process.sentinel for worker, _ in busy.values()]
            ready = connection.wait(waiting)
            for conn in [c for c in ready if c in busy]:
                worker, index = busy[conn]
                try:
                    kind, value = conn.recv()
                except (EOFError, OSError):
                    self._broken = 'a worker died'
                    raise self._crashed(worker, 'running task {0}'.format(index))
                del busy[conn]
                idle.append(worker)
                if kind == 'ok':
                    results[index] = value
                else:
                    errors[index] = _rebuild(value)
            for worker, index in list(busy.values()):
                if worker.process.sentinel in ready and not worker.conn.poll():
                    self._broken = 'a worker died'
                    raise self._crashed(worker, 'running task {0}'.format(index))
        self._broken = None
        if errors:
            raise errors[min(errors)]
        return results

    def close(self):
        """Stop every worker. Idle workers of a healthy pool are asked
        to finish and exit; anything else is terminated. Returns once
        no worker process is left."""
        workers, self._workers = self._workers, []
        graceful = self._open and self._broken is None
        self._open = False
        for worker in workers:
            if graceful:
                try:
                    worker.conn.send(None)
                except (OSError, ValueError):
                    pass
        for worker in workers:
            process = worker.process
            if process.pid is not None:
                if graceful:
                    process.join(_JOIN_TIMEOUT)
                if process.is_alive():
                    process.terminate()
                    process.join(_JOIN_TIMEOUT)
                if process.is_alive():
                    process.kill()
                    process.join()
            _PARENT_ENDS.discard(worker.conn)
            try:
                worker.conn.close()
            except OSError:
                pass

    def __enter__(self):
        if not self._open:
            self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            # Leaving on an exception: do not wait for anything.
            self._broken = self._broken or 'it is being torn down'
        self.close()
        return False


class LocalBackend:
    """
    Where pooled work runs, when nothing else is asked for: worker
    processes on this machine (`WorkerPool`).

    A *backend* is the one thing `--simpar`, `--proc` and metric
    computation need from wherever their work runs, and what
    `solve(backend=...)`, `testsolve(backend=...)` and
    `par_diff(backend=...)` accept. It has:

    - `remote` : bool. False when its workers share this machine's
      Python environment and can import whatever this process can.
      True when they may not -- another machine, another environment --
      in which case classes are sent to it by value wherever they are
      not part of pymoso itself (`executor.ClassRef`).
    - `pool(workers, initializer, initargs)`, returning an object with
      `WorkerPool`'s shape and `WorkerPool.run`'s contract: `open()`
      returning itself, `run(tasks)`, `close()`, and use as a context
      manager. `initializer(*initargs)` runs once wherever tasks run
      and its return value is passed to every task as its first
      argument; a task is `(function, args)`; results come back in
      order; if tasks raise, `run` raises what the earliest of them
      raised, as that exception. `workers` is how many tasks may run
      at once; a backend that schedules for itself may ignore it.

    Parameters
    ----------
    context : multiprocessing context or None
        Defaults to the platform's default start method.
    """
    remote = False

    def __init__(self, context=None):
        self._context = context

    def pool(self, workers, initializer=None, initargs=()):
        return WorkerPool(workers, initializer, initargs, self._context)
