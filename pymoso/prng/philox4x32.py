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

Capacity (docs/rng-interface-design.md §3.9/§12 step 6): `stream_at`'s
single flat `coordinate` (matching the same shape the MRG-family suite
uses -- the real (stream, offset) split is step 6c, not this step) is
split into a 128-bit counter (low bits) and a key offset (high bits,
added mod 2**64 to the seed-derived base key), giving a combined
addressable space of 2**192 -- comparable to the MRG family's own
periods once "which stream" and "position within it" are kept separate
rather than forced through one dimension sized for the smaller of the
two. `coordinate >= 2**192` raises `CoordinateCapacityExceeded` rather
than silently wrapping.

Listing
-------
Philox4x32Stream
philox4x32_r
stream_at
CoordinateCapacityExceeded
"""

from .mrg32k3a import bsm

# Sourced from Random123's philox.h (see module docstring).
_M0 = 0xD2511F53
_M1 = 0xCD9E8D57
_W0 = 0x9E3779B9
_W1 = 0xBB67AE85
_MASK32 = 0xFFFFFFFF

DEFAULT_ROUNDS = 10

COUNTER_BITS = 128   # Philox4x32's native counter width
KEY_BITS = 64        # Philox4x32's native key width
CAPACITY_BITS = COUNTER_BITS + KEY_BITS  # 192, this module's own chosen
                                          # combined addressable space --
                                          # see module docstring


class CoordinateCapacityExceeded(ValueError):
    """`coordinate` in stream_at(seed, coordinate) is >= 2**192 (this
    module's own chosen combined key+counter capacity, docs/rng-
    interface-design.md §12 step 6) -- raised, not silently wrapped mod
    2**192, the same "fail loudly and exactly" posture point_code's own
    overflow check established (pymoso/prng/base.py)."""


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


def stream_at(seed, coordinate):
    """
    §3.1's stream_at, for Philox4x32: direct (key, counter) indexing,
    no jump-ahead computed at all -- confirming §3.5's own claim under
    a genuinely different generator construction (MRG32k3a/MRG31k3p
    reach a coordinate by computing how far to jump from a fixed start;
    this reaches it by indexing directly).

    `coordinate`'s low 128 bits become the starting counter; its
    remaining high bits are added, mod 2**64, to `seed`'s own base key
    -- an exact positional split (§3.9), not a hash, so distinct
    coordinates within capacity yield distinct (key, counter) pairs by
    construction. `coordinate >= 2**192` raises CoordinateCapacityExceeded
    rather than silently wrapping (module docstring).

    Parameters
    ----------
    seed : tuple of int, length 2
        The base key, each entry in [0, 2**32) -- Philox4x32's own
        generator-shaped seed (§3.7): 2 non-negative ints, not a
        6-tuple, since nothing about this generator's own structure
        calls for one.
    coordinate : int
        Non-negative, < 2**192 (CAPACITY_BITS).

    Returns
    -------
    Philox4x32Stream

    Raises
    ------
    ValueError
        `coordinate` is negative.
    CoordinateCapacityExceeded
        `coordinate` >= 2**192.
    """
    if coordinate < 0:
        raise ValueError('coordinate must be non-negative, got {0}'.format(coordinate))
    if coordinate >= (1 << CAPACITY_BITS):
        raise CoordinateCapacityExceeded(
            'coordinate={0} does not fit in this module\'s chosen capacity '
            'of 2**{1} (a 2**{2}-bit counter plus a 2**{3}-bit key offset). '
            'See docs/rng-interface-design.md §12 step 6.'.format(
                coordinate, CAPACITY_BITS, COUNTER_BITS, KEY_BITS
            )
        )
    counter_int = coordinate & ((1 << COUNTER_BITS) - 1)
    key_offset = coordinate >> COUNTER_BITS
    base_key_int = (seed[0] << 32) | seed[1]
    eff_key_int = (base_key_int + key_offset) & ((1 << KEY_BITS) - 1)
    key = _int_to_words(eff_key_int, 2)
    counter = _int_to_words(counter_int, 4)
    return Philox4x32Stream(key, counter)
