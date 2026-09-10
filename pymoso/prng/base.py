"""
The generator-agnostic pieces of docs/rng-interface-design.md's RNG
interface: the Stream protocol every conforming backend must satisfy
(§3.2), the backward-compatibility adapter (§3.6) that lets a Stream be
used anywhere a random.Random-shaped object is expected, and the
non-CRN coordinate-assembly functions (point_code/offset_within_
iteration, §3.4) -- pure integer positional-radix packing, generator-
agnostic in its *logic*.

Correction, §12 step 6c-completion: the packing logic is
generator-agnostic, but the bit-width budget it packs into (module-level
POINT_BITS/VISIT_BITS/REPL_COUNT_BITS/REPL_RESERVE_BITS below) is not --
it is MRG-family's own 127-bit budget (sized to ITER_STRIDE=2**127),
which only the MRG family's periods have room to absorb. point_width/
offset_within_iteration now take that budget as parameters (defaulting
to the constants below, so every existing MRG-only call site is
unaffected) so a generator with a smaller native capacity -- Philox's
own 118-bit budget, comfortably under its 128-bit counter but not under
MRG's 127-bit stride -- can call the same packing logic with its own
figures instead of silently reusing a budget sized for a different
generator. See pymoso.prng.philox4x32's own point_width/
offset_within_iteration.

Stream/RandomCompatAdapter are not yet wired into any backend or into
chnbase.py/chnutils.py -- scaffolding, built ahead of its first real
caller because the step list (§12 step 2) groups it with mrg_common.py's
generalized jump, not because anything consumes it yet. MRG32k3a keeps
subclassing random.Random directly and unchanged; nothing here changes
its behavior.

point_code/offset_within_iteration are landed here in step 3 (ahead of
step 4a/4b, which actually wire them into chnbase.py's coordinate
computation) for the same reason: they have no dependency on `crnflag`
or how chnbase.py uses them, so there is no reason to wait -- see §7.1
items 8-9 and docs/rng-interface-design.md §12 step 3's own note to
that effect.
"""
import random
from typing import Protocol, runtime_checkable


@runtime_checkable
class Stream(Protocol):
    """The complete required surface a conforming generator backend's
    stream_at(base_seed, coordinate) must return (§3.2). Everything
    else -- expovariate, gauss, uniform, choice, sample, shuffle,
    triangular, ... -- is not part of this contract; it's what
    RandomCompatAdapter below provides for free, the same way CPython's
    random.Random already implements all of it in terms of random()/
    getrandbits()."""

    def random(self) -> float:
        """Uniform on [0, 1)."""
        ...

    def getrandbits(self, k: int) -> int:
        """Uniform on [0, 2**k), unbiased. Rejection sampling is
        permitted here -- see §3.3 for why this one method is exempt
        from the monotonicity requirement normalvariate is not."""
        ...

    def normalvariate(self, mu: float = 0, sigma: float = 1) -> float:
        """A monotone, single-draw transform of one random() draw
        (§3.3) -- required, not incidental: CRN's variance-reduction
        guarantee depends on it."""
        ...


