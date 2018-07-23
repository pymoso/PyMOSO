#!/usr/bin/env python
from ..chnbase import Oracle
import math


class ProbTPA(Oracle):
    def __init__(self, prn):
        self.num_obj = 2
        self.dim = 2
        super().__init__(prn)

    def get_feasspace(self):
        dim = self.dim
        mcD = dict()
        for i in range(dim):
            mcD[i] = [(0, 51)]
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
        obj2 = math.pow(x[0], 2)/100.0 + math.pow(x[1]/10.0 - 2.0*xi[2], 2)
        obj1 = math.pow(x[0]/10.0 - 2.0*xi[0], 2) + math.pow(x[1]/10.0 - xi[1], 2)
        return obj1, obj2
