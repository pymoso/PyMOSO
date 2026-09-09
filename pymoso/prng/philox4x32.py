#!/usr/bin/env python
"""
Summary
-------
Philox4x32-10 (Salmon, Moraes, Dror & Shaw 2011, "Parallel Random
Numbers: As Easy as 1, 2, 3"): a counter-based generator, onboarded per
docs/rng-interface-design.md §12 step 6 -- the interface's real test,
since Philox has no recurrence, no "advancing" state, and no jump-ahead
at all. `stream_at` reaches a position by direct (key, counter)
indexing, not by computing how far to jump from a fixed start.

Every constant is sourced from Random123 (github.com/DEShawResearch/
random123, John Salmon's own reference implementation; mirrored at
thesalmons.org), corroborated independently by the C++ standardization
proposal P2075 ("Philox as an extension of the C++ RNG engines"), which
states the same constants. The round function below was validated
against Random123's own published known-answer-test vectors
(tests/kat_vectors in that repository) at 10 rounds, three inputs
(all-zero, all-0xffffffff, and the "pi digits" vector) -- bit-for-bit
matches, not merely self-consistent. See
docs/rng-interface-design.md's step 6 entry for the full sourcing and
capacity-sizing account.

Round count: 10 (`PHILOX4x32_DEFAULT_ROUNDS` in Random123 itself), the
library default and the value "Philox4x32" means throughout the
ecosystem (numpy, PyTorch, the C++ proposal) -- not the statistical
minimum (Salmon et al. 2011 report BigCrush passing at 7).

Philox4x32Stream implements only pymoso/prng/base.py's Stream protocol
(random/getrandbits/normalvariate) -- deliberately not a random.Random
subclass, unlike MRG32k3a/MRG31k3p. base.RandomCompatAdapter exists
exactly for a caller that needs the full random.Random surface on top
of a bare Stream; this is that pattern's first real user, not a second,
divergent convention.

Coordinate shape (docs/rng-interface-design.md §3.9/§12 step 6c):
`stream_at(seed, stream, offset)` maps `stream` directly onto the key
(added, mod 2**64, to `seed`'s own base key) and `offset` directly onto
the counter -- no jump-ahead, no flattening into one integer first.
`OFFSET_CAPACITY` (2**118) and the stream-side family constants below
(`ISP_ITER_MARGIN`, `SYNC_ROLE_OFFSET`, mirroring mrg32k3a.py's own
names for the same roles) are this module's own chosen policy numbers,
sized against budget-anchored ceilings (not period-anchored ones, since
nothing in the framework bounds replications/iteration or
iterations/run beyond `--budget`) -- see docs/rng-interface-design.md's
step 6/6c entries for the full sizing account and the reasoning behind
each figure. `stream >= 2**KEY_BITS` or `offset >= 2**COUNTER_BITS`
raises `CoordinateCapacityExceeded` rather than silently wrapping; this
module's own family-capacity constants exist for callers to pass to
`pymoso.prng.base.one_past`, which enforces the *narrower*, framework-
level boundaries (e.g. one isp path's own reserved iteration range)
this module has no way to know about on its own.

Listing
-------
Philox4x32Stream
philox4x32_r
stream_at
point_width
offset_within_iteration
CoordinateCapacityExceeded
"""

from .mrg32k3a import bsm
from .base import (
    point_width as _base_point_width,
    offset_within_iteration as _base_offset_within_iteration,
)

# Sourced from Random123's philox.h (see module docstring).
_M0 = 0xD2511F53
_M1 = 0xCD9E8D57
_W0 = 0x9E3779B9
_W1 = 0xBB67AE85
_MASK32 = 0xFFFFFFFF

DEFAULT_ROUNDS = 10

COUNTER_BITS = 128   # Philox4x32's own native counter width
KEY_BITS = 64        # Philox4x32's own native key width

