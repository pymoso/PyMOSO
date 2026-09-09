"""
The generator-agnostic pieces of docs/rng-interface-design.md's RNG
interface: the Stream protocol every conforming backend must satisfy
(§3.2), the backward-compatibility adapter (§3.6) that lets a Stream be
used anywhere a random.Random-shaped object is expected, and the
non-CRN coordinate-assembly functions (point_code/offset_within_
iteration, §3.4) -- pure integer arithmetic, generator-agnostic, used
identically by every backend's crn=False branch.

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

    Not yet used by MRG32k3a itself (see module docstring) -- this class
    exists so the pattern is written down and testable ahead of that
    wiring, not because anything constructs one yet.
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

    def random(self) -> float:
        return self._stream.random()

    def getrandbits(self, k: int) -> int:
        return self._stream.getrandbits(k)

    def normalvariate(self, mu: float = 0, sigma: float = 1) -> float:
        return self._stream.normalvariate(mu, sigma)


# ---------------------------------------------------------------------------
# Non-CRN coordinate assembly (§3.4). Exact, collision-free by
# construction -- not a hash, not probabilistic (see §3.4's "what does
# work, exactly, with no probability involved" for why a hash-based
# scheme was ruled out). Sizing: ITER_STRIDE (2**127) is split three
# ways -- REPL_BITS for replication, VISIT_BITS for visit, the rest
# (POINT_BITS) for the point itself, adaptively divided across a
# problem's own dimension as W bits per component.
# ---------------------------------------------------------------------------

REPL_BITS = 32
VISIT_BITS = 20
POINT_BITS = 127 - REPL_BITS - VISIT_BITS  # 75


class PointCodeOverflow(ValueError):
    """A point's zigzag-encoded component doesn't fit in the W bits
    this problem's dimension leaves available. Raised, not silently
    reduced mod something -- fail loudly and exactly, the same posture
    MAX_RI moved to when it became a checked constant (KNOWN_ISSUES.md
    issue 3), per §3.4."""


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


def point_width(dim):
    """
    W: bits available per zigzagged component of a point, for a
    problem of dimension `dim` -- POINT_BITS split evenly across
    `dim` components. Computed once per Oracle (from its own `dim`
    attribute), not a single fixed constant for every problem.

    Parameters
    ----------
    dim : int
        Must be at least 1.

    Returns
    -------
    int
    """
    if dim < 1:
        raise ValueError('dim must be at least 1, got {0}'.format(dim))
    return POINT_BITS // dim


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


def offset_within_iteration(x, visit, replication, W):
    """
    The crn=False branch's non-CRN coordinate component, within one RA
    iteration: point_code(x) and `visit` and `replication` packed into
    one integer, positionally, at fixed VISIT_BITS/REPL_BITS widths
    (§3.4). Not yet wired into chnbase.py (that's step 4a/4b); this is
    the pure-function layer §7.1 items 8-9 test directly.

    Parameters
    ----------
    x : tuple of int
    visit : int
        Non-negative, < 2**VISIT_BITS.
    replication : int
        Non-negative, < 2**REPL_BITS.
    W : int
        point_width(len(x)).

    Returns
    -------
    int

    Raises
    ------
    PointCodeOverflow
        See point_code.
    """
    return (
        point_code(x, W) * (1 << (VISIT_BITS + REPL_BITS))
        + visit * (1 << REPL_BITS)
        + replication
    )
