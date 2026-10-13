"""
The executor interface: simulation work expressed as data, run by a
pluggable backend with one lifecycle.

Since the RNG redesign (docs/rng-interface-design.md), a replication is
fully described by values: which point, and which coordinate
`(root, stream, offset)` its random-number stream starts at. Nothing
about it depends on an Oracle's mutable state or on the order other
replications ran in. This module is the seam that follows from that:

- `ReplicationBlock` is the unit of work -- `count` replications of one
  point, `stride` apart, starting at a coordinate. Plain, immutable,
  picklable data. No Oracle, no stream object, no seed derived from
  object state.
- A `ProblemHandle` is how a backend gets something to simulate with.
  The interface never takes a problem class or an Oracle instance
  directly, only a handle, so how a problem reaches a worker (by
  reference, as a source bundle, or pickled by value) is a property of
  the handle, not of the interface.
- An `Executor` runs blocks: `open(problem, generator)`, `run(blocks)`,
  `close()`, usable as a context manager. `run` takes a *list* of
  blocks and returns one list of `Replication` results per block, in
  order.

Division of labour with `chnbase.Oracle`. The caller computes each
block's `(stream, offset)` -- cheap integer arithmetic, and the place
where the overflow checks, the high-water mark and the point-code
collision record live. The backend turns `(root, stream, offset)` into
an actual stream. For a process-pool backend that moves the expensive
jump (~1.5-2 ms, docs/hit-cost-baseline.md) out of the serial parent.

Why `run` takes a list (docs/simpar-ceiling.md). `Oracle.hit()` passes
one block. What bounds parallel speedup today is that parallelism is
confined to one `hit()` call; a caller that submits several points at
once is the fix, and needs no change here.

Two backends. `SerialExecutor` runs everything in the calling process,
bit for bit what `Oracle.hit()` did inline before this module existed.
`PoolExecutor` runs the same blocks on worker processes (`--simpar`),
each worker holding a `SerialExecutor` of its own, on the one process
lifecycle the package has (pymoso/pool.py).

Whole sample paths (`--proc`) are not replication blocks and do not go
through `Executor.run`: a path carries a solver and a tester, returns a
result dict, and runs a `SerialExecutor` of its own inside its worker.
They are a second kind of job on the same pool -- see
`chnutils.testsolve`. What the two share is the pool and `ClassRef`,
the transportable form of a class.
"""
import inspect
import os
import pickle
import sys
import types
from collections import OrderedDict
from dataclasses import dataclass
from typing import NamedTuple

from .pool import LocalBackend
from .prng import registry
from .prng.base import ReplicationDrawOverflow, ensure_random_compatible


# ---------------------------------------------------------------------------
# Work, and its result, as data
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ReplicationBlock:
    """
    `count` replications of the point `x`. Replication i draws from the
    stream at `(root, stream, offset + i*stride)`.

    Attributes
    ----------
    x : tuple of int
        Handed to `g()` unchanged.
    root : tuple of int
        The oracle role's root seed, in the selected generator's own
        shape -- what `Stream.root_seed()` returns.
    stream : int
        Non-negative.
    offset : int
        Non-negative. The first replication's offset within `stream`.
    stride : int
        Positive. The distance between consecutive replications, and
        each replication's reserve: the number of raw values its `g()`
        may draw before reaching the next replication's start.
    count : int
        At least 1.
    """
    x: tuple
    root: tuple
    stream: int
    offset: int
    stride: int
    count: int


class Replication(NamedTuple):
    """
    One replication's outcome.

    Attributes
    ----------
    isfeas : bool
    objectives : tuple of float
        Whatever `g()` returned as its second value.
    raw_consumed : int
        How many raw values the replication drew from its stream.
    """
    isfeas: bool
    objectives: tuple
    raw_consumed: int


# ---------------------------------------------------------------------------
# Problem handles: how a backend gets something to simulate with
# ---------------------------------------------------------------------------