# ---------------------------------------------------------------------------
# Chosen policy numbers (docs/rng-interface-design.md §12 step 6/6c) --
# not derived, budget-anchored the same way step 6's own REPL_RESERVE_BITS/
# REPL_COUNT_BITS were. Mirrors mrg32k3a.py's own offset_within_iteration/
# ISP_STRIDE/SYNC_ROLE_OFFSET structure exactly, at the (stream, offset)
# level instead of one flat integer's bit-fields.
# ---------------------------------------------------------------------------

# Offset side: point(72) + visit(4) + replication count(30) +
# replication reserve(12) = 118 bits, comfortably under COUNTER_BITS
# (2**10 margin) -- step 6's own figures, restated here as the single
# OFFSET_CAPACITY a caller needs for one_past's own offset_capacity
# argument.
#
# §12 step 6c-completion, correcting step 6c's own report: these four
# figures were documented here as "step 6's own figures" from the start,
# but until this step nothing in the codebase actually packed an offset
# against them -- the only offset_within_iteration/point_width that
# existed was pymoso.prng.base's, sized to MRG-family's 127-bit budget
# (point 75/visit 6/repl-count 32/repl-reserve 14). An offset built that
# way and handed to this module's own stream_at raised nothing: stream_
# at's own bounds check is against COUNTER_BITS (2**128, the raw
# hardware limit), not OFFSET_CAPACITY -- so an offset in [2**118,
# 2**127) silently exceeded this module's own declared capacity with no
# exception anywhere (tests/test_philox_offset_budget.py's own
# test_shared_base_budget_silently_exceeds_philox_own_capacity confirms
# this directly). POINT_BITS/VISIT_BITS/REPL_COUNT_BITS/
# REPL_RESERVE_BITS below, plus this module's own point_width/
# offset_within_iteration, are what actually wire these four figures
# into real checks -- point_width(dim) and offset_within_iteration(...)
# now reject an oversized point/visit/replication with the correctly-
# scoped PointCodeOverflow/VisitOverflow/ReplicationOverflow, at
# assembly time, before stream_at ever sees it.
#
# NOT YET WIRED IN: chnbase.py's own coordinate assembly (Oracle.
# _hit_via_coordinate) still calls pymoso.prng.base.point_width/
# offset_within_iteration unconditionally, with no generator-selection
# argument at all -- nothing anywhere in the framework calls this
# module's point_width/offset_within_iteration below yet. This step
# only builds the mechanism and proves it correct in isolation, the
# same posture step 5/6 already established for onboarding a generator
# ahead of its own CLI reachability. §12 step 6b (not yet landed) is
# what threads a selected generator through Oracle's own internals so
# this budget is actually honored on a real solve()/testsolve() run --
# until then, Philox remains not usable for real solving through this
# codebase's own coordinate path, only through direct, standalone
# stream_at calls, exactly as before this step.
OFFSET_CAPACITY = 1 << 118

POINT_BITS = 72
VISIT_BITS = 4
REPL_COUNT_BITS = 30
REPL_RESERVE_BITS = 12
assert POINT_BITS + VISIT_BITS + REPL_COUNT_BITS + REPL_RESERVE_BITS == 118
assert OFFSET_CAPACITY == 1 << (POINT_BITS + VISIT_BITS + REPL_COUNT_BITS + REPL_RESERVE_BITS)

# Stream side, mirroring mrg32k3a.py's ISP_ITER_MARGIN (how many
# iterations one isp path's own slot reserves) and SYNC_ROLE_OFFSET
# (where the sync zone begins) -- both far smaller than MRG's own
# 2**32/2**175 equivalents, because Philox's 64-bit key is far smaller
# than MRG's own period, not because this module needs less headroom
# for the same realistic usage. Both still comfortably clear the
# budget-anchored ceilings they're sized against (10**9 iterations,
# 10,000 isp paths): ISP_ITER_MARGIN gives 2**30 (~1.07e9, >10**9
# iterations before the next isp path's own slot begins) and
# SYNC_ROLE_OFFSET leaves 2**64 - 2**48 ~= 2**64 of key space for sync
# values -- 2**16 (65,536x) of margin beyond ISP_ITER_MARGIN itself.
ISP_ITER_MARGIN = 1 << 30
SYNC_ROLE_OFFSET = 1 << 48


