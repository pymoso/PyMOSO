#!/usr/bin/env python
"""
Provide the base class for problem implementations.

An `Oracle` is a simulation with a point for input. It decides which
random numbers every replication of every point gets -- a coordinate,
computed -- hands the replications to its executor to run, and
aggregates what comes back. `pymoso.chnbase.Oracle` is this class,
and the documented import path.

Listing
--------------
Oracle(object), class
"""
import statistics
from math import gcd, sqrt
from .prng import registry
from .prng import base as _prng_base
from .prng.base import (
    ReplicationOverflow, IterationOverflow, SyncOverflow, PointCodeCollision, one_past,
    canonical_point, PointNotEncodable,
)
from .executor import (
    ReplicationBlock, SerialExecutor, PoolExecutor, InProcessHandle, ClassHandle,
)


# The largest replication_draws accepted: 2**40 draws leaves the MRG
# family 49 bits of point code (Philox 46). Past it, hashed point codes
# start to collide at realistic numbers of points per iteration.
MAX_REPLICATION_DRAWS = 1 << 40


# The mean and variance of replications, defined here rather than taken
# from statistics, whose variance(data, xbar) changed between Python 3.10
# and 3.14 (KNOWN_ISSUES.md issue 17): 3.10 squared each deviation with
# **, which is the C library's pow, and 3.14 multiplies. Both sum exactly
# and round once; so do these, with d * d, an IEEE multiply, so no part
# depends on the Python version or the platform. They give 3.14's values.
# ints and floats only; other number types (Decimal, Fraction) go to
# statistics as before, so they keep their type.

