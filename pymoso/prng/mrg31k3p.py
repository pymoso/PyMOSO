#!/usr/bin/env python
"""
Summary
-------
MRG31k3p (L'Ecuyer & Touzin 2000): a second combined multiple recursive
generator, onboarded per docs/rng-interface-design.md §12 step 5 -- the
interface's first real test against a generator other than MRG32k3a.

Every constant below is sourced from L'Ecuyer's own SSJ library
(github.com/umontreal-simul/ssj, src/main/java/umontreal/ssj/rng/
MRG31k3p.java) -- not from the original paper directly (not fetched),
and not inferred from MRG32k3a by analogy. The recurrence was derived
two independent ways from that same source file (decoding its fast
bit-shift step implementation, and cross-checking against its own
separately-published exact one-step jump matrices) and the two agreed
exactly. Full sourcing account, the period figure and its residual
(deliberately unchased) ambiguity, and the coordinate-constant margin
arithmetic are all in docs/rng-interface-design.md's step 5 entry, not
repeated here.

Unlike mrg32k3a()'s own single-step recurrence (float arithmetic, for
historical/legacy consistency), mrg31k3p() below uses exact Python
integer arithmetic throughout -- MRG31k3p's coefficients are small
enough (2^22, 129, 2^15, 32769) and Python ints are arbitrary-precision,
so there is no reason to introduce float round-trip risk here at all,
unlike the jump-ahead *matrices* KNOWN_ISSUES.md issue 1 is about (which
this module never touches in float form either -- jump_seed_n below is
mrg_common.mat_pow_mod end to end, exact integers throughout, same as
mrg32k3a.py's own generalized jump).

REPL_STRIDE/ITER_STRIDE/OFFSET_CAPACITY/ISP_ITER_MARGIN/ISP_STRIDE/
SYNC_ROLE_OFFSET/SYNC_ZONE_STREAM_START/SYNC_STRIDE are all reused
directly from mrg32k3a.py, not redefined here: docs/rng-interface-
design.md's step 5 entry works out that every existing coordinate
constant (sized against MRG32k3a's period, ~2**191) stays safely under
MRG31k3p's own, much smaller period (~2**185) -- confirmed by direct
computation, not assumed, so these stay global constants rather than
becoming per-generator ones. Re-exported under this module's own name
(§12 step 6b) so chnbase.py can look them up uniformly as
`backend.CONSTANT` regardless of which MRG-family generator is
selected, without needing to know they happen to be the same object.

This module did not originally wire MRG31k3p into chnbase.py's
coordinate machinery or into any CLI/library selection surface -- that
landed at step 6b (docs/rng-interface-design.md §12), not this step,
and includes REPL_RESERVE_STRIDE's own cached matrices below (added at
6b, once chnbase.py's _hit_via_coordinate actually called this
generator's replication-coordinate path -- see that constant's own
comment for why adding it speculatively, ahead of a real caller, would
have been premature at this step).

Listing
-------
MRG31k3p
mrg31k3p
get_next_prnstream
jump_substream
jump_seed_n
stream_at
point_width
offset_within_iteration
validate_seed
DEFAULT_SEED
"""

import random

from .mrg32k3a import (
    bsm, REPL_STRIDE, ITER_STRIDE, REPL_RESERVE_BITS, REPL_RESERVE_STRIDE,
    OFFSET_CAPACITY, ISP_ITER_MARGIN, ISP_STRIDE, SYNC_ROLE_OFFSET,
    SYNC_ZONE_STREAM_START, SYNC_STRIDE, point_width, offset_within_iteration,
)
from .mrg_common import (
    mat333mult as _mat333mult,
    mat311mod as _mat311mod,
    mat_pow_mod as _mat_pow_mod,
    jump_n as _jump_n,
)

# Sourced from umontreal-simul/ssj's MRG31k3p.java (see module docstring).
mrg31m1 = 2147483647          # 2**31 - 1, a Mersenne prime
mrg31m2 = 2147462579          # 2**31 - 21069
mrg31norm = 2.0 ** -31         # NOT 1/mrg31m1 -- matches SSJ's own literal
                               # (4.656612873077392578125e-10) exactly.
                               # Deliberately smaller than 1/mrg31m1 so the
                               # raw-difference boundary case (mrg31m1
                               # itself) normalizes strictly below 1.0 --
                               # the source's own "must never return either
                               # 0 or 1" invariant, achieved by this choice
                               # of normalizer, not by clamping output.