def point_width(dim):
    """
    W: bits available per zigzagged component of a point, using this
    module's own 72-bit point budget (POINT_BITS above) -- not
    pymoso.prng.base's 75-bit MRG-family one (§12 step 6c-completion).
    Delegates to pymoso.prng.base.point_width for the actual division;
    only the budget passed in differs.

    Parameters
    ----------
    dim : int
        Must be at least 1.

    Returns
    -------
    int
    """
    return _base_point_width(dim, point_bits=POINT_BITS)


def offset_within_iteration(x, visit, replication, W):
    """
    This module's own offset assembly, using its own 118-bit budget
    (VISIT_BITS/REPL_COUNT_BITS/REPL_RESERVE_BITS above) -- not
    pymoso.prng.base's 127-bit MRG-family one (§12 step 6c-completion).
    Delegates to pymoso.prng.base.offset_within_iteration for the
    actual packing and overflow checks; only the budget passed in
    differs, so an oversized point/visit/replication raises the same
    PointCodeOverflow/VisitOverflow/ReplicationOverflow those checks
    already provide, just scoped to this generator's real capacity
    instead of a different generator's larger one.

    Parameters
    ----------
    x : tuple of int
    visit : int
        Non-negative, < 2**VISIT_BITS.
    replication : int
        Non-negative, < 2**REPL_COUNT_BITS.
    W : int
        point_width(len(x)) -- this module's own version, above.

    Returns
    -------
    int

    Raises
    ------
    PointCodeOverflow
    VisitOverflow
    ReplicationOverflow
    """
    return _base_offset_within_iteration(
        x, visit, replication, W,
        visit_bits=VISIT_BITS,
        repl_count_bits=REPL_COUNT_BITS,
        repl_reserve_bits=REPL_RESERVE_BITS,
    )


class CoordinateCapacityExceeded(ValueError):
    """`stream`/`offset` in stream_at(seed, stream, offset) don't fit
    in this generator's own native key/counter widths -- raised, not
    silently wrapped, the same "fail loudly and exactly" posture
    `point_code`'s own overflow check established (pymoso/prng/base.py).
    This is this module's own generator-level capacity check only; the
    narrower, framework-level family boundaries (docs/rng-interface-
    design.md §12 step 6c) are `pymoso.prng.base.one_past`'s job, using
    `ISP_ITER_MARGIN`/`SYNC_ROLE_OFFSET` above."""


def _mulhilo32(a, b):
    """32x32 -> 64-bit product, split into (high, low) 32-bit halves --
    Python ints are arbitrary precision, so this is exact, no emulated
    overflow needed (unlike a fixed-width-int reference implementation).

    Parameters
    ----------
    a : int
    b : int
        Both in [0, 2**32).

    Returns
    -------
    hi : int
    lo : int
        Both in [0, 2**32).
    """
    p = a * b
    return (p >> 32) & _MASK32, p & _MASK32


def _philox4x32_round(ctr, key):
    """One Philox4x32 round -- the one and only place these coefficients
    are stated, derived directly from Random123's own philox.h (see
    module docstring for the sourcing and validation account).

    Parameters
    ----------
    ctr : tuple of int, length 4
    key : tuple of int, length 2
        All entries in [0, 2**32).

    Returns
    -------
    tuple of int, length 4
    """
    hi0, lo0 = _mulhilo32(_M0, ctr[0])
    hi1, lo1 = _mulhilo32(_M1, ctr[2])
    return (hi1 ^ ctr[1] ^ key[0], lo1, hi0 ^ ctr[3] ^ key[1], lo0)


def _philox4x32_bumpkey(key):
    """Advance the key by one Weyl step. Parameters/Returns: as
    _philox4x32_round's own key."""
    return ((key[0] + _W0) & _MASK32, (key[1] + _W1) & _MASK32)