def _exact_sum(values):
    """The exact sum of ints and floats as (numerator, denominator), or
    None if one of them is an infinity or a nan."""
    num, den = 0, 1
    for v in values:
        try:
            p, q = v.as_integer_ratio()
        except (OverflowError, ValueError):
            return None
        lcm = den // gcd(den, q) * q
        num, den = num * (lcm // den) + p * (lcm // q), lcm
    return num, den


def _is_plain(data):
    return all(isinstance(v, (int, float)) for v in data)


def _mean(data):
    """The mean, rounded once from the exact sum; an int when every value
    is an int and the mean is whole, as statistics.mean gives"""
    if not _is_plain(data):
        return statistics.mean(data)
    total = _exact_sum(data)
    if total is None:
        # an infinity or a nan decides the result, as in float addition
        acc = 0
        for v in data:
            acc = acc + v
        return acc / len(data)
    num, den = total
    den = den * len(data)
    if num % den == 0 and all(isinstance(v, int) for v in data):
        return num // den
    return num / den


def _variance(data, xbar):
    """The sample variance about xbar: each deviation d = x - xbar and its
    square d * d rounded as floats, those squares summed exactly, divided
    by n - 1 and rounded once; nan if a value or xbar is not finite"""
    if not _is_plain(data) or not isinstance(xbar, (int, float)):
        return statistics.variance(data, xbar)
    total = _exact_sum([(x - xbar) * (x - xbar) for x in data])
    if total is None:
        return float('nan')
    num, den = total
    den = den * (len(data) - 1)
    if num % den == 0 and isinstance(xbar, int) and all(isinstance(v, int) for v in data):
        return num // den
    return num / den


class Oracle(object):
    """
    Base class to implement black-box simulations that implicitly
    define a MOSO problem.

    **What a point is.** A point is a tuple of numbers, and `g()`
    decides whether it is feasible. That is the whole contract, and it
    is the same with and without CRN:

    - A whole number is the same point whatever type it arrives as:
      30, 30.0, `numpy.int64(30)` and `Fraction(30)` are one point and
      draw from the same streams. `g()` is handed the point as the
      caller gave it.
    - A number that is not whole (30.5) is passed to `g()` like any
      other. A problem on the integers will call it infeasible, as
      the built-in ones do; one that allows it may simulate it.
    - A point with a component that is not a finite real number --
      nan, an infinity, a string -- is reported infeasible without
      `g()` being called: it cannot be given a random-number stream.

    The built-in RA solvers search the integer lattice, so the points
    they generate are integers wherever they start.

    **What `g()` must give.** At a feasible point, every objective's
    observations must have finite variance. The convergence results of
    the built-in algorithms assume it (Wang, Pasupathy and Schmeiser
    2013, Lemma 5.2, for R-SPLINE; Assumption 3 of Cooper, Hunter and
    Nagaraj, the paper that introduces R-MinRLE, R-PE and R-PERLE).
    Nothing checks it.

    **One stream per purpose.** `rng.advance(d)` returns a second
    generator `d` draws past `rng`, leaving `rng` where it was: drawing
    from it gives what `rng` would give after `d` more draws, a draw
    being one `random()` call, on every generator. **The replication's
    reserve is checked on `rng` only.** Draws taken on an advanced
    generator are not counted, so without common random numbers a `g()`
    that advances, and draws, past `replication_draws` reaches the next
    replication's numbers and nothing raises
    (tests/test_rng_advance.py records it).

    Attributes
    ----------
    rng : Stream object
    The stream the Oracle was constructed over. It identifies the
    selected generator (`type(self.rng)`, set_crnflag()) and supplies
    the root every coordinate is computed from (`rng.root_seed()`,
    stored as `_orc_root`). hit() never draws from it and never moves
    it: each replication's `g(x, rng)` call is handed its own fresh
    stream at that replication's coordinate (docs/rng-interface-
    design.md §12 step 9). Its state between calls means nothing to the
    framework -- MOCOMPASS, in-tree, still saves and restores it via
    getstate()/setstate() as its own attempted cross-point
    synchronization, which has no effect on what hit() draws (see
    docs/mocompass-mopbnb-known-issues.md and §4.2/§4.3).
    _iteration : int
    Count of completed _advance_iteration() calls (one per RA
    iteration). The
    `stream` half of every default- and CRN-branch coordinate: under
    crnflag=True, iteration k's replication r is drawn at
    `stream_at(_orc_root, k, r*REPL_STRIDE)` for every point (§2 --
    that sharing across points *is* what "common random numbers" means
    here); under crnflag=False, at `stream_at(_orc_root, k,
    offset_within_iteration(x, visit, r, W))`.
    _executor : executor.Executor, or None
    What actually runs replications: hit() describes each call as a
    `ReplicationBlock` and hands it over (pymoso/executor.py). Opened
    lazily, on the first hit(). By default a SerialExecutor over this
    instance -- so `g()` is called on this very object, with whatever
    state it carries; after set_simpar(n > 1), a PoolExecutor of n
    worker processes over this Oracle's class. The serial one (here,
    or inside each worker) holds the per-stream cache that keeps
    crnflag=True hit()s cheap; see SerialExecutor's own docstring
    before touching that. `None` until first needed, and again after
    mp_cleanup().
    _orc_root : tuple of int
    Fixed for the Oracle's entire lifetime (set once, in set_crnflag(),
    never reassigned) -- the reference point every hit() coordinate is
    computed from (§4.1/§4.3, §12 step 9): `rng.root_seed()`.
    crnflag : bool
    Indicates whether common random numbers is turned on or off.
    Defaults to off.
    simpar : int
    Number of processes to use when doing simulations. Defaults to 1
    dim : int
    Number of dimensions of feasible points
    num_obj : int
    Number of objectives returned by g

    Parameters
    ----------
    rng : prng.MRG32k3a object

    """

    def __init__(self, rng):
        self.rng = rng
        self.crnflag = False
        self._iteration = 0
        # commands/solve.py/testsolve.py construct a throwaway Oracle
        # over a plain random.Random() -- no root_seed() -- purely to
        # read .dim, and never call set_crnflag() on it. So nothing
        # here touches `rng`: _orc_root gets its real value in
        # set_crnflag(), which every real solve()/testsolve()/
        # mp_replicate() path calls before any hit().
        self._executor = None
        self._orc_root = None
        # §12 step 6b: the selected generator's own canonical NAME
        # (a string, not the module itself -- see the `_backend`
        # property below for why), resolved from type(self.rng) the
        # first time set_crnflag() runs (same "not dereferenced until a
        # real path sets it" posture as the three seed attributes
        # above) -- see registry.backend_for_stream.
        self._backend_name = None
        self._repl_reserve_bits = None
        # crnflag=False continuation tracking (§4.1) -- how many
        # replications hit() has already drawn for (x, visit) within
        # the current iteration, so a repeat call gets the next
        # contiguous block instead of restarting at 0 (MOPBnB's own
        # need, see hit()). Reset whenever the iteration advances.
        self._replications_drawn = {}
        self._point_codes = {}
        # §12 step 6c/8: the oracle-role coordinate high-water mark --
        # (stream, offset), the *last* coordinate actually touched via
        # hit() (any branch) or _hit_via_coordinate, relative to
        # `_orc_root` -- see get_endseed()'s own docstring for the full
        # contract, its oracle-role-only scope, and why this tracks the
        # last touch rather than "one past" it (§3.9's stream/offset
        # split, not a flat integer, needs an explicit carry step to
        # compute "one past" safely -- pymoso.prng.base.one_past).
        # `None` means untouched. Monotonic for the Oracle's lifetime
        # (reset only in set_crnflag(), matching `_iteration`'s own
        # reset there) -- never reset by _advance_iteration(), since every
        # branch's own `stream` value only ever increases as
        # `_iteration` advances.
        self._high_water_mark = None
        super().__init__()

    # How many uniform draws one replication of g() may make without
    # common random numbers, with every generator. One more raises
    # ReplicationDrawOverflow. A problem whose g() needs more sets this
    # on its class, to a power of two up to 2**40; every replication
    # then starts that far from the last. The bits come out of the code
    # a point's position is computed from, so a larger value makes
    # points with large or many components fall back to a hashed code
    # sooner (prng/base.py, encode_point), and a hashed collision raises
    # PointCodeCollision. With --crn and sync=, replications are 2**76
    # draws apart (more with Philox) whatever this says. A class
    # attribute, not an argument: it is a property of g(), and a worker
    # rebuilding the oracle from its class gets it with the class.
    replication_draws = 1 << 14

    @classmethod
    def replication_reserve_bits(cls, backend):
        """
        `replication_draws`, in the selected generator's units of
        offset: the log2 of the stride between replications when
        common random numbers are off.

        Parameters
        ----------
        backend : module
            The selected generator's own module.

        Returns
        -------
        int

        Raises
        ------
        ValueError
            If `replication_draws` is not a power of two between the
            generator's draws per unit of offset and 2**40.
        """
        draws = cls.replication_draws
        unit = backend.DRAWS_PER_OFFSET
        if (not isinstance(draws, int) or isinstance(draws, bool) or draws < unit
                or draws > MAX_REPLICATION_DRAWS or draws & (draws - 1)):
            raise ValueError(
                '{0}.replication_draws must be a power of two from {1} to 2**40, '
                'got {2!r}. It is the number of uniform draws one replication of '
                'g() may make without common random numbers; the default is '
                '16384.'.format(cls.__name__, unit, draws)
            )
        return (draws // unit).bit_length() - 1

    @property
    def _backend(self):
        """
        The selected generator's own module (registry.GENERATORS
        lookup from `_backend_name`) -- a property, not a plain
        attribute, specifically so the stored state (`_backend_name`,
        a string) stays picklable. `testsolve`'s own `--proc` path
        ships fully-constructed Oracle instances across a process
        boundary (KNOWN_ISSUES.md issue 7's own pre-existing fragility)
        -- storing the module object directly here broke that pickling
        outright (`TypeError: cannot pickle 'module' object`, confirmed
        directly when this was first tried), not a hypothetical
        concern.
        """
        return registry.GENERATORS[self._backend_name]

    def _initialize_if_needed(self):
        """
        Behave as if `set_crnflag(False)` had been called, if nothing
        has called it yet.

        `solve()` and `testsolve()` always call `set_crnflag()`, which
        fixes the generator and the root every coordinate is computed
        from. An oracle constructed and used directly -- `hit()` on a
        fresh instance -- has its flag already (False, from __init__)
        but not those two, and used to fail with `KeyError: None`.
        Construction itself stays free of that work: instances built
        only to read `dim` (testsolve, the CLI) may hold a plain
        `random.Random`, which no generator owns.
        """
        if self._backend_name is None:
            self.set_crnflag(self.crnflag)

    def set_simpar(self, simpar, backend=None):
        """
        Choose how many processes run this Oracle's replications.

        With `simpar` of 1, replications run in this process. Above 1,
        they run on that many worker processes
        (`executor.PoolExecutor`): the workers are started on the
        first hit(), are sent this Oracle's *class*, and construct a
        fresh instance per replication -- so a problem whose `g()`
        depends on per-instance state set after construction cannot
        use it.

        Parameters
        ----------
        simpar : int
            Number of processes to use when performing simulation replications.
        backend : backend or None
            Where those processes are, when `simpar` is above 1
            (`pool.LocalBackend` describes what a backend is). Defaults
            to worker processes on this machine.

        Returns
        -------
        Oracle
            self, so this doubles as a context manager: `with
            orc.set_simpar(n):` guarantees mp_cleanup() runs via
            __exit__ on every exit path (normal return, exception, or
            KeyboardInterrupt), not only when the caller's own code
            happens to reach an explicit mp_cleanup() call.

        Raises
        ------
        ValueError
            `simpar` is above 1 and this Oracle's class cannot be sent
            to a worker process (executor.ClassRef). Raised here,
            before any worker exists.
        """
        self._close_executor()
        remote = getattr(backend, 'remote', False)
        self._class_handle = ClassHandle(type(self), remote=remote) if simpar > 1 else None
        self._pool_backend = backend
        self.simpar = simpar
        return self

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._close_executor(abandon=exc_type is not None)
        return False


    def mp_cleanup(self):
        """
        Stop whatever is running this Oracle's replications, worker
        processes included. Call this after simulation is complete, or
        use `with orc.set_simpar(n):`. A later hit() starts again.
        """
        self._close_executor()


    def set_crnflag(self, crnflag):
        """
        Set the common random number (crn) flag and initialize the
        iteration baseline.

        Also resolves `self._backend` (the selected generator's own
        module, from `type(self.rng)`, §12 step 6b) -- set_crnflag() is
        this class's own authoritative initialization point (see
        `_orc_root`'s own comment below). Every registered generator
        supports both crnflag values (§12 step 9).

        Parameters
        ----------
        crnflag: bool
        """
        self.crnflag = crnflag
        backend = registry.backend_for_stream(self.rng)
        self._backend_name = registry.GENERATOR_NAMES[backend]
        self._repl_reserve_bits = type(self).replication_reserve_bits(backend)
        self._iteration = 0
        self._close_executor()
        # Fixed for the Oracle's lifetime, unlike `_iteration` above:
        # the reference point every coordinate -- default, CRN, visit=
        # and sync= alike -- is computed from (docs/rng-interface-
        # design.md §4.1/§4.3, §12 step 9). Captured here rather than in
        # __init__ because set_crnflag() is the authoritative
        # initialization point in every real solve()/testsolve()/
        # mp_replicate() call path (see __init__).
        #
        # root_seed(), not get_seed(): the value _hit_via_coordinate
        # passes as stream_at's own base_seed (§12 step 6b) -- for the
        # MRG family these are identical (a raw seed already is a valid
        # stream_at base), but not for Philox, whose get_seed() returns
        # its own full (key, counter, buffer) state, not the 2-tuple
        # base key stream_at expects. See root_seed()'s own docstring
        # on each backend's Stream class.
        self._orc_root = self.rng.root_seed()
        self._replications_drawn = {}
        self._point_codes = {}
        self._high_water_mark = None

    def _touch_coordinate(self, stream, offset):
        """
        Record that the oracle-role coordinate `(stream, offset)` --
        relative to `_orc_root` -- has now been touched: the *last* raw
        position a replication's own reserve could actually have
        reached, not "one past" it. Called once per hit() replication
        block, from every branch that computes a coordinate (§12 step 8).

        §12 step 6b: takes `(stream, offset)` directly now, computed by
        the caller against the selected backend's own `OFFSET_CAPACITY`
        -- not a flat integer this method itself divmods by a hardcoded
        `ITER_STRIDE`, which only the MRG family has at all (§3.9:
        Philox's own coordinate is two-dimensional natively, no
        flattening step to invert). Every caller already computes
        `(stream, offset)` this way now (`_hit_via_coordinate`'s own
        `divmod(offset + m*stride - 1, backend.OFFSET_CAPACITY)`, for
        every branch -- the CRN branch's `(self._iteration,
        m*REPL_STRIDE - 1)` is that same expression at `offset = 0`,
        §12 step 9) -- this method
        only ever compares and stores the pair.

        Storing the last position touched, rather than "one past" it
        directly, is deliberate (a change from this method's own
        earlier, flat-integer form): computing "one past" is now a
        carry operation (`pymoso.prng.base.one_past`), done once at
        `get_endseed()` time, where the carry's own safety can be
        checked explicitly -- see that method's own docstring for why.

        The sync branch's own `stream` (at or above
        `backend.SYNC_ZONE_STREAM_START`) sorts correctly, automatically,
        above any default/CRN-branch touch by plain tuple comparison,
        without this method needing to know which branch called it.

        Parameters
        ----------
        stream : int
            Non-negative.
        offset : int
            Non-negative.
        """
        candidate = (stream, offset)
        if self._high_water_mark is None or candidate > self._high_water_mark:
            self._high_water_mark = candidate

    def get_endseed(self):
        """
        A stream guaranteed not to overlap anything this Oracle has
        actually handed to `g()` so far -- §8.2's high-water-mark
        `endseed` (docs/rng-interface-design.md), replacing
        `crn_advance()`'s own call-count-only reporting (`_iteration *
        ITER_STRIDE`), which lost real information (confirmed
        empirically: MOCOMPASS and MOPBnB used to report identical
        `endseed`s for verified-different consumption).

        **Oracle-role only** (§8.2's own explicit scoping, not "every
        role" a run touches): a solver's own draws -- `RASolver`'s
        `sprn`/`solvprn`/`xprn`, `RLESolver`'s equivalents -- are not
        coordinate-based yet (no onboarded generator's `stream_at`
        covers solver-role today), and are a structurally separate
        concern from what this method can see: `solvprn` is an ordinary
        `MRG32k3a` stream, advanced one raw draw at a time the way
        `random.Random` always has been, so reaching the coordinate
        region oracle-role coordinates occupy (`ITER_STRIDE = 2**127`
        and up, per iteration) would take on the order of 2**127
        ordinary draws -- not reachable in practice, but a real
        limitation of this method's guarantee, not covered tracking
        described as "every role." A caller relying on `get_endseed()`
        to also bound solver-role consumption would be relying on
        something this method does not actually provide.

        **The carry, proven safe before use, not assumed** (§12 step
        6c): `_high_water_mark` stores the last coordinate genuinely
        touched, as `(stream, offset)`; the seed returned must be one
        past it -- `pymoso.prng.base.one_past(stream, offset,
        offset_capacity, stream_family_capacity)`, which raises
        `StreamFamilyExceeded` rather than silently landing in a
        different, already-allocated family's own territory (the same
        class of defect `MAX_RI`'s unenforced silent overlap was). The
        family capacity depends on which zone the touch's own `stream`
        falls in, both inside this isp path's own slot: below
        `SYNC_ZONE_STREAM_START`, it's the default/CRN zone, bounded by
        `ISP_ITER_MARGIN` (carrying past it would land in this path's
        own sync zone); at or above it, it's the sync zone, bounded by
        `ISP_STREAM_SPAN` (carrying past it would land in the *next*
        isp path's slot). The sync zone used to be left unbounded
        (`None`), which was only defensible while it lay outside every
        slot -- the defect described at `SYNC_ZONE_STREAM_START`'s own
        definition (mrg32k3a.py). An untouched
        Oracle (`_high_water_mark is None`) returns `_orc_root` itself,
        with no carry computed at all -- there is nothing to be "one
        past" yet.

        Returns
        -------
        tuple of int
            A seed safely past everything this run's own oracle-role
            coordinates touched -- safe to hand to independent,
            unrelated work (e.g. a fresh `MOSOSolver` run).

        Raises
        ------
        StreamFamilyExceeded
            The carry would land in a different family's own reserved
            territory (see above) -- pathological, not reachable by
            any realistic run under MRG32k3a's own margins, but checked
            rather than assumed.
        """
        self._initialize_if_needed()
        if self._high_water_mark is None:
            return self._orc_root
        stream, offset = self._high_water_mark
        backend = self._backend
        family_capacity = backend.ISP_ITER_MARGIN if stream < backend.SYNC_ZONE_STREAM_START else backend.ISP_STREAM_SPAN
        next_stream, next_offset = one_past(
            stream, offset, offset_capacity=backend.OFFSET_CAPACITY, stream_family_capacity=family_capacity
        )
        return backend.stream_at(self._orc_root, next_stream, next_offset).get_seed()

    def get_high_water_mark(self):
        """
        The `(stream, offset)` pair `get_endseed()` derives its seed
        from -- `_high_water_mark`, relative to `_orc_root`, or `None`
        if this Oracle has never touched a coordinate. Exists for
        `testsolve()`'s own cross-path aggregation (docs/rng-interface-
        design.md §12 step 8 stage 2): each `isp` path's `Oracle` runs
        in its own process under `--proc`/`--simpar`, so only picklable
        result-dict values -- not the live `Oracle` object `get_endseed()`
        itself needs -- survive back to the caller. `RASolver.solve`
        (and MOCOMPASS/MOPBnB's own `solve()`) return this value in
        their result dict for exactly that reason. Not part of any
        per-path public seed contract on its own -- `get_endseed()`
        remains the one meaningful seed for a single path; this is
        raw material for combining several.

        Returns
        -------
        tuple of (int, int), or None
        """
        return self._high_water_mark

    def _advance_iteration(self):
        """
        Advance to the next RA iteration. Every default- and CRN-branch
        coordinate carries `_iteration` as its `stream`, so this one
        increment moves both branches to a stream disjoint from every
        earlier iteration's: iteration k's CRN baseline is
        `stream_at(_orc_root, k, 0)`, i.e. `orc_root + k*2**127` for the
        MRG family (docs/rng-interface-design.md §2).

        Also resets `_replications_drawn` (hit()'s crnflag=False
        continuation tracking, §4.1): a new iteration's coordinate space
        is disjoint from the last one's, so no continuation state from
        the previous iteration could be meaningful here even if kept.
        The executor's base-stream cache is keyed on `(root, stream)`,
        and `stream` is `_iteration`, so it needs no reset here -- the
        next hit() simply asks for a different stream.

        §12 step 9: this used to jump `rng` itself one ITER_STRIDE
        forward and re-read `_iteration_baseline_seed`/`_next_seed` from
        it, a second, stateful implementation of the position
        `stream_at` computes directly. That model is gone; nothing here
        touches `rng`, for either crnflag value or any generator.

        Framework bookkeeping, not solver API: RASolver.rasolve()
        calls this once per RA iteration, and nothing else should. It
        was public as `crn_advance()` until docs/rng-interface-
        design.md §11 open question 7 was carried out -- removed
        outright, no deprecated alias, because the one way real solvers
        used it (MOCOMPASS and MOPBnB, once, at the end of solve()) did
        nothing useful and looked like CRN support it did not provide
        (§4.2). A custom MOSOSolver that called `orc.crn_advance()`
        should delete that line; nothing replaces it.
        """
        self._iteration += 1
        self._replications_drawn = {}
        self._point_codes = {}

    def _record_point_code(self, code, x):
        """
        Collision detection for the default branch's point codes: note
        that `x` was coded as `code` in the current iteration, and raise
        if a *different* point already holds that code.

        Needed because `encode_point` is no longer injective: a point
        too large for the exact positional code is hashed into the same
        field (pymoso/prng/base.py). Exact codes cannot collide with
        each other, but a hashed code can coincide with another hashed
        code or with an exact one, so every code is recorded, not only
        hashed ones. With this check a run is still "correct or
        raises": two points are never silently handed the same
        replication streams.

        `_point_codes` maps code -> point for the current iteration
        only. It is reset in `_advance_iteration()`, because the next
        iteration draws from a different stream, where the same code is
        a different position. Its size is the number of distinct points
        hit on the default branch this iteration -- the same order as
        `_replications_drawn`, which already holds one entry per point.

        **Where the check is exhaustive.** Point codes are computed in
        exactly one place, `_hit_via_coordinate`'s default branch, in
        the process that owns this Oracle, and every one passes through
        here first. `visit != 0` uses the same code and is covered. The
        CRN and sync branches put no point in the coordinate and have
        nothing to collide. Under `--simpar`, workers never compute
        coordinates -- this process computes every seed and queues
        `(x, seed)` -- so this one record sees every point. Under
        `--proc`, each isp path has its own Oracle and its own record,
        and also its own slot of streams: the same code on two paths is
        two different positions, so there is no cross-path collision to
        miss.

        **Three ways around it, none new, written down so they are not
        rediscovered:**

        1. Code that calls a backend's `stream_at`,
           `offset_within_iteration` or `offset_from_point_code`
           directly, instead of `hit()`. Nothing here sees those
           coordinates.
        2. A subclass that overrides `hit()` or `_hit_via_coordinate`
           and computes coordinates itself.
        3. Two Oracles constructed over the same root in one process.
           Each keeps its own record; they draw from the same streams.

        The first and third were equally unguarded when the code was
        exact: an exact code only ever promised distinct points
        distinct positions *within one Oracle's own hit() calls*. This
        check is no weaker than `PointCodeOverflow`'s guard was; it has
        the same scope.

        Parameters
        ----------
        code : int
        x : tuple of int

        Raises
        ------
        PointCodeCollision
        """
        seen = self._point_codes.get(code)
        if seen is None:
            self._point_codes[code] = tuple(x)
        elif seen != tuple(x):
            raise PointCodeCollision(
                'points {0} and {1} both map to point code {2} in RA '
                'iteration {3} and would share replication streams. At '
                'least one is too large for the exact positional code '
                '(dim={4}) and was hashed. Use crn=True, or reduce the '
                'dimension or magnitude of the points. See docs/rng-'
                'interface-design.md §3.4.'.format(seen, tuple(x), code, self._iteration, len(x))
            )

    def _get_executor(self):
        """
        The executor that runs this Oracle's replications, opened on
        first use: a `SerialExecutor` over this very instance
        (`InProcessHandle(self)`), or -- after `set_simpar(n)` with n
        above 1 -- a `PoolExecutor` of n workers over this Oracle's
        class.

        Lazy because `set_crnflag()` is what fixes the generator, and
        it runs after construction. It is dropped (`_close_executor`)
        by `set_crnflag()`, `set_simpar()` and `mp_cleanup()`, and
        reopened on the next hit() if there is one.

        Returns
        -------
        executor.Executor
        """
        if self._executor is None:
            handle = getattr(self, '_class_handle', None)
            if handle is not None:
                backend = getattr(self, '_pool_backend', None)
                self._executor = PoolExecutor(self.simpar, backend=backend).open(handle, self._backend_name)
            else:
                self._executor = SerialExecutor().open(InProcessHandle(self), self._backend_name)
        return self._executor

    def _close_executor(self, abandon=False):
        """`abandon`: do not wait for work in progress (an exception is
        propagating)."""
        executor = getattr(self, '_executor', None)
        self._executor = None
        if executor is not None:
            if abandon:
                executor.__exit__(Exception, None, None)
            else:
                executor.close()

    def __getstate__(self):
        # An Oracle is plain data plus, possibly, live worker
        # processes. A copy does not get the processes; it opens its
        # own executor on its first hit().
        state = self.__dict__.copy()
        if isinstance(state.get('_executor'), PoolExecutor):
            state['_executor'] = None
        return state

    def _hit_via_coordinate(self, x, m, visit, sync, start_replication=0, crn=False):
        """
        The explicit-coordinate replication path (docs/rng-interface-
        design.md §4.1/§4.3), computed fresh from the Oracle's fixed
        `_orc_root` -- the one path every hit() call runs through, for
        every branch (§12 step 9). Never touches `rng`.

        This method computes *where* the block is and checks that it is
        allowed to be there; it does not run anything. It builds a
        `ReplicationBlock` -- point, root, `(stream, offset)`, stride,
        count -- and hands it to the executor (pymoso/executor.py),
        which turns the coordinate into streams and calls `g()`.
        Aggregating the results into a mean and standard error happens
        back here.

        Three coordinate shapes, one loop:

        - default (`sync is None`, `crn` False): `stream = _iteration`,
          `offset = offset_within_iteration(x, visit, replication, W)`,
          replications `REPL_RESERVE_STRIDE` apart.
        - CRN (`crn` True): `stream = _iteration`, `offset =
          replication*REPL_STRIDE` -- the default branch's stream with
          the point and visit terms dropped (CRN is point-independent by
          construction, §2) and the sync branch's wide stride. The
          block starts at offset 0 of the iteration's stream, which
          the executor has cached -- that, not a fresh jump from the
          root per call, is why a CRN hit() is cheap.
        - sync (`sync` an int): the caller-chosen axis, below.

        §12 step 6b: generalized off the MRG-only mechanism step 6c left
        in place (raw jump_seed_n chaining on a bare seed tuple, then
        constructing `MRG32k3a(s)` directly per replication -- both
        MRG-shaped, neither expressible for Philox, which has no
        jump-ahead and builds its stream from `(key, counter)`, not a
        flat seed). The offset/default branch (`sync is None` --
        every ordinary `hit()` call, visit!=0 included: `visit` is just
        a parameter of `offset_within_iteration`, not a separate
        formula) now computes `stream = self._iteration`, `offset =
        self._backend.offset_within_iteration(...)` directly -- no
        flattening through an `ITER_STRIDE`-sized `base` integer at all,
        since `stream`/`offset` were always the two dimensions §3.9
        already named; the flattening was legacy structure from before
        that split existed, not something intrinsic to the computation.
        The sync branch is two-dimensional too: `stream =
        SYNC_ZONE_STREAM_START + sync // SYNC_PER_STREAM`, inside this
        isp path's own slot, with `SYNC_PER_STREAM` sync values sharing
        a stream -- see the selected backend's own constants for the
        sizing, and mrg32k3a.py for the defect the nesting fixes.

        Three callers, unified here on purpose (docs/rng-interface-
        design.md §12 step 4a's own convergence note, completed by step
        9): hit()'s own `crnflag=True` path (`crn=True`,
        `start_replication` always 0 -- every CRN hit() restarts at the
        iteration baseline, which is what makes the streams common
        across points); hit()'s explicit
        `visit!=0`/`sync=<int>` arguments (`start_replication` always 0
        there -- no continuation concept for an explicitly independent
        block, or for a solver-controlled sync axis whose own caller,
        e.g. MOCOMPASS's `nx[x]`, already encodes "which block"), and
        hit()'s own default `crnflag=False` path (step 4b's cutover --
        `start_replication` tracked automatically by hit() itself, per
        `(x, visit)`, across calls within one iteration, §4.1).

        Advances via a real per-replication `Stream.advance(stride)`
        call on both branches, not a fresh `stream_at` call per
        replication (the expensive, ~127-round binary exponentiation
        step 2's own commit found and fixed as a regression for MRG,
        and would be for any backend -- `advance`'s own contract exists
        specifically so this stays O(1) per replication generically,
        not just for MRG's own cached jump_seed_n fast path; timed
        directly against this step's own before/after, not assumed --
        see docs/rng-interface-design.md §12 step 6b). The sync
        branch's replication term is `replication*REPL_STRIDE` (§4.3's
        own formula -- the same spacing the CRN branch uses); the
        offset/default branch's is `replication*2**REPL_RESERVE_BITS`
        (base.py's offset_within_iteration) -- this branch used to
        advance via a single raw mrg32k3a() step instead (no reserve at
        all), a defect found ahead of §12 step 8 (docs/rng-interface-
        design.md's step 8 prerequisite writeup): a g() call drawing
        more than one raw value (every built-in problem) ran its own
        consumption into the position reserved for the next
        replication, so replications were not actually independent.
        The executor still enforces the reserve at runtime
        -- raising ReplicationDrawOverflow if a single replication
        draws more than 2**REPL_RESERVE_BITS raw values (this
        generator's own REPL_RESERVE_BITS, per §12 step 6c-completion's
        own finding that this check was comparing against a hardcoded,
        MRG-shaped budget regardless of which backend was selected) --
        via `Stream.raw_consumed()` now (§12 step 6b), replacing the
        removed set_class_cache()/.generate monkeypatch, which reached
        into an MRG-only attribute no other backend has. Enforced
        under simpar>1 too: the check runs wherever the replication
        does, in the worker, and the exception comes back.

        Parameters
        ----------
        x : tuple of int
        m : int
        visit : int
        sync : int or None
        start_replication : int
            Non-negative. Which replication index this call's block
            starts at.
        crn : bool
            True for hit()'s own `crnflag=True` path. Requires `sync is
            None` and `visit == 0`; `x` is not part of the coordinate.

        Returns
        -------
        isfeas, obmean, obse : as hit()

        Raises
        ------
        ReplicationDrawOverflow
            A single replication drew more raw values than its
            reserved block holds.
        ReplicationOverflow
            The block's last replication index is past the selected
            backend's `REPL_COUNT_LIMIT`.
        IterationOverflow
            `_iteration` has reached the backend's `ISP_ITER_MARGIN`
            (default and CRN branches).
        SyncOverflow
            `sync` is at or past the backend's `SYNC_CAPACITY`.
        """
        block = self._block_for(x, m, visit, sync, start_replication, crn)
        return self._aggregate(self._get_executor().run([block])[0])

    def _block_for(self, x, m, visit, sync, start_replication=0, crn=False):
        """
        The "where" half of `_hit_via_coordinate` (see its docstring):
        check that the block may be where it is, record it in the
        high-water mark and the point-code table, and return it as a
        `ReplicationBlock`. Nothing is run.
        """
        backend = self._backend
        # Every axis raises at its own boundary, before anything is
        # drawn -- nothing below wraps or spills into a neighbouring
        # zone (docs/rng-interface-design.md, the SYNC_ROLE_OFFSET/
        # ISP_STRIDE entry). offset_within_iteration checks the default
        # branch's *first* replication index itself; this covers the
        # block's last one, and the CRN and sync branches, which have
        # no other check.
        if start_replication + m > backend.REPL_COUNT_LIMIT:
            raise ReplicationOverflow(
                'replications {0}..{1} of x={2} do not fit under this '
                'generator\'s limit of {3} replications per block. See '
                'docs/rng-interface-design.md §3.4.'.format(
                    start_replication, start_replication + m - 1, x, backend.REPL_COUNT_LIMIT
                )
            )
        if sync is None and self._iteration >= backend.ISP_ITER_MARGIN:
            raise IterationOverflow(
                'RA iteration {0} is past the {1} iterations one '
                'independent sample path reserves under {2}; the next '
                'stream belongs to the sync zone. A run that terminates '
                'normally cannot get here -- check that every iteration '
                'of the solver consumes simulation budget '
                '(KNOWN_ISSUES.md issue 13).'.format(
                    self._iteration, backend.ISP_ITER_MARGIN, self._backend_name
                )
            )
        if sync is not None:
            if sync >= backend.SYNC_CAPACITY:
                raise SyncOverflow(
                    'sync={0} does not fit in the {1} sync values one '
                    'independent sample path reserves under {2}. See '
                    'docs/rng-interface-design.md §4.3.'.format(
                        sync, backend.SYNC_CAPACITY, self._backend_name
                    )
                )
            # Two-dimensional like every other coordinate (§3.9):
            # SYNC_PER_STREAM sync values share a stream, inside this
            # path's own sync zone. For the MRG family this flattens to
            # exactly §4.3's `SYNC_ROLE_OFFSET + sync*SYNC_STRIDE +
            # replication*REPL_STRIDE`.
            stride = backend.REPL_STRIDE
            stream = backend.SYNC_ZONE_STREAM_START + sync // backend.SYNC_PER_STREAM
            offset = (sync % backend.SYNC_PER_STREAM) * backend.SYNC_STRIDE + start_replication * stride
        elif crn:
            stride = backend.REPL_STRIDE
            stream = self._iteration
            offset = start_replication * stride
        else:
            # encode_point: the exact positional code when x fits, a
            # hash when it does not (a high-dimensional problem). Either
            # way the code is checked against every other point this
            # iteration has used before anything is drawn.
            # replication_draws moves bits between the replication's
            # reserve and the point code; the default moves none.
            reserve_bits = self._repl_reserve_bits
            point_bits = backend.POINT_BITS - (reserve_bits - backend.REPL_RESERVE_BITS)
            code, _hashed = _prng_base.encode_point(x, point_bits=point_bits)
            self._record_point_code(code, x)
            stream = self._iteration
            offset = _prng_base.offset_from_point_code(
                code, visit, start_replication, visit_bits=backend.VISIT_BITS,
                repl_count_bits=backend.REPL_COUNT_BITS, repl_reserve_bits=reserve_bits,
            )
            stride = 1 << reserve_bits
        # Work as data. `stride` is also each replication's reserve:
        # how many raw values its g() may draw before running into the
        # next replication's start -- the executor checks it on every
        # branch; only the default branch's is small enough to reach.
        block = ReplicationBlock(x=x, root=self._orc_root, stream=stream, offset=offset, stride=stride, count=m)
        # §12 step 8: this block's own replications span
        # [offset, offset + m*stride) relative to `stream` -- see
        # _touch_coordinate's own docstring for why the last position
        # actually touched is offset + m*stride - 1, not offset +
        # m*stride. Carried into `stream + extra_stream` generically via
        # this backend's own OFFSET_CAPACITY (ITER_STRIDE for the MRG
        # family; Philox's own, smaller, real capacity), not a
        # hardcoded ITER_STRIDE -- the same per-generator-budget fix
        # §12 step 6c-completion made for offset_within_iteration
        # itself.
        extra_stream, last_offset = divmod(offset + m * stride - 1, backend.OFFSET_CAPACITY)
        self._touch_coordinate(stream + extra_stream, last_offset)
        return block

    def _aggregate(self, replications):
        """
        One block's replications as hit() reports them.

        Parameters
        ----------
        replications : list of executor.Replication

        Returns
        -------
        isfeas, obmean, obse : as hit()
        """
        m = len(replications)
        dr = range(self.num_obj)
        mr = range(m)
        feas = [replication.isfeas for replication in replications]
        objm = [replication.objectives for replication in replications]
        isfeas = False
        obmean = []
        obse = []
        if all(feas):
            isfeas = True
            if m == 1:
                # matches the default path's own m==1 special case:
                # statistics.variance() requires at least two points.
                obmean = objm[0]
                obse = [0 for o in objm[0]]
            else:
                obmean = tuple([_mean([objm[i][k] for i in mr]) for k in dr])
                obvar = [_variance([objm[i][k] for i in mr], obmean[k]) for k in dr]
                obse = tuple([sqrt(obvar[i]/m) for i in dr])
        return isfeas, obmean, obse

    def hit(self, x, m, visit=0, sync=None):
        """
        Generate the means and standard errors of 'm' simulation
        replications at point 'x'.

        Parameters
        ----------
        x : tuple of numbers
    point at which to simulate
    m : int
    number of replications to simulate 'x'
    visit : int
    Optional, default 0. Nonzero requests an independent resample
    block for this (x, visit) pair, bypassing the default per-point
    continuation (docs/rng-interface-design.md §4.1). Additive: at
    the default 0, hit()'s behavior is exactly as before this
    parameter existed.
    sync : int or None
    Optional, default None. A non-negative int hands the coordinate's
    synchronization axis to the caller entirely, excluding `x`/`visit`
    (§4.3) -- for a solver implementing its own cross-point CRN
    policy. Additive: at the default None, hit()'s behavior is
    exactly as before this parameter existed. Passing both `sync` and
    a non-default `visit` raises ValueError.

        Returns
        -------
        isfeas : bool
    indicates the feasibility of 'x'. False, with empty means and
    standard errors and nothing simulated, for a point that has a
    component which is not a finite real number (class docstring).
        obmean : tuple of float
    mean of each objective of 'm' simulations
        obse : tuple of float
    mean of standard errors of each objective of 'm' simulations

        Notes
        -----
        Every branch routes through `_hit_via_coordinate` (docs/rng-
        interface-design.md §12 step 9). crnflag=True: every call
        restarts at the iteration's baseline, replications REPL_STRIDE
        apart, the same streams for every point (§2's formula,
        bit-identical to the mutable-`rng` mechanism it replaced --
        tests/test_oracle_coordinate_migration.py). crnflag=False
        (docs/rng-interface-design.md §12 step
        4b): coordinate-derived, order-independent by construction --
        different points visited in any order within one iteration no
        longer share a mutable walk position at all. Continuation
        across repeated calls to the same (x, visit) within one
        iteration (§4.1, needed by MOPBnB) is tracked here, in
        `_replications_drawn`, reset whenever `_iteration` advances
        (_advance_iteration()) -- not inside `_hit_via_coordinate` itself,
        since a genuinely opt-in `visit!=0`/`sync=<int>` call never
        continues automatically (a fresh independent block, or a
        solver-controlled axis that already encodes "which block"
        itself).
        """

        block = self._plan_hit(x, m, visit, sync)
        if block is None:
            return False, [], []
        return self._aggregate(self._get_executor().run([block])[0])

    def hit_many(self, requests):
        """
        The same results as `[self.hit(x, m) for x, m in requests]`,
        with every replication of every request handed to the executor
        together.

        Under `set_simpar(n)` that is the difference between n workers
        sharing one point's `m` replications and sharing all of them
        (docs/simpar-ceiling.md). Serially there is no difference at
        all. It is safe because a replication's stream is a function
        of its coordinate, not of the order replications run in.

        A point that appears twice gets two consecutive blocks, as two
        hit() calls would give it (crnflag=False), or the same block
        twice (crnflag=True).

        Parameters
        ----------
        requests : iterable of (tuple of int, int)
            `(x, m)` pairs.

        Returns
        -------
        list of (isfeas, obmean, obse)
            One per request, in order, each as hit() returns it.
        """
        blocks = [self._plan_hit(x, m) for x, m in requests]
        if not blocks:
            return []
        # A point that has no coordinate has no block; it is reported
        # infeasible in its place (see _plan_hit).
        planned = [block for block in blocks if block is not None]
        ran = iter(self._get_executor().run(planned)) if planned else iter(())
        return [self._aggregate(next(ran)) if block is not None else (False, [], []) for block in blocks]

    def _plan_hit(self, x, m, visit=0, sync=None):
        """hit()'s argument checks and coordinate bookkeeping, without
        running anything: the block a hit(x, m, visit, sync) call made
        now would run. Advances the per-point continuation."""
        self._initialize_if_needed()
        assert(m >= 1)
        if sync is not None:
            if visit != 0:
                raise ValueError(
                    'hit() cannot take both sync and a non-default visit -- '
                    'sync already selects the coordinate axis; there is no '
                    'sensible way to also apply visit\'s per-point escape '
                    'hatch on top of it. See docs/rng-interface-design.md §4.3.'
                )
            if sync < 0:
                raise ValueError('sync must be non-negative, got {0}'.format(sync))
        if visit < 0:
            raise ValueError('visit must be non-negative, got {0}'.format(visit))
        # A point is a tuple of numbers and the oracle decides whether
        # it is feasible. The one thing decided here is narrower: a
        # point with a component that is not a finite real number has
        # no coordinate, so it cannot be given a stream, and it is
        # reported infeasible without g() being asked. Checked whatever
        # crnflag is -- a CRN block never needs the point's code -- so
        # that the two modes answer alike.
        try:
            canonical_point(x)
        except (PointNotEncodable, TypeError):
            return None
        if sync is not None or visit != 0:
            return self._block_for(x, m, visit, sync)

        if not self.crnflag:
            key = (x, visit)  # visit == 0 here, always
            start = self._replications_drawn.get(key, 0)
            block = self._block_for(x, m, visit, None, start_replication=start)
            self._replications_drawn[key] = start + m
            return block

        return self._block_for(x, m, 0, None, crn=True)

    def g(self, x, rng):
        """
        Generate a single replication at point `x`.

        Feasibility is decided here. `x` is whatever the caller or the
        solver asked for -- a tuple of numbers, not necessarily of int
        (see the class docstring) -- so a problem defined on integers
        in a box should answer False for anything else, as a test like
        `xi in range(lo, hi + 1)` does.

        Parameters
        ----------
        x : tuple of numbers
        rng : random.Random object

        Returns
        -------
        bool
            Indicates feasibility of `x`
        tuple of float
            The simulated values for each objective
        """
        raise NotImplementedError
