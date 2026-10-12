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

This module has one backend, `SerialExecutor`, which reproduces what
`Oracle.hit()` did inline before it existed, bit for bit. `--simpar`
and `--proc` still run through their own older mechanisms
(`Oracle.set_simpar`, `chnutils.par_runs`).
"""
import inspect
import os
import sys
import types
from collections import OrderedDict
from dataclasses import dataclass
from typing import NamedTuple

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
    -- the recipe `chnbase.mp_replicate` has always used.

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

    Subclasses implement `simulator()`. Adding a transport -- pickling
    a class by value with cloudpickle, for a problem defined in a
    notebook cell, which has no source file to bundle -- means adding a
    subclass here, behind an optional dependency. The executor
    interface does not change (docs/forkserver-hang.md's correction).
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


class ClassHandle(ProblemHandle):
    """
    A problem class, in transportable form: either the class itself
    (it pickles by reference, because a fresh process can import it) or
    a source bundle (it was loaded from a user-supplied file and has no
    importable module) -- see `build_transport_descriptor`. Each
    replication constructs a fresh instance (`simulate_with_class`).

    Parameters
    ----------
    orccls : Oracle class

    Raises
    ------
    ValueError
        `orccls` has no locatable source at all (defined
        interactively). The source-bundle transport cannot carry it.
    """
    transportable = True

    def __init__(self, orccls):
        self.descriptor = build_transport_descriptor(orccls)

    def load(self):
        """The problem class, reconstructed if it travelled as a
        source bundle."""
        return reconstruct_transport_descriptor(self.descriptor)

    def simulator(self):
        return _ClassSimulator(self.load())


def build_transport_descriptor(cls):
    """
    Build whatever a --simpar worker process needs to reconstruct cls,
    once per worker rather than once per replication -- see
    Oracle.set_simpar, the broadcast point this is built at.

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

    Parameters
    ----------
    cls : Oracle class

    Returns
    -------
    cls, unchanged, or a dict source-bundle descriptor

    Raises
    ------
    ValueError
        cls has no locatable source at all (defined interactively, not
        loaded from a .py file) -- --simpar cannot transport it to a
        worker process. Raised here, at worker-creation time, rather
        than left to surface as a hang once a job is dispatched.
    """
    module = sys.modules.get(cls.__module__)
    if module is not None and getattr(module, '__pymoso_dynamic__', False):
        return _build_source_bundle(cls, module)
    try:
        inspect.getfile(cls)
    except (TypeError, OSError) as e:
        raise ValueError(
            f"{cls.__name__} has no locatable source file, so it cannot be "
            "sent to a --simpar worker process. This happens for a class "
            "defined interactively (a REPL or notebook), not loaded from a "
            ".py file. Define it in a .py file and try again, or run "
            "without --simpar."
        ) from e
    return cls


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

        `Oracle`'s own `--simpar` path uses this to get the seeds it
        queues for its workers, until that path moves behind this
        interface as a backend of its own.

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