def simulate_with_class(orccls, x, stream):
    """
    One replication of `x` from a problem *class*: construct an
    instance over `stream`, then call its `g()`. This is what a worker
    that was handed a class (not a live instance) does per replication
    -- the recipe `--simpar` workers have always used.

    Parameters
    ----------
    orccls : Oracle class
    x : tuple of int
    stream : Stream
        Unwrapped: the instance's own `set_crnflag()` needs the real
        backend stream. `g()` is handed the random.Random-compatible
        view of the same stream (docs/rng-interface-design.md §3.6).

    Returns
    -------
    isfeas : bool
    objvals : tuple of float
    """
    orc = orccls(stream)
    orc.set_crnflag(False)
    return orc.g(x, ensure_random_compatible(stream))


class _InstanceSimulator:
    """Calls a live instance's `g()`. A class, not a closure, so it
    pickles wherever the instance does; `g` is looked up at call time,
    so replacing `instance.g` after the executor opened is honoured."""

    def __init__(self, instance):
        self._instance = instance

    def __call__(self, x, stream):
        return self._instance.g(x, ensure_random_compatible(stream))


class _ClassSimulator:
    def __init__(self, orccls):
        self._orccls = orccls

    def __call__(self, x, stream):
        return simulate_with_class(self._orccls, x, stream)


class ProblemHandle:
    """
    What an executor is opened with instead of a problem class or an
    Oracle instance.

    Attributes
    ----------
    transportable : bool
        Whether this handle may be sent to another process. A backend
        that runs work elsewhere must refuse one that is not.

    Subclasses implement `simulator()`.

    Correction (Phase 4). This docstring used to say that pickling a
    class by value, for a problem defined in a notebook cell, would be
    a further subclass here. It is not: it is a third form of
    `ClassRef`. The earlier plan was made when a problem was the only
    thing that travelled; since Phase 3 a tester and a solver travel
    too, as `ClassRef`s and not as handles, and a by-value handle
    would have left a notebook's tester and solver unable to travel.
    The executor interface is unchanged either way.
    """
    transportable = False

    def simulator(self):
        """
        Returns
        -------
        callable
            `simulate(x, stream) -> (isfeas, objvals)`, where `stream`
            is the selected generator's own, unwrapped stream object.
        """
        raise NotImplementedError


class InProcessHandle(ProblemHandle):
    """
    A live Oracle instance, simulated in this process by calling its
    own `g()`. Whatever state the instance carries is used as-is --
    which is what `Oracle.hit()` has always done serially. Not
    transportable: it stands for *this* object, here.
    """
    transportable = False

    def __init__(self, instance):
        self._instance = instance

    def simulator(self):
        return _InstanceSimulator(self._instance)


class ClassRef:
    """
    A class in a form that can be sent to a worker process and turned
    back into the class there: the class itself when a fresh process
    can import it, a source bundle when it was loaded from a
    user-supplied file, and the class pickled by value (cloudpickle,
    the `notebook` extra) when it is neither -- see
    `build_transport_descriptor`. Problems, solvers and testers all
    travel this way.

    Parameters
    ----------
    cls : class
    remote : bool
        Whether the worker may be somewhere that cannot import what
        this process can (`pool.LocalBackend` describes the flag).
        Default False.

    Raises
    ------
    ValueError
        `cls` cannot be transported: it has no source file (defined in
        a REPL or notebook) or cannot be found again by name (defined
        inside a function), and cloudpickle is not installed or cannot
        pickle it. Raised here, in the parent, whatever the start
        method -- `fork` would carry such a class across by
        inheritance, and the same code would then fail on macOS, on
        Windows, and on Linux from Python 3.14.
    """

    def __init__(self, cls, remote=False):
        self.descriptor = build_transport_descriptor(cls, remote=remote)
        self.name = cls.__name__

    def load(self):
        """The class, reconstructed if it travelled as a source
        bundle."""
        return reconstruct_transport_descriptor(self.descriptor)


class ClassHandle(ProblemHandle):
    """
    A problem class, in transportable form (`ClassRef`). Each
    replication constructs a fresh instance (`simulate_with_class`).

    Parameters
    ----------
    orccls : Oracle class
    remote : bool
        As for `ClassRef`. Default False.

    Raises
    ------
    ValueError
        `orccls` cannot be transported -- see `ClassRef`.
    """
    transportable = True

    def __init__(self, orccls, remote=False):
        self._ref = ClassRef(orccls, remote=remote)

    @property
    def descriptor(self):
        return self._ref.descriptor

    def load(self):
        """The problem class, reconstructed if it travelled as a
        source bundle."""
        return self._ref.load()

    def simulator(self):
        return _ClassSimulator(self.load())


