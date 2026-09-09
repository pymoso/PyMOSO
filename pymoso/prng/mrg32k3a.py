#!/usr/bin/env python
"""
Summary
-------
Provide a subclass of random.Random using mrg32k3a as the generator
with substream support.

Listing
-------
MRG323k3a
get_next_prnstream
jump_substream
jump_seed_n
"""

import random
from math import log
import functools

# mat333mult/mat311mod/mat_pow_mod/jump_n now live in mrg_common.py
# (shared, generalized jump machinery) and are used here only
# internally (see jump_seed_n below) -- imported under private aliases,
# deliberately not re-exported as `pymoso.prng.mrg32k3a.mat333mult`/
# `mat311mod` any more. That import path had exactly one real consumer,
# scratch/task1_mechanism.py, checked directly (grepped the whole repo,
# tracked and untracked) rather than assumed -- a one-off diagnostic
# script from the original float-precision-defect investigation
# (KNOWN_ISSUES.md issue 1), hardcoding an absolute personal path, whose
# findings are already captured in docs/phase2a-verification.md; nothing
# else imports either name from this module. Not carrying a compatibility
# re-export for a script that won't run again.
from .mrg_common import (
    mat333mult as _mat333mult,
    mat311mod as _mat311mod,
    mat_pow_mod as _mat_pow_mod,
    jump_n as _jump_n,
)

## constants used in mrg32k3a and in substream generation
## all from:
 # P. L'Ecuyer, ``Good Parameter Sets for Combined Multiple Recursive Random Number Generators'',
 # Operations Research, 47, 1 (1999), 159--164.
 #
 # P. L'Ecuyer, R. Simard, E. J. Chen, and W. D. Kelton,
 # ``An Objected-Oriented Random-Number Package with Many Long Streams and Substreams'',
 # Operations Research, 50, 6 (2002), 1073--1075
 #
## a1p127/a2p127/a1p76/a2p76 below are the historical pre-computed jump
## matrices at the two fixed exponents this module has always exposed.
## As of the generalized jump (_m1_step/_m2_step + mrg_common.mat_pow_mod,
## below), get_next_prnstream/jump_substream no longer read these four
## directly -- the same values are now computed on demand from the base
## recurrence instead of transcribed twice. Left in place, unchanged,
## and still public (unlike mat333mult/mat311mod above): KNOWN_ISSUES.md
## issue 1's own tracked narrative refers to these specific names when
## describing the float-precision defect they were involved in, and
## tests/test_mrg_common.py -- a real, permanent, tracked consumer,
## not a throwaway script -- imports all four directly as a regression
## pin confirming the generalized jump reproduces them exactly.

a1p127 = [[2427906178.0, 3580155704.0, 949770784.0],
    [226153695.0, 1230515664.0, 3580155704.0],
    [1988835001.0,  986791581.0, 1230515664.0]
]

a2p127 = [[1464411153.0,  277697599.0, 1610723613.0],
    [32183930.0, 1464411153.0, 1022607788.0],
    [2824425944.0, 32183930.0, 2093834863.0]
]

a1p76 = [[82758667.0, 1871391091.0, 4127413238.0],
    [3672831523.0, 69195019.0, 1871391091.0],
    [3672091415.0, 3528743235.0, 69195019.0]
]

a2p76 = [[1511326704.0, 3759209742.0, 1610795712.0],
    [4292754251.0, 1511326704.0, 3889917532.0],
    [3859662829.0, 4292754251.0, 3708466080.0],
]

mrgnorm = 2.328306549295727688e-10
mrgm1 = 4294967087.0
mrgm2 = 4294944443.0
mrgm1i = int(mrgm1)  # exact int form; getrandbits() needs integer arithmetic, not mrgnorm's float round-trip
mrgm2i = int(mrgm2)  # same, for the generalized jump below (mrg_common.jump_n)
mrga12 = 1403580.0
mrga13n = 810728.0
mrga21 = 527612.0
mrga23n = 1370589.0

