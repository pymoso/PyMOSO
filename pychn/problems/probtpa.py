#!/usr/bin/env python
from ..chnbase import Oracle
import numpy as np


class ProbTPA(Oracle):
    """Test Problem A"""
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
        """Realize 3 chi square random variables with 1 df."""
        z1 = prn.normalvariate(0, 1)
        z2 = prn.normalvariate(0, 1)
        z3 = prn.normalvariate(0, 1)
        z = np.array([z1, z2, z3])
        xi = np.power(z, 2)
        return xi

    def g(self, x, xi):
        """Estimate g(x) given randomness xi."""
        obj1 = (x[0]/10.0 - 2.0*xi[0])**2 + (x[1]/10.0 - xi[1])**2
        obj2 = (x[0]**2)/100.0 + (x[1]/10.0 - 2.0*xi[2])**2
        return obj1, obj2