def build_transport_descriptor(cls, remote=False):
    """
    Build whatever a worker process needs to reconstruct cls. It is
    sent once per worker, when the pool opens, not once per job.

    A class loaded normally (built-in problems/testers, or anything
    else genuinely importable) is returned as-is: it already pickles
    by reference correctly regardless of multiprocessing start method,
    since a fresh worker can just `import` it like any other
    dependency.

    A class loaded from a user-supplied file
    (commands/basecomm.load_user_module marks its module
    __pymoso_dynamic__ = True) has no real module backing it -- nothing
    a worker can `import` by name, since the name only exists because
    the CLI process put it in sys.modules. For that case, this returns
    a source-bundle descriptor instead: every .py file's source text in
    cls's directory, shipped as plain strings -- always picklable
    regardless of start method, since no code or class objects are
    involved -- reconstructed fresh in the worker
    (reconstruct_transport_descriptor).

    Ships the whole directory rather than analyzing cls's file for
    which siblings it actually imports -- a real constraint, not an
    oversight: a custom problem/tester's sibling imports must live flat
    in one directory (matching commands/basecomm.load_user_module,
    which only puts that one directory on sys.path -- a package-style
    layout with subdirectories, or `from .sibling import x`, isn't
    supported by either).

    A class that is neither -- defined interactively, in a notebook
    cell or a REPL, so that it has no source file; or inside a
    function, so that it cannot be found again by name -- is pickled
    *by value* with cloudpickle when cloudpickle is installed (the
    `notebook` extra): the class's own code travels in the payload,
    with whatever functions and constants of its defining namespace it
    uses. What does not travel by value is any module the class
    imports; those are imported again in the worker, by name.

    With `remote=True` the worker may be on another machine, where
    "this process can import it" says nothing. Then only pymoso's own
    classes go by reference -- pymoso has to be installed there
    anyway -- and a class from any other module goes by value, its
    module's own functions and classes with it. (A source bundle is
    text and travels anywhere; it is unchanged.)

    Parameters
    ----------
    cls : Oracle class
    remote : bool
        Default False.

    Returns
    -------
    cls, unchanged; a dict source-bundle descriptor (keys `files`,
    `entry`, `class_name`); or a dict by-value descriptor (keys
    `by_value`, `class_name`)

    Raises
    ------
    ValueError
        cls has no locatable source at all (defined interactively, not
        loaded from a .py file), or does not pickle by reference
        (defined inside a function), or -- for a remote worker -- is
        not part of pymoso; and cloudpickle is not installed, or
        cannot pickle it. Raised here, before any worker exists,
        rather than left to surface as a hang once a job is
        dispatched.
    """
    module = sys.modules.get(cls.__module__)
    if module is not None and getattr(module, '__pymoso_dynamic__', False):
        return _build_source_bundle(cls, module)
    if remote:
        if _is_pymoso_class(cls):
            return cls
        descriptor = _build_by_value(cls, with_module=True)
        if descriptor is None:
            raise ValueError(
                f"{cls.__name__} cannot be sent to a remote worker: it is "
                "not part of pymoso, so the worker's machine may be unable "
                "to import it, and sending it by value needs cloudpickle, "
                "which is not installed. " + _NOTEBOOK_EXTRA
            )
        return descriptor
    try:
        inspect.getfile(cls)
    except (TypeError, OSError) as e:
        descriptor = _build_by_value(cls)
        if descriptor is not None:
            return descriptor
        raise ValueError(
            f"{cls.__name__} has no locatable source file, so it cannot be "
            "sent to a worker process as it is. This is the case for a "
            "class defined interactively, in a notebook cell or a REPL. "
            + _NOTEBOOK_EXTRA + " " + _OTHER_WAYS
        ) from e
    try:
        pickle.dumps(cls)
    except Exception as e:
        descriptor = _build_by_value(cls)
        if descriptor is not None:
            return descriptor
        raise ValueError(
            f"{cls.__name__} cannot be sent to a worker process: a worker "
            "finds a class again by its module and name, and this one "
            f"cannot be found that way ({e}). This is the case for a class "
            "defined inside a function, or in a module that was loaded "
            "without being made importable. " + _NOTEBOOK_EXTRA + " "
            + _OTHER_WAYS
        ) from e
    return cls