# One-step transition matrices for mrg32k3a()'s own recurrence above, in
# the same (non-reversed) seed[0:3]/seed[3:6] component order
# mat333mult already uses -- derived directly from mrg32k3a()'s two
# update lines (newseed = (seed[1], seed[2], p1, seed[4], seed[5], p2)),
# not transcribed from a second, independent source, so there is exactly
# one place these coefficients are stated. mrg_common.mat_pow_mod raises
# each to an arbitrary power mod mrgm1i/mrgm2i; jump_substream/
# get_next_prnstream below become thin wrappers around jump_seed_n at
# the two fixed exponents 2**76/2**127. Verified to reproduce a1p76/
# a2p76/a1p127/a2p127 below exactly, not just derived and assumed --
# see tests/test_mrg_common.py.
_m1_step = [[0, 1, 0], [0, 0, 1], [(-int(mrga13n)) % mrgm1i, int(mrga12) % mrgm1i, 0]]
_m2_step = [[0, 1, 0], [0, 0, 1], [(-int(mrga23n)) % mrgm2i, 0, int(mrga21) % mrgm2i]]

# Computed once, at import time, not per call: jump_seed_n's two
# hot-path exponents (2**76, 2**127 -- the only ones get_next_prnstream/
# jump_substream ever ask for) are cached here rather than run through
# mat_pow_mod's ~127-round binary exponentiation on every single call.
# This is not a hypothetical optimization -- get_next_prnstream runs
# once per RA iteration and jump_substream once per replication
# (chnbase.py), so recomputing the full power on every call is a real,
# measured regression: the full test suite went from ~60s to over 4
# minutes, with one CLI end-to-end test timing out, before this caching
# was added. Equal to a1p76/a2p76/a1p127/a2p127 above, by construction
# (mat_pow_mod is the same general operation, at the same exponents) and
# confirmed equal in tests/test_mrg_common.py -- computed here via the
# general mechanism rather than reused from those four directly, so
# jump_seed_n stays genuinely "the general jump, cached at its two known
# exponents," not a silent fallback to the old hardcoded path.
_jump76_p1 = _mat_pow_mod(_m1_step, 2**76, mrgm1i)
_jump76_p2 = _mat_pow_mod(_m2_step, 2**76, mrgm2i)
_jump127_p1 = _mat_pow_mod(_m1_step, 2**127, mrgm1i)
_jump127_p2 = _mat_pow_mod(_m2_step, 2**127, mrgm2i)


#constants used for approximating the inverse standard normal cdf
## Beasly-Springer-Moro
bsma = [2.50662823884, -18.61500062529, 41.39119773534, -25.44106049637]
bsmb = [-8.47351093090, 23.08336743743, -21.06224101826, 3.13082909833]
bsmc = [0.3374754822726147, 0.9761690190917186, 0.1607979714918209, 0.0276438810333863, 0.0038405729373609,0.0003951896411919, 0.0000321767881768, 0.0000002888167364, 0.0000003960315187]


# this is adapted to pure Python from the P. L'Ecuyer code referenced above
def mrg32k3a(seed):
    """
    Generate a random number between 0 and 1 from a seed.

    Parameters
    ----------
    seed : tuple of int
        Length must be 6.

    Returns
    -------
    newseed : tuple of int
    u : float
    """
    p1 = mrga12*seed[1] - mrga13n*seed[0]
    k1 = int(p1/mrgm1)
    p1 -= k1*mrgm1
    if p1 < 0.0:
        p1 += mrgm1
    p2 = mrga21*seed[5] - mrga23n*seed[3]
    k2 = int(p2/mrgm2)
    p2 -= k2*mrgm2
    if p2 < 0.0:
        p2 += mrgm2
    if p1 <= p2:
        u = (p1 - p2 + mrgm1)*mrgnorm
    else:
        u = (p1 - p2)*mrgnorm
    newseed = (seed[1], seed[2], int(p1), seed[4], seed[5], int(p2))
    return newseed, u