class RandomCompatAdapter(random.Random):
    """Backward-compatibility adapter (§3.6), needed because
    Oracle.g(self, x, rng) hands `rng` directly to arbitrary third-party
    code (custom Oracles, and -- confirmed, not hypothetical, per §3.6 --
    custom MOSOSolvers like MOCOMPASS/MOPBnB) documented only as
    "an rng-shaped object," which today means the *entire* random.Random
    API, not just the four Stream methods.

    Composition at the core: __init__/random/getrandbits/normalvariate
    all delegate to a composed Stream object (`self._stream`), never
    implement the recurrence themselves -- subclassing random.Random
    here is a purely cosmetic, opt-in convenience layer on top of that,
    not the load-bearing mechanism (the Stream/stream_at layer above is,
    and is what the conformance suite in §7 tests). A caller that wants
    the full stdlib distribution surface (gauss, uniform, triangular,
    shuffle, ...) gets it for free, backed by `self._stream`, exactly as
    it does today from MRG32k3a's own random.Random subclassing.

    Not used by MRG32k3a/MRG31k3p themselves -- both already subclass
    random.Random directly, so they already have the full surface
    natively. §12 step 6b found its first real caller: Philox4x32Stream
    is deliberately *not* a random.Random subclass (its own module
    docstring), so a built-in problem/tester calling `rng.expovariate()`
    (BSProb's own `g()`) or `rng.choice()` (every built-in tester's own
    `get_ranx0`) on a raw Philox stream raises AttributeError -- confirmed
    directly, not hypothetical, running `pymoso testsolve --generator
    philox4x32 ...` with no `<x>` (which exercises `get_ranx0`).
    `ensure_random_compatible` below is what chnbase.py now calls before
    handing any generator's stream to such code.
    """

    def __init__(self, stream: Stream):
        self._stream = stream
        # random.Random.seed() only accepts None/int/float/str/bytes/
        # bytearray; this call's only purpose is to satisfy that type
        # check; the parent's C-level Mersenne state it seeds is never
        # consulted, since random()/getrandbits()/normalvariate() are
        # fully overridden below -- same reasoning as MRG32k3a.seed()'s
        # own super().seed() call.
        super().__init__(0)

    def __reduce__(self):
        """
        §12 step 6b: found needing this the moment this class got a
        real caller (testsolve()'s own --proc path pickles a fully-
        constructed Oracle/solver, including whatever `sprn`/`solvprn`
        it holds -- KNOWN_ISSUES.md issue 9's own pattern). Without
        this override, random.Random's own inherited __reduce__
        reconstructs via `self.__class__()` -- zero arguments -- then
        applies state; RandomCompatAdapter.__init__ requires `stream`,
        so that call fails outright. Confirmed directly: `pickle.
        dumps(RandomCompatAdapter(stream))` raised "__init__() missing
        1 required positional argument: 'stream'" before this existed.
        Reconstructing via the real constructor, passing `self._stream`
        itself (picklable the same way any other Stream instance is,
        e.g. as a --simpar job payload), is the direct fix.

        Returns
        -------
        tuple
        """
        return (RandomCompatAdapter, (self._stream,))

    def random(self) -> float:
        return self._stream.random()

    def getrandbits(self, k: int) -> int:
        return self._stream.getrandbits(k)

    def normalvariate(self, mu: float = 0, sigma: float = 1) -> float:
        return self._stream.normalvariate(mu, sigma)


def ensure_random_compatible(stream):
    """
    §12 step 6b: `stream` if it already provides the full random.Random
    surface (MRG32k3a/MRG31k3p, both real subclasses), otherwise
    `RandomCompatAdapter(stream)` (Philox4x32Stream, or any future
    backend that similarly implements only the minimal §3.2 protocol).

    Callers: chnbase.py wraps with this immediately before handing a
    stream to `g(x, rng)`/`get_ranx0(rng)` -- code documented only as
    "an rng-shaped object" (§3.6) that may call `expovariate`/`choice`/
    `sample`/... -- never before its own internal coordinate machinery
    (`advance`/`raw_consumed`/`root_seed`/`backend_for_stream`'s own
    `isinstance` check all need the *unwrapped* backend-native
    instance; wrapping is a presentation-layer step for the code the
    stream is handed to, not a replacement for the object itself).

    Parameters
    ----------
    stream : Stream

    Returns
    -------
    random.Random
    """
    if isinstance(stream, random.Random):
        return stream
    return RandomCompatAdapter(stream)
# ---------------------------------------------------------------------------
# Non-CRN coordinate assembly (§3.4). Exact, collision-free by
# construction -- not a hash, not probabilistic (see §3.4's "what does
# work, exactly, with no probability involved" for why a hash-based
# scheme was ruled out). Sizing: ITER_STRIDE (2**127) is split four
# ways -- REPL_RESERVE_BITS + REPL_COUNT_BITS for replication,
# VISIT_BITS for visit, the rest (POINT_BITS) for the point itself,
# adaptively divided across a problem's own dimension as W bits per
# component.
#
# REPL_RESERVE_BITS exists to fix a defect found ahead of §12 step 8
# (docs/rng-interface-design.md's step 8 prerequisite writeup carries
# the full reproduction): replication used to be packed with stride 1
# (consecutive replications one raw recurrence step apart), under the
# assumption that a single replication consumes exactly one raw draw.
# No built-in g() satisfies that -- ProbTPA/ProbTPB/ProbTPC each draw
# 3 normalvariate()s per replication, BSProb draws ~1000 expovariate()s
# (tau=100, lambd=10 -> Poisson(1000) arrivals) -- so replication i's
# stream ran into positions replication i-1's own g() call had already
# consumed, and replications were not independent. REPL_RESERVE_BITS
# is the fix: each replication now gets a real 2**REPL_RESERVE_BITS-
# wide block, honored as an actual stride in offset_within_iteration,
# the same way REPL_STRIDE (2**76) already was for the CRN/sync
# branches (chnbase.py's _hit_via_coordinate). A g() that draws more
# than 2**REPL_RESERVE_BITS raw values overruns its reserve and must
# raise (chnbase.py's _hit_via_coordinate enforces this at the call
# site, where the actual draw count is observable) rather than
# silently collide with the next replication's block.
# ---------------------------------------------------------------------------