# The remedy that works wherever the class was defined comes first.
# "Define it in a .py file" used to be the advice, and it is the wrong
# advice in a notebook -- most of all a hosted one.
_NOTEBOOK_EXTRA = (
    "Install cloudpickle and it is sent by value: `pip install "
    "pymoso[notebook]`, or `%pip install pymoso[notebook]` in a notebook."
)
_OTHER_WAYS = (
    "Outside a notebook, defining it at the top level of a .py file "
    "works too. Or run with simpar and proc left at 1, which needs no "
    "worker process."
)


def _is_pymoso_class(cls):
    """Whether a worker that has pymoso installed, and nothing else of
    this process's, can find `cls` by name."""
    if cls.__module__ != 'pymoso' and not cls.__module__.startswith('pymoso.'):
        return False
    try:
        return pickle.loads(pickle.dumps(cls)) is cls
    except Exception:
        return False


def _build_by_value(cls, with_module=False):
    """
    `cls` pickled by value, or None when cloudpickle is not installed.

    Parameters
    ----------
    cls : class
    with_module : bool
        Also send by value everything else `cls` uses from its own
        module, where cloudpickle would otherwise leave a reference to
        a module it sees is importable here.

    Raises
    ------
    ValueError
        cloudpickle is installed and cannot pickle `cls`.
    """
    try:
        import cloudpickle
    except ImportError:
        return None
    module = sys.modules.get(cls.__module__)
    registered = False
    # Not if the user registered it themselves: undoing ours would
    # undo theirs.
    if with_module and module is not None and module.__name__ not in cloudpickle.list_registry_pickle_by_value():
        cloudpickle.register_pickle_by_value(module)
        registered = True
    try:
        payload = cloudpickle.dumps(cls)
    except Exception as e:
        raise ValueError(
            f"{cls.__name__} cannot be sent to a worker process: it has to "
            f"be pickled by value, and that failed ({type(e).__name__}: {e}). "
            "Something it uses from the namespace it was defined in -- an "
            "open file, a lock, a database or Spark session -- cannot be "
            "pickled. Create such things inside g(), not outside the class."
        ) from e
    finally:
        if registered:
            cloudpickle.unregister_pickle_by_value(module)
    return {'by_value': payload, 'class_name': cls.__name__}


def _build_source_bundle(cls, module):
    filepath = module.__file__
    directory = os.path.dirname(os.path.abspath(filepath))
    entry_name = os.path.splitext(os.path.basename(filepath))[0]
    files = {}
    for fname in sorted(os.listdir(directory)):
        if fname.endswith('.py'):
            with open(os.path.join(directory, fname)) as f:
                files[fname[:-3]] = f.read()
    return {'files': files, 'entry': entry_name, 'class_name': cls.__name__}