def philox4x32_r(rounds, ctr, key):
    """
    Philox4x32-R: `rounds` applications of _philox4x32_round, bumping
    the key before every round after the first (round 1 uses the
    unbumped key) -- the exact structure Random123's own philox4x32_R
    uses, validated against its own published known-answer-test
    vectors at rounds=10 (module docstring).

    Parameters
    ----------
    rounds : int
        Non-negative.
    ctr : tuple of int, length 4
    key : tuple of int, length 2
        All entries in [0, 2**32).

    Returns
    -------
    tuple of int, length 4
        The output block, every entry in [0, 2**32).
    """
    if rounds <= 0:
        return tuple(ctr)
    ctr = _philox4x32_round(ctr, key)
    for _ in range(1, rounds):
        key = _philox4x32_bumpkey(key)
        ctr = _philox4x32_round(ctr, key)
    return ctr


class Philox4x32Stream:
    """
    A Stream (pymoso/prng/base.py) backed by Philox4x32-10, fixed at a
    given (key, counter) -- reached via stream_at below, never
    constructed directly by a caller that wants the interface's own
    guarantees (§3.1).

    Draws are produced 4 words (one block) at a time, buffered, and
    consumed low-word-first; the counter is incremented by 1 (mod
    2**128) whenever the buffer is exhausted and refilled. A single
    stream's own counter therefore only ever moves within the 2**128
    block range stream_at handed it -- staying inside the same key for
    its entire lifetime, exactly as Random123's own key/counter roles
    intend (key = which stream, counter = position within it).

    Parameters
    ----------
    key : tuple of int, length 2
    counter : tuple of int, length 4
        Both entries in [0, 2**32) per component; the starting counter
        block this stream draws from first.
    """

    def __init__(self, key, counter):
        self._key = tuple(key)
        self._counter = list(counter)
        self._buffer = []

    def _increment_counter(self):
        for i in range(4):
            self._counter[i] = (self._counter[i] + 1) & _MASK32
            if self._counter[i] != 0:
                break
            # else: this word wrapped to 0, carry into the next --
            # exhausting the full 2**128 counter range would take more
            # raw draws than any run in this project ever will (see
            # docs/rng-interface-design.md §12 step 6's own REPL_RESERVE
            # sizing); no overflow check here for the same reason
            # MRG32k3a's own period wraparound isn't checked in code,
            # only documented (§8.2).

    def _refill(self):
        self._buffer = list(philox4x32_r(DEFAULT_ROUNDS, tuple(self._counter), self._key))
        self._increment_counter()

    def _next_word(self):
        """One raw, exactly-uniform 32-bit word."""
        if not self._buffer:
            self._refill()
        return self._buffer.pop(0)

    def random(self):
        """
        Uniform on [0, 1) -- one raw word, exact-by-construction (a
        power-of-two-ranged word divided by that same power of two).

        Returns
        -------
        float
        """
        return self._next_word() / 4294967296.0  # 2**32

    def getrandbits(self, k):
        """
        Uniform on [0, 2**k), unbiased with no rejection needed --
        unlike MRG32k3a/MRG31k3p's own getrandbits (mrgm1i/mrg31m1 are
        not powers of two, so their digit-concatenation scheme must
        reject the biased remainder), Philox's own raw words are
        already exactly 2**32-ranged: concatenating whole words
        (shift-and-OR, each word independent and exactly uniform) and
        truncating the result to k bits only ever drops high-order bits
        from the last word contributed, which cannot bias the
        lower-order bits that remain -- still exactly uniform, per
        §7 item 5.

        Parameters
        ----------
        k : int
            Number of bits requested, > 0.

        Returns
        -------
        int
            Uniform over [0, 2**k).
        """
        if k <= 0:
            raise ValueError('number of bits must be greater than zero')
        bits = 0
        nbits = 0
        while nbits < k:
            bits |= self._next_word() << nbits
            nbits += 32
        return bits & ((1 << k) - 1)

    def normalvariate(self, mu=0, sigma=1):
        """
        A monotone, single-draw transform of one random() draw (§3.3),
        via the same bsm() every generator in this codebase uses --
        generator-agnostic by construction, imported not copied.

        Parameters
        ----------
        mu : float
        sigma : float

        Returns
        -------
        float
        """
        u = self.random()
        z = bsm(u)
        return sigma * z + mu

    def get_seed(self):
        """
        The stream's full internal state -- key, current counter
        position, and any buffered-but-unconsumed words -- as a
        hashable, comparable tuple. Not part of §3.2's required Stream
        surface; provided because the §7 conformance suite's own
        reusable checks (tests/test_prng_conformance.py's own
        check_distinctness) compare two streams' "landed state," the
        same way they do for MRG32k3a/MRG31k3p.

        Returns
        -------
        tuple
        """
        return (self._key, tuple(self._counter), tuple(self._buffer))


