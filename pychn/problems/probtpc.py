#!/usr/bin/env python
from ..chnbase import Oracle
import math


class ProbTPC(Oracle):
    """Test Problem C"""
    def __init__(self, prn):
        self.num_obj = 2
        self.dim = 3
        self.density_factor = 2
        super().__init__(prn)

    def get_feasspace(self):
        dim = self.dim
        df = self.density_factor
        mcD = dict()
        for i in range(dim):
            mcD[i] = [(-5*df, 5*df + 1)]
        return mcD

    def get_xi(self, prn):
        z1 = prn.normalvariate(0, 1)
        z2 = prn.normalvariate(0, 1)
        z3 = prn.normalvariate(0, 1)
        xi0 = math.pow(z1, 2)
        xi1 = math.pow(z2, 2)
        xi2 = math.pow(z3, 2)
        return xi0, xi1, xi2

    def g(self, x, xi):
        df = self.density_factor
        x = tuple(i/df for i in x)
        s = [math.sin(i) for i in x]
        sum1 = [-10*xi[i]*math.exp(-0.2*math.sqrt(x[i]**2 + x[i+1]**2)) for i in [0, 1]]
        sum2 = [xi[i]*(math.pow(math.fabs(x[i]), 0.8) + 5*math.pow(s[i], 3)) for i in [0, 1, 2]]
        obj1 = math.fsum(sum1)
        obj2 = math.fsum(sum2)
        return obj1, obj2