REPL_RESERVE_BITS = 14  # 16384 raw draws/replication -- ~16x BSProb's own
                        # ~1000-draw workload, the heaviest built-in g();
                        # exceeding it raises (chnbase.py) rather than
                        # silently overlapping the next replication's block
REPL_COUNT_BITS = 32    # replication index < 2**32 -- unchanged from the
                        # original REPL_BITS: calc_m(200) = 379,810,553
                        # (~2**28.5, checked directly, not assumed -- see
                        # docs/rng-interface-design.md), ~5.6x margin here.
                        # calc_m/calc_b's own float overflow (nu ~7440/
                        # ~3882 respectively -- KNOWN_ISSUES.md issue 12)
                        # makes headroom beyond calc_m(200)'s scale moot:
                        # a solver ever reaching a larger m already fails
                        # via that overflow before hit() sees it
VISIT_BITS = 6          # visit < 2**6 (64) -- shrunk from the original 20 to
                        # make room for REPL_RESERVE_BITS above (the total
                        # non-CRN budget is fixed at 127 bits, shared with
                        # ITER_STRIDE); still zero in-tree callers pass
                        # visit != 0 (§4.1), so this is headroom for a
                        # currently-hypothetical opt-in use, not a measured
                        # requirement like the other three fields -- revisit
                        # if a real caller needs more than 64 independent
                        # resample generations for one point in one iteration
POINT_BITS = 127 - REPL_RESERVE_BITS - REPL_COUNT_BITS - VISIT_BITS  # 75,
                        # unchanged -- BSProb (dim=9, the tightest built-in
                        # problem) still gets W = 75 // 9 = 8


class PointCodeOverflow(ValueError):
    """A point's zigzag-encoded component doesn't fit in the W bits
    this problem's dimension leaves available. Raised, not silently
    reduced mod something -- fail loudly and exactly, the same posture
    MAX_RI moved to when it became a checked constant (KNOWN_ISSUES.md
    issue 3), per §3.4."""


class VisitOverflow(ValueError):
    """`visit` doesn't fit in VISIT_BITS. Same posture as
    PointCodeOverflow -- found during the same audit that found the
    replication-stride defect above (docs/rng-interface-design.md's
    step 8 prerequisite writeup): visit's own bound was documented
    ("Non-negative, < 2**VISIT_BITS") but never enforced, so a caller
    exceeding it would have silently overflowed into point_code's
    zone instead of raising."""


class ReplicationOverflow(ValueError):
    """`replication` doesn't fit in REPL_COUNT_BITS. Same posture and
    same audit as VisitOverflow above -- an unenforced bound that would
    have silently overflowed into visit's zone."""


class ReplicationDrawOverflow(ValueError):
    """A single replication's g() call drew more than
    2**REPL_RESERVE_BITS raw values, overrunning the block reserved
    for it and running into the next replication's own starting
    position -- the defect REPL_RESERVE_BITS exists to prevent (see
    its own comment above). Raised by chnbase.py's
    _hit_via_coordinate, the only place that observes how many raw
    values a replication actually drew; not raised here, since this
    module only assembles coordinates."""


def zigzag(v):
    """
    Bijection Z -> N: 2v for v >= 0, -2v-1 for v < 0.

    Parameters
    ----------
    v : int

    Returns
    -------
    int
        Non-negative.
    """
    return 2 * v if v >= 0 else -2 * v - 1


