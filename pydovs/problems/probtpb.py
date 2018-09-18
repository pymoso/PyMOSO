#!/usr/bin/env python
from ..chnbase import Oracle
from math import exp


class ProbTPB(Oracle):
    """Test Problem B"""
    def __init__(self, prn):
        self.num_obj = 2
        self.dim = 2
        super().__init__(prn)

    def get_feasspace(self):
        dim = self.dim
        mcD = dict()
        for i in range(dim):
            mcD[i] = [(0, 101)]
        return mcD

    def g(self, x, prn):
        """Estimate g(x)."""
        obj1 = []
        obj2 = []
        isfeas = self.check_xfeas(x)
        if isfeas:
            z1 = prn.normalvariate(0, 1)
            z2 = prn.normalvariate(0, 1)
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
