#!/usr/bin/env python
import random
from math import fabs, pow, log, fsum

def mrg32k3a(seed):
    m1 = 4294967087
    m2 = 4294944443
    p1 = 1403580*seed[1] - 810728*seed[0]
    k1 = int(p1/m1)
    p1 -= k1*m1
    if p1 < 0.0:
        p1 += m1
    p2 = 527612*seed[5] - 1370589*seed[3]
    k2 = int(p2/m2)
    p2 -= k2*m2
    if p2 < 0.0:
        p2 += m2
    if p1 <= p2:
        u = (p1 - p2 + m1)*2.328306549295728e-10
    else:
        u = (p1 - p2)*2.328306549295728e-10
    newseed = (seed[1], seed[2], p1, seed[4], seed[5], p2)
    return newseed, u


def bsm(u):
    a = (2.50662823884, -18.61500062529, 41.39119773534, -25.44106049637)
    b = (-8.47351093090, 23.08336743743, -21.06224101826, 3.13082909833)
    c = (0.3374754822726147, 0.9761690190917186, 0.1607979714918209, 0.0276438810333863, 0.0038405729373609,0.0003951896411919, 0.0000321767881768, 0.0000002888167364, 0.0000003960315187)
    y = u - 0.5
    if fabs(y) < 0.42:
        r = pow(y, 2)
        r2 = pow(r, 2)
        r3 = pow(r, 3)
        r4 = pow(r, 4)
        asum = fsum([a[0], a[1]*r, a[2]*r2, a[3]*r3])
        bsum = fsum([1, b[0]*r, b[1]*r2, b[2]*r3, b[3]*r4])
        z = y*(asum/bsum)
    else:
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
        clst = [c[0], c[1]*s, c[2]*s0, c[3]*s1, c[4]*s2, c[5]*s3, c[6]*s4, c[7]*s5, c[8]*s6]
        t = fsum(clst)
        z = signum*t
    return z


class MRG32k3a(random.Random):
    def __init__(self, x=None):
        assert(len(x) == 6)
        self.version = 1
        super().__init__(x)

    def seed(self, a=None, version=3):
        if a:
            assert(len(a) == 6)
        self._current_seed = a
        super().seed(a)

    def random(self):
        seed = self._current_seed
        newseed, u = mrg32k3a(seed)
        self.seed(newseed)
        return u

    def get_seed(self):
        return tuple(self._current_seed)

    def getstate(self):
        return self.get_seed(), super().getstate()

    def setstate(self, state):
        self.seed(state[0])
        super().setstate(state[1])

    def normalvariate(self, mu, sigma):
        u = self.random()
        z = bsm(u)
        return sigma*z + mu
