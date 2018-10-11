#!/usr/bin/env python
from ..chnbase import Oracle
from math import exp


class ProbTPB(Oracle):
    """Test Problem B"""
    def __init__(self, rng):
        self.num_obj = 2
        self.dim = 2
        super().__init__(rng)

    def g(self, x, rng):
        """Estimate g(x)."""
        obj1 = None
        obj2 = None
        isfeas = True
        xr = range(0, 101)
        for xi in x:
            if not xi in xr:
                isfeas = False
        if isfeas:
            z1 = rng.normalvariate(0, 1)
            z2 = rng.normalvariate(0, 1)
            xi = (z1**2, z2**2)
            g1 = 4*x[0]/100
            if x[1] >= 0 and x[1] <= 40:
                f2 = 4 - 3*exp(-pow((x[1]-20)/2, 2))
            else:
                f2 = 4 - 2*exp(-pow((x[1]-70)/20, 2))
            alpha = 0.25 + 3.75*(f2 - 1)
            if g1 <= f2:
                h = 1 - pow(g1/f2, alpha)
            else:
                h = 0
            obj2 = xi[0]*g1
            obj1 = xi[0]*xi[1]*f2*h
        return isfeas, (obj1, obj2)
