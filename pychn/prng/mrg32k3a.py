#!/usr/bin/env python
"""Provide a subclass of random.Random using mrg32k3a as the generator with substream support."""

import random
import numpy as np
from math import log


## constants used in mrg32k3a and in substream generation
## all from:
 # P. L'Ecuyer, ``Good Parameter Sets for Combined Multiple Recursive Random Number Generators'',
 # Operations Research, 47, 1 (1999), 159--164.
 #
 # P. L'Ecuyer, R. Simard, E. J. Chen, and W. D. Kelton,
 # ``An Objected-Oriented Random-Number Package with Many Long Streams and Substreams'',
 # Operations Research, 50, 6 (2002), 1073--1075

a1p127 = ((2427906178.0, 3580155704.0, 949770784.0),
    (226153695.0, 1230515664.0, 3580155704.0),
    (1988835001.0,  986791581.0, 1230515664.0)
)

a2p127 = ((1464411153.0,  277697599.0, 1610723613.0),
    (32183930.0, 1464411153.0, 1022607788.0),
    (2824425944.0, 32183930.0, 2093834863.0)
)

# precomputed A matrix for jumping 2^127 steps in mrg32k3a period
A1p127 = np.array(a1p127)
A2p127 = np.array(a2p127)
mrgnorm = 2.328306549295727688e-10
mrgm1 = 4294967087.0
mrgm2 = 4294944443.0
mrga12 = 1403580.0
mrga13n = 810728.0
cp1 = np.array([mrga12, -mrga13n])
mrga21 = 527612.0
mrga23n = 1370589.0
cp2 = np.array([mrga21, -mrga23n])
mrgtwo17 = 131072.0
mrgtwo53 = 9007199254740992.0
mrgfact = 5.9604644775390625e-8


#constants used for approximating the inverse standard normal cdf
## Beasly-Springer-Moro
bsma = np.array([2.50662823884, -18.61500062529, 41.39119773534, -25.44106049637])
bsmb = np.array([-8.47351093090, 23.08336743743, -21.06224101826, 3.13082909833])
bsmc = np.array([0.3374754822726147, 0.9761690190917186, 0.1607979714918209, 0.0276438810333863, 0.0038405729373609,0.0003951896411919, 0.0000321767881768, 0.0000002888167364, 0.0000003960315187])


## mrg32k3a -- what more to say??
def mrg32k3a(seed):
    """Generate a pseudo-random u distributed as U(0, 1)."""
    # seeds used in first linear component
    s1 = np.array([seed[1], seed[0]])
    # construct first component
    p11 = np.dot(cp1, s1)
    p1 = np.mod(p11, mrgm1)
    # seeds used in second linear component
    s2 = np.array([seed[5], seed[3]])
    # construct second component
    p12 = np.dot(cp2, s2)
    p2 = np.mod(p12, mrgm2)
    # create the next seed
    newseed = (seed[1], seed[2], p1, seed[4], seed[5], p2)
    # set u and return
    u = np.multiply(np.sum([p1, -p2]), mrgnorm)
    if p1 <= p2:
        u = np.multiply(np.sum([p1, -p2, mrgm1]), mrgnorm)
    return newseed, u


# Beasly-Springer-Moro
def bsm(u):
    """Generate the uth quantile of the standard normal distribution."""
    # check if u is in the central or tail section of the normal distrubution
    y = u - 0.5
    if abs(y) < 0.42:
        # u is in central part, use Beasly-Springer approximation (1977)
        r0 = y**2
        r = np.power(r0, range(5))
        asum = np.dot(r[:-1], bsma)
        bsum = np.dot(r[1:], bsmb) + 1
        z = y*(asum/bsum)
    else:
        # u is in the tails, use Moro approximation (1995)
        if y < 0.0:
            signum = -1
            r = u
        else:
            # y >= 0
            signum = 1
            r = 1 - u
        s0 = log(-log(r))
        s = np.power(s0, range(9))
        t = np.dot(bsmc, s)
        z = signum*t
    return z


class MRG32k3a(random.Random):
    """Subclass of the default random.Random using mrg32k3a as the generator."""

    def __init__(self, x=None):
        """Initialize the generator with an optional mrg32k3a seed (tuple of length 6)."""
        if not x:
            x = (12345, 12345, 12345, 12345, 12345, 12345)
        assert(len(x) == 6)
        self.version = 2
        super().__init__(x)

    def seed(self, a):
        """Set the seed of mrg32k3a and update the generator state."""
        assert(len(a) == 6)
        self._current_seed = a
        super().seed(a)

    def random(self):
        """Generate a random u ~ U(0, 1) and advance the generator state."""
        seed = self._current_seed
        newseed, u = mrg32k3a(seed)
        self.seed(newseed)
        return u

    def get_seed(self):
        """Return the current mrg32k3a seed."""
        return self._current_seed

    def getstate(self):
        """Return a state object describing the current generator."""
        return self.get_seed(), super().getstate()

    def setstate(self, state):
        """Set the internal state of the generator."""
        self.seed(state[0])
        super().setstate(state[1])

    def normalvariate(self, mu=0, sigma=1):
        """Generate a random z ~ N(mu, sigma)."""
        u = self.random()
        z = bsm(u)
        return sigma*z + mu


def get_next_prnstream(seed):
    """Create a generator seeded 2^127 steps from the input seed."""
    assert(len(seed) == 6)
    # split the seed into 2 components of length 3
    s1 = np.array(seed[0:3])
    s2 = np.array(seed[3:6])
    # A*s % m
    ns1m = np.matmul(a1p127, s1)
    ns2m = np.matmul(a2p127, s2)
    ns1 = np.mod(ns1m, mrgm1)
    ns2 = np.mod(ns2m, mrgm2)
    # random.Random objects need a hashable seed
    sseed = tuple(np.append(ns1, ns2))
    prn = MRG32k3a(sseed)
    return prn