# as in beasly-springer-moro
def bsm(u):
    """
    Approximate the quantiles of the standard normal distribution.

    Parameters
    ----------
    u : float
        Desired quantile between 0 and 1

    Returns
    -------
    z : float
    """
    y = u - 0.5
    if abs(y) < 0.42:
        ## approximate from the center (Beasly Springer 1973)
        r = pow(y, 2)
        r2 = pow(r, 2)
        r3 = pow(r, 3)
        r4 = pow(r, 4)
        asum = sum([bsma[0], bsma[1]*r, bsma[2]*r2, bsma[3]*r3])
        bsum = sum([1, bsmb[0]*r, bsmb[1]*r2, bsmb[2]*r3, bsmb[3]*r4])
        z = y*(asum/bsum)
    else:
        ## approximate from the tails (Moro 1995)
        if y < 0.0:
            signum = -1
            r = u
        else:
            signum = 1
            r = 1 - u
        s = log(-log(r))
        s0 = pow(s, 2)
        s1 = pow(s, 3)
        s2 = pow(s, 4)
        s3 = pow(s, 5)
        s4 = pow(s, 6)
        s5 = pow(s, 7)
        s6 = pow(s, 8)
        clst = [bsmc[0], bsmc[1]*s, bsmc[2]*s0, bsmc[3]*s1, bsmc[4]*s2, bsmc[5]*s3, bsmc[6]*s4, bsmc[7]*s5, bsmc[8]*s6]
        t = sum(clst)
        z = signum*t
    return z


