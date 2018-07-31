#!/usr/bin/env python
from ..chnbase import Oracle


class ProbTPA(Oracle):
    """Test Problem A"""
    def __init__(self, prn):
        self.num_obj = 2
        self.dim = 2
        super().__init__(prn)

    def get_feasspace(self):
        """Get an iteratable to represent the feasible space."""
        dim = self.dim
        mcD = dict()
        for i in range(dim):
            mcD[i] = [(0, 51)]
        return mcD

    def g(self, x, prn):
        """Estimate g(x)."""
        isfeas = self.check_xfeas(x)
        obj1 = []
        obj2 = []
        if isfeas:
            z1 = prn.normalvariate(0, 1)
            z2 = prn.normalvariate(0, 1)
            z3 = prn.normalvariate(0, 1)
            xi = [z1**2, z2**2, z3**2]
            obj1 = (x[0]/10.0 - 2.0*xi[0])**2 + (x[1]/10.0 - xi[1])**2
            obj2 = (x[0]**2)/100.0 + (x[1]/10.0 - 2.0*xi[2])**2
        return isfeas, (obj1, obj2)
