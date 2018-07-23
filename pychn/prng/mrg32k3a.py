#!/usr/bin/env python
import random
import numpy as np
from math import fabs, pow, log, fsum


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

A1p127 = np.array(a1p127)
A2p127 = np.array(a2p127)
mrgnorm = 2.328306549295727688e-10
mrgm1 = 4294967087.0
mrgm2 = 4294944443.0
mrga12 = 1403580.0
mrga13n = 810728.0
mrga21 = 527612.0
mrga23n = 1370589.0
mrgtwo17 = 131072.0
mrgtwo53 = 9007199254740992.0
mrgfact = 5.9604644775390625e-8


#constants used for approximating the inverse standard normal cdf
## Beasly-Springer-Moro
bsma = np.array([2.50662823884, -18.61500062529, 41.39119773534, -25.44106049637])
bsmb = np.array([-8.47351093090, 23.08336743743, -21.06224101826, 3.13082909833])
bsmc = np.array([0.3374754822726147, 0.9761690190917186, 0.1607979714918209, 0.0276438810333863, 0.0038405729373609,0.0003951896411919, 0.0000321767881768, 0.0000002888167364, 0.0000003960315187])


def mrg32k3a(seed):
    p1 = mrga12*seed[1] - mrga13n*seed[0]
    k1 = p1//mrgm1
    p1 -= k1*mrgm1
    if p1 < 0.0:
        p1 += m1
    p2 = mrga21*seed[5] - mrga23n*seed[3]
    k2 = p2//mrgm2
    p2 -= k2*mrgm2
    if p2 < 0.0:
        p2 += mrgm2
    u = (p1 - p2 + mrgm1)*mrgnorm if p1 <= p2 else (p1 - p2)*mrgnorm
    newseed = (seed[1], seed[2], p1, seed[4], seed[5], p2)
    return newseed, u


def bsm(u):
    y = u - 0.5
    if fabs(y) < 0.42:
        r0 = y**2
        rlst = [r0**p for p in range(5)]
        r = np.array(rlst)
        asum = np.dot(r[:-1], bsma)
        bsum = np.dot(r[1:], bsmb) + 1
        z = y*(asum/bsum)
    else:
        # we have |y| >= 0.42
        if y < 0.0:
            signum = -1
            r = u
        else:
            # y >= 0
            signum = 1
            r = 1 - u
        s0 = log(-log(r))
        slst = [s0**p for p in range(9)]
        s = np.array(slst)
        t = np.dot(bsmc, s)
        z = signum*t
    return z


class MRG32k3a(random.Random):
    def __init__(self, x=None):
        if not x:
            x = (12345, 12345, 12345, 12345, 12345, 12345)
        assert(len(x) == 6)
        self.version = 2
        super().__init__(x)

    def seed(self, a):
        assert(len(a) == 6)
        self._current_seed = a
        super().seed(a)

    def random(self):
        seed = self._current_seed
        newseed, u = mrg32k3a(seed)
        self.seed(newseed)
        return u

    def get_seed(self):
        return self._current_seed

    def getstate(self):
        return self.get_seed(), super().getstate()

    def setstate(self, state):
        self.seed(state[0])
        super().setstate(state[1])

    def normalvariate(self, mu, sigma):
        u = self.random()
        z = bsm(u)
        return sigma*z + mu


def get_next_prnstream(seed):
    assert(len(seed) == 6)
    s1s = seed[0:3]
    s2s = seed[3:6]
    s1 = np.array(s1s)
    s2 = np.array(s2s)
    ns1m = np.matmul(a1p127, s1)
    ns2m = np.matmul(a2p127, s2)
    ns1 = np.mod(ns1m, mrgm1)
    ns2 = np.mod(ns2m, mrgm2)
    sseed = tuple(np.append(ns1, ns2))
    prn = MRG32k3a(sseed)
    return prn


def main():
    iseed = (12345, 12345, 12345, 12345, 12345, 12345)
    # prnlst = []
    # for i in range(50):
    #     prn = get_next_prnstream(iseed)
    #     iseed = prn._current_seed
    #     prnlst.append(prn)
    # print(len(prnlst))
    # for p in prnlst:
    #     print(p._current_seed)
    prn1 = MRG32k3a(iseed)
    for i in range(10):
        z = prn1.normalvariate(0, 1)
        print(z)


if __name__ == '__main__':
    main()