class MRG32k3a(random.Random):
    """
    Implements mrg32k3a as the generator for a random.Random object

    Attributes
    ----------
    _current_seed : tuple of int
        6 integer mrg32k3a seed

    Parameters
    ----------
    x : tuple of int, optional
        Seed from which to start the generator

    See also
    --------
    random.Random
    """

    def __init__(self, x=None):
        if not x:
            x = (12345, 12345, 12345, 12345, 12345, 12345)
        assert(len(x) == 6)
        self.generate = mrg32k3a
        self.bsm = bsm
        super().__init__(x)

    def set_class_cache(self, cache_flag):
        """
        Sets whether to use an LRU cache for both the random function and the
        bsm function.

        Parameters
        ----------
        cache_flag : bool

        See also
        --------
        functools.lru_cache
        """
        if not cache_flag:
            self.generate = mrg32k3a
            self.bsm = bsm
        else:
            self.generate = functools.lru_cache(maxsize=None)(mrg32k3a)
            self.bsm = functools.lru_cache(maxsize=None)(bsm)

    def seed(self, a):
        """
        Set the seed of mrg32k3a and update the generator state.

        Parameters
        ----------
        a : tuple of int
        """
        assert(len(a) == 6)
        self._current_seed = a
        # random.Random.seed() only accepts None/int/float/str/bytes/bytearray
        # (a tuple raises TypeError as of Python 3.11, and was already a
        # deprecated hash-based path before that). This call's only purpose
        # is to satisfy that type check: the parent's C-level Mersenne state
        # it seeds is never consulted, since random()/generate() are fully
        # overridden below. The packing below is an arbitrary bijection, not
        # a meaningful encoding -- nothing relies on its value or reverses it.
        packed = 0
        for component in a:
            packed = (packed << 32) | component
        super().seed(packed)

    def _advance(self):
        """
        Step the generator once and update the state.

        Returns
        -------
        newseed : tuple of int
        u : float
        """
        seed = self._current_seed
        newseed, u = self.generate(seed)
        self.seed(newseed)
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
        Step the generator once and return the exact-integer combined draw,
        skipping the float round-trip through mrgnorm that random() takes.

        newseed[2] and newseed[5] are exactly the p1/p2 mrg32k3a() computes
        internally (its newseed is (seed[1], seed[2], p1, seed[4], seed[5],
        p2)) and u is just (p1 - p2, folded into [1, mrgm1] via +mrgm1) times
        mrgnorm. Recomputing that fold here in integers, instead of reversing
        u, avoids relying on float precision to recover an exact integer.

        Returns
        -------
        int
            Uniform over {1, ..., mrgm1i} -- mrgm1i distinct values, not a
            power of two.
        """
        newseed, _u = self._advance()
        p1 = newseed[2]
        p2 = newseed[5]
        return (p1 - p2 + mrgm1i) if p1 <= p2 else (p1 - p2)

    def getrandbits(self, k):
        """
        Generate a non-negative int with k uniformly-distributed random
        bits.

        Each call to _next_raw() yields one digit uniform over
        {1, ..., mrgm1i}, a range of size mrgm1i = 2**32 - 209 -- not a
        power of two, so no fixed number of raw bits can be sliced out of
        it without bias. Instead, digits are concatenated in base mrgm1i
        until the combined range covers at least 2**k, giving an integer
        exactly uniform over [0, mrgm1i**t); the excess above the largest
        multiple of 2**k is then discarded by rejection (redrawing all t
        digits) rather than reduced by a biased modulo.

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
                digits = digits*mrgm1i + (self._next_raw() - 1)
                span *= mrgm1i
            usable = (span // target) * target
            if digits < usable:
                return digits % target
            # else: digits landed in the biased remainder above the largest
            # multiple of 2**k -- discard and redraw all t digits.

    def get_seed(self):
        """
        Return the current mrg32k3a seed.

        Returns
        -------
        tuple of int
            The current mrg32k3a seed
        """
        return self._current_seed

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
            tuple[0] is mrg32k3a seed, [1] is random.Random.getstate

        See also
        --------
        random.Random
        """
        self.seed(state[0])
        super().setstate(state[1])

    def normalvariate(self, mu=0, sigma=1):
        """
        Generate a normal random variate.

        Parameters
        ----------
        mu : float
            Expected value of the normal distribution from which to
            generate. Default is 0.
        sigma : float
            Standard deviatoin of the normal distribution from which to
            generate. Default is 1.

        Returns
        -------
        float
            A normal variate from the specified distribution

        """
        u = self.random()
        z = self.bsm(u)
        return sigma*z + mu


def jump_seed_n(seed, n):
    """
    Advance a full 6-component seed n steps, via the generalized
    binary-exponentiation matrix power (mrg_common.mat_pow_mod/jump_n)
    applied to each half independently. jump_substream/
    get_next_prnstream below are thin wrappers around this at the two
    fixed exponents 2**76/2**127; nothing else calls this with any other
    `n` yet -- see docs/rng-interface-design.md §3.4/§3.5 for the later
    step where an arbitrary coordinate does.

    At those same two fixed exponents, this reuses the matrices
    precomputed once at import time (above) instead of re-running
    mat_pow_mod's binary exponentiation on every call -- see the comment
    above _jump76_p1 for why that caching is load-bearing, not
    cosmetic. Any other `n` runs the general computation directly; nothing
    about its *result* differs between the two paths, only the cost.

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
    if n == 2**76:
        p1, p2 = _jump76_p1, _jump76_p2
    elif n == 2**127:
        p1, p2 = _jump127_p1, _jump127_p2
    else:
        ns1 = _jump_n(s1, _m1_step, n, mrgm1i)
        ns2 = _jump_n(s2, _m2_step, n, mrgm2i)
        return tuple(ns1 + ns2)
    ns1 = _mat311mod(_mat333mult(p1, s1), mrgm1i)
    ns2 = _mat311mod(_mat333mult(p2, s2), mrgm2i)
    return tuple(ns1 + ns2)


def get_next_prnstream(seed, use_cache):
    """
    Instantiate a generator seeded 2^127 steps from the input seed.

    Parameters
    ----------
    seed : tuple of int
    crn : bool

    Returns
    -------
    prn : MRG32k3a object
    """
    sseed = jump_seed_n(seed, 2**127)
    prn = MRG32k3a(sseed)
    prn.set_class_cache(use_cache)
    return prn

def jump_substream(prn):
    """
    Advance the rng to the next substream 2^76 steps.

    Parameters
    ----------
    prn : MRG32k3a object
    """
    prn.seed(jump_seed_n(prn.get_seed(), 2**76))