# One-step transition matrices, same state-vector convention mrg32k3a.py's
# _m1_step/_m2_step use: seed[0:3]/seed[3:6], oldest-to-newest, recurrence
# coefficients in the matrix's own last row. Derived directly from
# mrg31k3p()'s two update lines below (the one and only place these
# coefficients are stated), not transcribed from a second source.
_m1_step = [[0, 1, 0], [0, 0, 1], [129, 4194304, 0]]
_m2_step = [[0, 1, 0], [0, 0, 1], [32769, 0, 32768]]

# Computed once, at import time -- same regression this module's sibling
# guards against (mrg32k3a.py's own comment above _jump_replreserve_p1
# explains the measured cost of not doing this).
#
# §12 step 6b: REPL_RESERVE_STRIDE's own cached matrices, added here --
# absent until this step (see module docstring's original "There is
# deliberately no REPL_RESERVE_STRIDE-cached jump here" note), because
# nothing called this generator's replication-coordinate path before
# step 6b actually threaded a selected backend through chnbase.py's
# _hit_via_coordinate. Uncached, MRG31k3p.advance(REPL_RESERVE_STRIDE)
# (the default/offset branch's own per-replication step) would fall
# through jump_seed_n's general binary-exponentiation path on every
# replication -- the same O(log n)-per-call shape step 2's own
# regression was, reproduced here for this generator specifically had
# this not been added; timed directly, not assumed, once threaded in.
_jump76_p1 = _mat_pow_mod(_m1_step, REPL_STRIDE, mrg31m1)
_jump76_p2 = _mat_pow_mod(_m2_step, REPL_STRIDE, mrg31m2)
_jump127_p1 = _mat_pow_mod(_m1_step, ITER_STRIDE, mrg31m1)
_jump127_p2 = _mat_pow_mod(_m2_step, ITER_STRIDE, mrg31m2)
_jump_replreserve_p1 = _mat_pow_mod(_m1_step, REPL_RESERVE_STRIDE, mrg31m1)
_jump_replreserve_p2 = _mat_pow_mod(_m2_step, REPL_RESERVE_STRIDE, mrg31m2)


def mrg31k3p(seed):
    """
    Generate a random number between 0 and 1 from a seed, exact integer
    arithmetic throughout (see module docstring for why this differs
    from mrg32k3a()'s float-based step).

    Parameters
    ----------
    seed : tuple of int
        Length must be 6.

    Returns
    -------
    newseed : tuple of int
    u : float
    """
    x1n = (4194304 * seed[1] + 129 * seed[0]) % mrg31m1
    x2n = (32768 * seed[5] + 32769 * seed[3]) % mrg31m2
    if x1n <= x2n:
        u = (x1n - x2n + mrg31m1) * mrg31norm
    else:
        u = (x1n - x2n) * mrg31norm
    newseed = (seed[1], seed[2], x1n, seed[4], seed[5], x2n)
    return newseed, u


# §3.7/§12 step 6b: this generator's own default seed -- proposed and
# approved as (12345,)*6, the same value/shape as MRG32k3a's own
# default: nothing about MRG31k3p calls for a different one, and this
# keeps every registered generator's default recognizable from the
# same example number.
DEFAULT_SEED = (12345, 12345, 12345, 12345, 12345, 12345)


def validate_seed(tokens):
    """
    §3.2/§3.7: validate raw --seed tokens against MRG31k3p's own shape
    -- exactly 6 integers, the same shape as MRG32k3a's (see that
    module's own validate_seed for the full division-of-responsibility
    rationale).

    Parameters
    ----------
    tokens : sequence of str or int

    Returns
    -------
    tuple of int, length 6

    Raises
    ------
    ValueError
        Wrong count, or a token that isn't an integer -- named against
        this generator specifically ("mrg31k3p expects 6 integers, got
        4"), per §3.7.
    """
    tokens = tuple(tokens)
    if len(tokens) != 6:
        raise ValueError('mrg31k3p expects 6 integers, got {0}.'.format(len(tokens)))
    try:
        return tuple(int(t) for t in tokens)
    except (TypeError, ValueError):
        raise ValueError(
            'mrg31k3p expects 6 integers, got non-integer token(s) in {0!r}.'.format(tokens)
        )