def _int_to_words(n, count):
    """Split a non-negative int into `count` 32-bit words, most-
    significant first -- an exact, collision-free positional radix
    decomposition (the same posture point_code already established),
    not a hash. `n` must be < 2**(32*count).

    Parameters
    ----------
    n : int
    count : int

    Returns
    -------
    tuple of int, length `count`
    """
    words = []
    for i in range(count - 1, -1, -1):
        words.append((n >> (32 * i)) & _MASK32)
    return tuple(words)


def stream_at(seed, stream, offset):
    """
    §3.9's two-dimensional coordinate, for Philox4x32: `stream` maps
    directly onto the key (added, mod 2**64, to `seed`'s own base key);
    `offset` maps directly onto the counter. No jump-ahead computed at
    all -- confirming §3.5's own claim under a genuinely different
    generator construction (MRG32k3a/MRG31k3p reach a coordinate by
    computing how far to jump from a fixed start; this reaches it by
    indexing directly). `stream`/`offset` are added via exact modular
    arithmetic, not a hash, so distinct pairs within capacity yield
    distinct (key, counter) pairs by construction -- the same "exact,
    collision-free by construction" posture `point_code` established.

    `offset >= OFFSET_CAPACITY` (2**128, the counter's own native
    width) or `stream >= 2**KEY_BITS` (this generator's own ultimate
    key capacity) raises `CoordinateCapacityExceeded` rather than
    silently wrapping. This is a generator-level safety net only --
    it does not know about, or enforce, the *framework*-level family
    boundaries (e.g. how many iterations one isp path reserves); that
    is `pymoso.prng.base.one_past`'s own job, checked by the caller
    before `stream` ever reaches this function (docs/rng-interface-
    design.md §12 step 6c).

    Parameters
    ----------
    seed : tuple of int, length 2
        The base key, each entry in [0, 2**32) -- Philox4x32's own
        generator-shaped seed (§3.7): 2 non-negative ints, not a
        6-tuple, since nothing about this generator's own structure
        calls for one.
    stream : int
        Non-negative, < 2**64 (KEY_BITS).
    offset : int
        Non-negative, < 2**128 (COUNTER_BITS, this generator's own
        `OFFSET_CAPACITY`).

    Returns
    -------
    Philox4x32Stream

    Raises
    ------
    ValueError
        `stream` or `offset` is negative.
    CoordinateCapacityExceeded
        `stream >= 2**64` or `offset >= 2**128`.
    """
    if stream < 0:
        raise ValueError('stream must be non-negative, got {0}'.format(stream))
    if offset < 0:
        raise ValueError('offset must be non-negative, got {0}'.format(offset))
    if offset >= (1 << COUNTER_BITS):
        raise CoordinateCapacityExceeded(
            'offset={0} does not fit in this generator\'s own counter '
            'width of 2**{1}. See docs/rng-interface-design.md §12 '
            'step 6c.'.format(offset, COUNTER_BITS)
        )
    if stream >= (1 << KEY_BITS):
        raise CoordinateCapacityExceeded(
            'stream={0} does not fit in this generator\'s own key width '
            'of 2**{1}. See docs/rng-interface-design.md §12 step '
            '6c.'.format(stream, KEY_BITS)
        )
    base_key_int = (seed[0] << 32) | seed[1]
    eff_key_int = (base_key_int + stream) & ((1 << KEY_BITS) - 1)
    key = _int_to_words(eff_key_int, 2)
    counter = _int_to_words(offset, 4)
    return Philox4x32Stream(key, counter)