def reconstruct_transport_descriptor(descriptor):
    """
    The worker side of build_transport_descriptor: turns a
    source-bundle dict back into a class, or passes an already-real
    class through unchanged. Pure data in (for the bundle case) -- no
    pickled code or class objects -- so this works identically
    regardless of multiprocessing start method.

    Execution order isn't assumed (e.g. "entry last"): the bundled
    directory can contain files unrelated to the entry point that have
    their own cross-imports (confirmed directly -- pymoso/examples/
    ships both myproblem.py and mytester.py, and mytester.py imports
    myproblem.py; a real --simpar run on a fixture built from that
    directory bundles both even though only one is the entry point).
    Instead, this retries whichever files raise ImportError against
    modules not populated yet, until a full pass makes no further
    progress -- a simple fixed-point resolution that works for any
    acyclic dependency order among the bundled files without having to
    guess it upfront.

    A by-value descriptor is unpickled. That needs cloudpickle
    installed where this runs, and every module the class imports.

    Parameters
    ----------
    descriptor : Oracle class, or dict as built by
        build_transport_descriptor

    Returns
    -------
    Oracle class

    Raises
    ------
    ImportError
        The bundled files' cross-imports can't be resolved in any
        order (a genuine circular import among them, or one of them
        imports something this bundle doesn't include).
    """
    if not isinstance(descriptor, dict):
        return descriptor
    if 'by_value' in descriptor:
        # A cloudpickle payload is an ordinary pickle; reading it needs
        # cloudpickle importable here, since it names cloudpickle's own
        # reconstruction functions. cloudpickle returns the same class
        # object each time one process loads the same class.
        return pickle.loads(descriptor['by_value'])
    files = descriptor['files']
    entry = descriptor['entry']
    modules = {}
    for name in files:
        mod = types.ModuleType(name)
        mod.__file__ = f'<transported:{name}.py>'
        modules[name] = mod
        sys.modules[name] = mod
    pending = dict(files)
    last_errors = {}
    while pending:
        progressed = False
        for name in sorted(pending):
            try:
                code = compile(pending[name], f'<transported:{name}.py>', 'exec')
                exec(code, modules[name].__dict__)
            except ImportError as e:
                last_errors[name] = e
                continue
            del pending[name]
            progressed = True
        if not progressed:
            raise ImportError(
                f"Could not resolve import order for bundled file(s) "
                f"{sorted(pending)} while reconstructing a --simpar transport "
                f"descriptor -- a circular import among the bundled files, or "
                f"one of them imports something outside the bundle. Last "
                f"error(s) seen: {last_errors}"
            )
    return getattr(modules[entry], descriptor['class_name'])


# ---------------------------------------------------------------------------
# The executor
# ---------------------------------------------------------------------------

class Executor:
    """
    The interface every backend implements.

    Lifecycle: `open(problem, generator)` once, any number of `run`
    calls, `close()` once. `close()` is safe to call on an executor
    that is not open. An executor is a context manager that closes
    itself; `open` returns the executor so that
    `with SerialExecutor().open(handle, 'mrg32k3a') as ex:` works.

    Contract for `run`:

    - It returns one list per block, in the order given, each holding
      that block's `count` `Replication` results in replication order.
    - Results do not depend on how blocks are grouped into calls, on
      the order of blocks within a call, or on which backend runs them:
      a replication's outcome is a function of its problem, its point
      and its coordinate.
    - An exception raised by a replication's `g()` is raised by `run`
      in the caller, as that exception -- wherever the replication
      actually ran. A backend may not swallow one or wait forever on a
      worker that died with one (KNOWN_ISSUES.md issue 15 is what
      happens otherwise).
    - A replication that draws more than `stride` raw values raises
      `ReplicationDrawOverflow` the same way.
    """

    def open(self, problem, generator):
        """
        Parameters
        ----------
        problem : ProblemHandle
        generator : str
            A registered generator name (pymoso.prng.registry).

        Returns
        -------
        Executor
            self.
        """
        raise NotImplementedError

    def run(self, blocks):
        """
        Parameters
        ----------
        blocks : sequence of ReplicationBlock

        Returns
        -------
        list of list of Replication
        """
        raise NotImplementedError

    def close(self):
        raise NotImplementedError

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


