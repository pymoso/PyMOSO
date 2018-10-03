#!/usr/bin/env python
from ..chnbase import Oracle
from math import exp, sqrt, sin


class ProbTPC(Oracle):
    """Test Problem C"""
    def __init__(self, rng):
        self.num_obj = 2
        self.dim = 3
        self.density_factor = 2
        super().__init__(rng)

    def get_feasspace(self):
        dim = self.dim
        df = self.density_factor
        mcD = dict()
        for i in range(dim):
            mcD[i] = [(-5*df, 5*df + 1)]
        return mcD

    def g(self, x, rng):
        obj1 = []
        obj2 = []
        isfeas = self.check_xfeas(x)
        if isfeas:
            z1 = rng.normalvariate(0, 1)
            z2 = rng.normalvariate(0, 1)
            z3 = rng.normalvariate(0, 1)
            xi = (z1**2, z2**2, z3**2)
            df = self.density_factor
            x = tuple(i/df for i in x)
            s = [sin(i) for i in x]
            sum1 = [-10*xi[i]*exp(-0.2*sqrt(x[i]**2 + x[i+1]**2)) for i in [0, 1]]
            sum2 = [xi[i]*(pow(abs(x[i]), 0.8) + 5*pow(s[i], 3)) for i in [0, 1, 2]]
            obj1 = sum(sum1)
            obj2 = sum(sum2)
        return isfeas, (obj1, obj2)