class MRG31k3p(random.Random):
    """
    Implements MRG31k3p as the generator for a random.Random object --
    structurally a close sibling of MRG32k3a (see that class's own
    docstring for the methods mirrored here).

    Attributes
    ----------
    _current_seed : tuple of int
        6 integer MRG31k3p seed

    Parameters
    ----------
    x : tuple of int, optional
        Seed from which to start the generator. Default (12345,)*6,
        matching SSJ's own stated default exactly.

    See also
    --------
    mrg32k3a.MRG32k3a
    """

    def __init__(self, x=None):
        if not x:
            x = DEFAULT_SEED
        assert(len(x) == 6)
        super().__init__(x)

    def _sync_parent_state(self, a):
        """
        Update _current_seed and the parent random.Random's own state to
        match -- shared by seed() and _advance(), which differ only in
        whether raw_consumed() resets. See MRG32k3a._sync_parent_state
        for the full rationale (identical here).

        Parameters
        ----------
        a : tuple of int
        """
        self._current_seed = a
        packed = 0
        for component in a:
            packed = (packed << 32) | component
        super().seed(packed)

    def seed(self, a):
        """
        Set the seed of MRG31k3p and update the generator state.

        Re-seeding is "starting fresh from a new position" -- resets
        raw_consumed() to 0, the same way a freshly-constructed instance
        would report it.

        Parameters
        ----------
        a : tuple of int
        """
        assert(len(a) == 6)
        self._sync_parent_state(a)
        self._raw_consumed = 0

    def _advance(self):
        """
        Step the generator once and update the state. See
        MRG32k3a._advance for why raw_consumed() is incremented here
        specifically (the one choke point every raw draw funnels
        through).

        Returns
        -------
        newseed : tuple of int
        u : float
        """
        seed = self._current_seed
        newseed, u = mrg31k3p(seed)
        self._sync_parent_state(newseed)
        self._raw_consumed += 1
        return newseed, u

    def random(self):
        """
        Generate a standard uniform variate and advance the generator
        state.

        Returns
        -------
        u : float
        """
        _newseed, u = self._advance()
        return u

    def _next_raw(self):
        """
        Step the generator once and return the exact-integer combined
        draw, skipping the float round-trip through mrg31norm that
        random() takes.

        newseed[2] and newseed[5] are exactly x1n/x2n as mrg31k3p()
        itself computed them (already exact integers, unlike
        MRG32k3a's own p1/p2 -- see module docstring), so this recovers
        the same raw combined value without reversing u.

        Returns
        -------
        int
            Uniform over {1, ..., mrg31m1} -- mrg31m1 distinct values,
            not a power of two.
        """
        newseed, _u = self._advance()
        x1n = newseed[2]
        x2n = newseed[5]
        return (x1n - x2n + mrg31m1) if x1n <= x2n else (x1n - x2n)

    def getrandbits(self, k):
        """
        Generate a non-negative int with k uniformly-distributed random
        bits. Same digit-concatenation-with-rejection scheme as
        MRG32k3a.getrandbits, parameterized on mrg31m1 instead of
        mrgm1i -- see that method's own docstring for why rejection,
        not a biased modulo.

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
        target = 1 << k
        while True:
            span = 1
            digits = 0
            while span < target:
                digits = digits * mrg31m1 + (self._next_raw() - 1)
                span *= mrg31m1
            usable = (span // target) * target
            if digits < usable:
                return digits % target
            # else: digits landed in the biased remainder above the largest
            # multiple of 2**k -- discard and redraw all t digits.

    def get_seed(self):
        """
        Return the current MRG31k3p seed.

        Returns
        -------
        tuple of int
            The current MRG31k3p seed
        """
        return self._current_seed

    def root_seed(self):
        """
        §12 step 6b: see MRG32k3a.root_seed -- identical contract, and
        identical to get_seed() here for the same reason (a raw MRG
        seed is already a valid stream_at base).

        Returns
        -------
        tuple of int
        """
        return self.get_seed()

    def getstate(self):
        """
        Return the state of the generator.

        Returns
        -------
        tuple of int
            The current seed
        tuple
            Random.getstate output

        See also
        --------
        random.Random
        """
        return self.get_seed(), super().getstate()

    def setstate(self, state):
        """
        Set the internal state of the generator.

        Parameters
        ----------
        state : tuple
            tuple[0] is the MRG31k3p seed, [1] is random.Random.getstate

        See also
        --------
        random.Random
        """
        self.seed(state[0])
        super().setstate(state[1])

    def normalvariate(self, mu=0, sigma=1):
        """
        Generate a normal random variate, via the same bsm() transform
        MRG32k3a uses -- generator-agnostic by construction (§3.3: the
        monotone inverse-CDF requirement is an interface obligation, a
        pure function of u, not a per-generator choice).

        Parameters
        ----------
        mu : float
            Expected value of the normal distribution from which to
            generate. Default is 0.
        sigma : float
            Standard deviation of the normal distribution from which to
            generate. Default is 1.

        Returns
        -------
        float
            A normal variate from the specified distribution
        """
        u = self.random()
        z = bsm(u)
        return sigma*z + mu

    def raw_consumed(self):
        """
        §12 step 6b: see MRG32k3a.raw_consumed -- identical contract.

        Returns
        -------
        int
        """
        return self._raw_consumed

    def advance(self, delta):
        """
        §12 step 6b: see MRG32k3a.advance -- identical contract, using
        this generator's own jump_seed_n.

        Parameters
        ----------
        delta : int
            Non-negative.

        Returns
        -------
        MRG31k3p
        """
        return MRG31k3p(jump_seed_n(self.get_seed(), delta))


def jump_seed_n(seed, n):
    """
    Advance a full 6-component seed n steps, via the generalized
    binary-exponentiation matrix power (mrg_common.mat_pow_mod/jump_n)
    applied to each half independently -- structurally identical to
    mrg32k3a.py's own jump_seed_n, generalized over MRG31k3p's own
    matrices/moduli instead. At the two fixed exponents REPL_STRIDE/
    ITER_STRIDE (reused from mrg32k3a.py -- see module docstring for why
    these stay global), this reuses the matrices cached at import time
    above; any other `n` runs the general computation directly.

    Parameters
    ----------
    seed : tuple of int
        Length must be 6.
    n : int
        Number of steps. Must be non-negative.

    Returns
    -------
    tuple of int
        The seed advanced n steps.
    """
    assert(len(seed) == 6)
    s1 = seed[0:3]
    s2 = seed[3:6]
    if n == REPL_RESERVE_STRIDE:
        p1, p2 = _jump_replreserve_p1, _jump_replreserve_p2
    elif n == REPL_STRIDE:
        p1, p2 = _jump76_p1, _jump76_p2
    elif n == ITER_STRIDE:
        p1, p2 = _jump127_p1, _jump127_p2
    else:
        ns1 = _jump_n(s1, _m1_step, n, mrg31m1)
        ns2 = _jump_n(s2, _m2_step, n, mrg31m2)
        return tuple(ns1 + ns2)
    ns1 = _mat311mod(_mat333mult(p1, s1), mrg31m1)
    ns2 = _mat311mod(_mat333mult(p2, s2), mrg31m2)
    return tuple(ns1 + ns2)


def stream_at(seed, stream, offset):
    """
    §3.9's two-dimensional coordinate, for MRG31k3p -- structurally
    identical to mrg32k3a.py's own stream_at, reusing the same
    REPL_STRIDE/ITER_STRIDE this module already imports (docs/rng-
    interface-design.md §12 step 5's own finding: these stay global,
    MRG31k3p's period comfortably absorbs them too).

    Parameters
    ----------
    seed : tuple of int
        Length 6.
    stream : int
        Non-negative.
    offset : int
        Non-negative, < `ITER_STRIDE`.

    Returns
    -------
    MRG31k3p
        Matches §3.1's own contract; see mrg32k3a.py's own stream_at
        docstring for why this returns a constructed instance, not a
        raw seed.
    """
    new_seed = jump_seed_n(seed, stream * ITER_STRIDE + offset)
    return MRG31k3p(new_seed)


def get_next_prnstream(seed):
    """
    Instantiate a generator seeded 2^127 steps from the input seed.

    Parameters
    ----------
    seed : tuple of int

    Returns
    -------
    prn : MRG31k3p object
    """
    sseed = jump_seed_n(seed, ITER_STRIDE)
    return MRG31k3p(sseed)


def jump_substream(prn):
    """
    Advance the rng to the next substream 2^76 steps.

    Parameters
    ----------
    prn : MRG31k3p object
    """
    prn.seed(jump_seed_n(prn.get_seed(), REPL_STRIDE))