class SerialExecutor(Executor):
    """
    Runs every replication in the calling process, in order.

    **The base-stream cache is the performance of `--crn`, not an
    optimization to simplify away.** Reaching `(root, stream, offset)`
    takes two steps: `stream_at(root, stream, 0)`, a full jump from the
    root (~1.5-2 ms for MRG32k3a), then `advance(offset)`. The first
    result is cached per `(root, stream)`. Every CRN block in an RA
    iteration has the same `stream` and starts at offset 0, so one jump
    serves the whole iteration and a CRN `hit()` costs ~20 microseconds;
    without the cache every one of them pays the full jump, about 80x
    more. Measured: docs/hit-cost-baseline.md, regenerated by
    docs/bench_hit_cost.py, and pinned by
    tests/test_oracle_coordinate_migration.py's stream_at count.

    A block on the default branch has a point-specific offset, so it
    still pays one general jump per block (the `advance(offset)`), as
    it did before this class existed. A cached base stream is never
    drawn from: every stream handed to `g()` is an `advance()`d copy.
    """

    # (root, stream) pairs kept. An RA iteration uses one stream for
    # its default/CRN blocks; a solver using sync= alternates with a
    # second. A handful covers both without growing over a long run.
    _BASE_CACHE_SIZE = 4

    def __init__(self):
        self._simulate = None
        # The generator's registered *name*, not its module: a module
        # cannot be pickled, and an Oracle that has opened its executor
        # still has to pickle (the same lesson as Oracle._backend_name).
        self._generator = None
        self._bases = OrderedDict()

    @property
    def _backend(self):
        if self._generator is None:
            return None
        return registry.GENERATORS[self._generator]

    def open(self, problem, generator):
        if self._simulate is not None:
            raise RuntimeError('this executor is already open; close() it first')
        registry.get_generator(generator)      # raises for an unknown name
        self._generator = generator
        self._simulate = problem.simulator()
        return self

    def close(self):
        self._simulate = None
        self._generator = None
        self._bases.clear()

    def _base_stream(self, root, stream):
        key = (root, stream)
        base = self._bases.get(key)
        if base is None:
            base = self._backend.stream_at(root, stream, 0)
            self._bases[key] = base
            if len(self._bases) > self._BASE_CACHE_SIZE:
                self._bases.popitem(last=False)
        else:
            self._bases.move_to_end(key)
        return base

    def streams(self, block):
        """
        The fresh stream each of `block`'s replications starts from, in
        replication order -- the "turn a coordinate into a stream" half
        of running a block, without the simulation.

        Separate from `run` so that the coordinate cost can be timed
        on its own (docs/bench_simpar_ceiling.py).

        Parameters
        ----------
        block : ReplicationBlock

        Returns
        -------
        list of Stream
        """
        if self._generator is None:
            raise RuntimeError('this executor is not open')
        streams = [self._base_stream(block.root, block.stream).advance(block.offset)]
        for _ in range(block.count - 1):
            streams.append(streams[-1].advance(block.stride))
        return streams

    def run(self, blocks):
        results = []
        for block in blocks:
            outcomes = []
            for stream in self.streams(block):
                isfeas, objectives = self._simulate(block.x, stream)
                drawn = stream.raw_consumed()
                if drawn > block.stride:
                    raise ReplicationDrawOverflow(
                        'a single replication of x={0} drew {1} raw values, '
                        'exceeding its reserved block of {2} '
                        '-- it overran the next replication\'s starting position. '
                        'See docs/rng-interface-design.md §3.4.'.format(block.x, drawn, block.stride)
                    )
                outcomes.append(Replication(isfeas, objectives, drawn))
            results.append(outcomes)
        return results


def _open_worker_executor(problem, generator):
    """A pool worker's state: a SerialExecutor of its own, opened over
    the transported problem. Its base-stream cache is per worker, which
    is what keeps --crn blocks cheap there too."""
    return SerialExecutor().open(problem, generator)


def _run_blocks(executor, blocks):
    return executor.run(blocks)