def point_width(dim, point_bits=POINT_BITS):
    """
    W: bits available per zigzagged component of a point, for a
    problem of dimension `dim` -- `point_bits` split evenly across
    `dim` components. Computed once per Oracle (from its own `dim`
    attribute), not a single fixed constant for every problem.

    Parameters
    ----------
    dim : int
        Must be at least 1.
    point_bits : int
        The calling generator's own offset-budget allocation for the
        point component (module-level `POINT_BITS` by default --
        MRG-family's own 127-bit budget, §3.4). Not every generator
        shares this budget: docs/rng-interface-design.md §12 step
        6c-completion found `offset_within_iteration`/`point_width`
        treated as "generator-agnostic, used identically by every
        backend" when only the MRG family's periods actually have room
        for it -- Philox's own, tighter capacity needs its own
        `point_bits` (see `pymoso.prng.philox4x32.point_width`, which
        calls this function with its own 72-bit figure rather than
        redefining the packing logic).

    Returns
    -------
    int
    """
    if dim < 1:
        raise ValueError('dim must be at least 1, got {0}'.format(dim))
    return point_bits // dim


def point_code(x, W):
    """
    Exact, collision-free integer encoding of a feasible point: each
    component is zigzag-encoded, then packed positionally into one
    integer at radix 2**W (§3.4). Injective on the domain where every
    zigzagged component fits in W bits; a component that doesn't is a
    detectable, per-point failure, raised here rather than silently
    wrapped.

    Parameters
    ----------
    x : tuple of int
    W : int
        Bits available per component -- point_width(len(x)).

    Returns
    -------
    int

    Raises
    ------
    PointCodeOverflow
        Some component's zigzag encoding is >= 2**W.
    """
    limit = 1 << W
    code = 0
    for i, xi in enumerate(x):
        z = zigzag(xi)
        if z >= limit:
            raise PointCodeOverflow(
                'point {0} (dim={1}), component {2}={3} (zigzag {4}) does '
                'not fit in W={5} bits (limit {6}) -- reduce the point\'s '
                'magnitude, encode it differently, or use crn=True, which '
                'never needs x in the coordinate at all. See docs/rng-'
                'interface-design.md §3.4.'.format(i, len(x), i, xi, z, W, limit)
            )
        code += z * (limit ** i)
    return code


def offset_within_iteration(x, visit, replication, W,
                             visit_bits=VISIT_BITS,
                             repl_count_bits=REPL_COUNT_BITS,
                             repl_reserve_bits=REPL_RESERVE_BITS):
    """
    The crn=False branch's non-CRN coordinate component, within one RA
    iteration: point_code(x), `visit`, and `replication` packed into
    one integer, positionally (§3.4). `replication` is multiplied by
    2**repl_reserve_bits, giving each replication a real reserved block
    -- not stride 1, which was this scheme's original defect (see
    REPL_RESERVE_BITS's own comment above): a caller drawing more than
    one raw value per replication (every built-in problem) would
    otherwise run its own consumption into the next replication's
    starting position. Exceeding the reserve is `chnbase.py`'s
    `_hit_via_coordinate`'s responsibility to catch (it's the only
    place that observes how many raw values a replication actually
    drew); this function only ever assembles coordinates, so it cannot
    detect that case itself.

    Parameters
    ----------
    x : tuple of int
    visit : int
        Non-negative, < 2**visit_bits.
    replication : int
        Non-negative, < 2**repl_count_bits.
    W : int
        point_width(len(x), point_bits=<this generator's own point_bits>).
    visit_bits, repl_count_bits, repl_reserve_bits : int
        The calling generator's own offset-budget allocation for each
        field (module-level `VISIT_BITS`/`REPL_COUNT_BITS`/
        `REPL_RESERVE_BITS` by default -- MRG-family's own 127-bit
        budget). §12 step 6c-completion: the offset budget is a
        property of the generator's own capacity (Philox's is 118
        bits, not 127 -- comfortably under its own `COUNTER_BITS=128`,
        not MRG-family's `ITER_STRIDE=2**127`), not shared framework
        state that happened to fit every generator examined so far.
        `pymoso.prng.philox4x32.offset_within_iteration` calls this
        function with its own, tighter figures rather than redefining
        the packing logic.

    Returns
    -------
    int

    Raises
    ------
    PointCodeOverflow
        See point_code.
    VisitOverflow
        `visit` >= 2**visit_bits.
    ReplicationOverflow
        `replication` >= 2**repl_count_bits.
    """
    if visit >= (1 << visit_bits):
        raise VisitOverflow(
            'visit={0} does not fit in VISIT_BITS={1} (limit {2}). See '
            'docs/rng-interface-design.md §3.4.'.format(visit, visit_bits, 1 << visit_bits)
        )
    if replication >= (1 << repl_count_bits):
        raise ReplicationOverflow(
            'replication={0} does not fit in REPL_COUNT_BITS={1} (limit '
            '{2}). See docs/rng-interface-design.md §3.4.'.format(
                replication, repl_count_bits, 1 << repl_count_bits
            )
        )
    return (
        point_code(x, W) * (1 << (visit_bits + repl_count_bits + repl_reserve_bits))
        + visit * (1 << (repl_count_bits + repl_reserve_bits))
        + replication * (1 << repl_reserve_bits)
    )