def split_blocks(blocks, parts):
    """
    Divide `blocks` into at most `parts` chunks of nearly equal
    replication count, cutting a block wherever a chunk boundary falls
    inside it.

    A block of `count` replications starting at `offset` is the same
    work as its first `k` replications followed by a block of `count -
    k` starting at `offset + k*stride`: a replication's stream is a
    function of its coordinate alone. That is what lets the unit of
    parallel work be the replication, not the hit() call or the point.

    Parameters
    ----------
    blocks : sequence of ReplicationBlock
    parts : int
        At least 1.

    Returns
    -------
    chunks : list of list of ReplicationBlock
        Non-empty chunks, in order: concatenated, they are `blocks`
        with some blocks cut into consecutive pieces.
    owners : list of list of int
        `owners[c][j]` is the index in `blocks` that `chunks[c][j]` is
        a piece of.
    """
    total = sum(block.count for block in blocks)
    chunks, owners = [], []
    if total == 0:
        return chunks, owners
    parts = min(parts, total)
    taken = 0                       # replications placed so far
    index, used = 0, 0              # current block, and how much of it is placed
    for part in range(parts):
        # Chunk boundaries at round(total * k / parts): sizes differ by
        # at most one.
        size = total * (part + 1) // parts - taken
        chunk, owner = [], []
        while size > 0:
            block = blocks[index]
            take = min(size, block.count - used)
            if take > 0:
                chunk.append(ReplicationBlock(
                    x=block.x, root=block.root, stream=block.stream,
                    offset=block.offset + used * block.stride, stride=block.stride, count=take,
                ))
                owner.append(index)
                used += take
                size -= take
                taken += take
            if used == block.count:
                index, used = index + 1, 0
        chunks.append(chunk)
        owners.append(owner)
    return chunks, owners


class PoolExecutor(Executor):
    """
    Runs replications on worker processes: `--simpar`.

    `open` starts `workers` processes (pymoso/pool.py owns them) and
    sends each the problem, once; each opens a `SerialExecutor` over
    it. `run` divides everything it is given -- all the blocks of the
    call, together -- into at most `workers` chunks of replications
    and runs one per worker. So the parallelism available to a call
    is its total replication count, whether that is one point's `m` or
    forty points' (docs/simpar-ceiling.md).

    The worker, not the parent, turns each coordinate into a stream,
    so that cost runs in parallel too; and the worker enforces each
    replication's draw reserve, which the mechanism this replaced
    could not do at all under `--simpar`.

    Cutting a block costs something: each piece pays its own jump to
    its starting offset (~1.5 ms for MRG32k3a on the default branch,
    docs/hit-cost-baseline.md). The pieces run in parallel, so wall
    time still falls; total CPU rises. A simulation much cheaper than
    that jump does not benefit from `--simpar` in the first place.

    Parameters
    ----------
    workers : int
        At least 1.
    context : multiprocessing context or None
        Defaults to the platform's default start method. Not used when
        `backend` is given.
    backend : backend or None
        Where the workers are (`pool.LocalBackend` describes what a
        backend is). Defaults to worker processes on this machine.

    Raises (from `open`)
    --------------------
    TypeError
        The problem handle is not transportable (`InProcessHandle`).
    Exception
        Whatever loading the problem raised in a worker -- for
        instance an ImportError from a user file's own imports. It is
        raised here, at open, not left to surface as a hang.
    """

    def __init__(self, workers, context=None, backend=None):
        if workers < 1:
            raise ValueError('an executor needs at least one worker, got {0}'.format(workers))
        self.workers = workers
        self._backend = backend if backend is not None else LocalBackend(context)
        self._pool = None

    def open(self, problem, generator):
        if self._pool is not None:
            raise RuntimeError('this executor is already open; close() it first')
        registry.get_generator(generator)      # raises for an unknown name
        if not problem.transportable:
            raise TypeError(
                '{0} cannot be sent to another process; a pool executor needs a '
                'transportable problem handle such as ClassHandle.'.format(type(problem).__name__)
            )
        self._pool = self._backend.pool(self.workers, _open_worker_executor, (problem, generator)).open()
        return self

    def close(self):
        pool, self._pool = self._pool, None
        if pool is not None:
            pool.close()

    def run(self, blocks):
        if self._pool is None:
            raise RuntimeError('this executor is not open')
        blocks = list(blocks)
        chunks, owners = split_blocks(blocks, self.workers)
        outcomes = self._pool.run([(_run_blocks, (chunk,)) for chunk in chunks])
        results = [[] for _ in blocks]
        for owner, pieces in zip(owners, outcomes):
            for index, piece in zip(owner, pieces):
                results[index].extend(piece)
        return results

    def __exit__(self, exc_type, exc_val, exc_tb):
        pool = self._pool
        if exc_type is not None and pool is not None:
            # Leaving on an exception: stop the workers without waiting
            # for whatever they are in the middle of.
            self._pool = None
            pool.__exit__(exc_type, exc_val, exc_tb)
        self.close()
        return False