# ---------------------------------------------------------------------------
# stream_at's coordinate is two-dimensional (§3.9, docs/rng-interface-
# design.md §12 step 6c): `stream` selects an independent, non-overlapping
# stream; `offset` selects a position within it. Every generator's
# stream_at(seed, stream, offset) maps this pair onto its own mechanism
# (flat-integer arithmetic for the MRG family, direct (key, counter)
# indexing for Philox) -- this module holds only the one piece of that
# story that's genuinely generator-agnostic: comparing and advancing
# (stream, offset) pairs themselves.
# ---------------------------------------------------------------------------

class StreamFamilyExceeded(ValueError):
    """Advancing `offset` past its own capacity carries into `stream + 1`
    -- safe only if `stream + 1` still belongs to the same reserved
    family (e.g. the same isp path's own reserved run of iteration
    values). Raised, not silently landed in adjacent, already-allocated
    territory -- the same class of defect MAX_RI's unenforced silent
    overlap was (KNOWN_ISSUES.md issue 3): a boundary that looks safe
    only because nothing has reached it. `stream_family_capacity=None`
    means the caller has deliberately chosen not to bound this family
    (documented per call site, e.g. MRG's own sync axis relies on
    remaining period headroom instead, §8.2) -- one_past never raises
    in that case."""


def one_past(stream, offset, offset_capacity, stream_family_capacity):
    """
    The high-water-mark pair one past `(stream, offset)` -- §8.2's "one
    past the maximum coordinate touched," generalized from a flat
    integer to a `(stream, offset)` pair. `offset + 1` is returned
    directly unless it would reach `offset_capacity` (this stream's own
    width), in which case it carries to `(stream + 1, 0)` -- exactly
    the carry a flat integer's own `+1` already does automatically
    (`stream*STRIDE + offset + 1` rolling over into `(stream+1)*STRIDE`
    when `offset+1 == STRIDE`), made explicit here since there is no
    single flat integer to carry within any more.

    The carry is checked, not assumed safe: `stream + 1` must still be
    less than `stream_family_capacity` (how many `stream` values this
    family reserves -- e.g. how many iterations one isp path's own
    slot holds) or this raises `StreamFamilyExceeded` rather than
    silently returning a pair that lands in adjacent, differently-
    owned territory.

    Parameters
    ----------
    stream : int
        Non-negative.
    offset : int
        Non-negative, < `offset_capacity`.
    offset_capacity : int
        Positive. This stream's own offset width.
    stream_family_capacity : int or None
        Positive, or `None` to skip the carry-target check entirely
        (the caller has its own reason the family is unbounded here,
        stated at the call site).

    Returns
    -------
    tuple of int
        `(stream, offset)`, advanced by one.

    Raises
    ------
    StreamFamilyExceeded
        The carry would produce `stream + 1 >= stream_family_capacity`.
    """
    if offset + 1 < offset_capacity:
        return stream, offset + 1
    if stream_family_capacity is not None and stream + 1 >= stream_family_capacity:
        raise StreamFamilyExceeded(
            'advancing past (stream={0}, offset={1}) would carry to '
            'stream={2}, which does not fit in this family\'s own '
            'capacity of {3}. See docs/rng-interface-design.md §12 '
            'step 6c.'.format(stream, offset, stream + 1, stream_family_capacity)
        )
    return stream + 1, 0
