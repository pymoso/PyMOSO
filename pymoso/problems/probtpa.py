#!/usr/bin/env python
from ..chnbase import Oracle


class ProbTPA(Oracle):
    """Test Problem A"""
    def __init__(self, rng):
        self.num_obj = 2
        self.dim = 2
        super().__init__(rng)

    def g(self, x, rng):
        """Estimate g(x)."""
        xr = range(0, 51)
        isfeas = True
        for xi in x:
            if not xi in xr:
                isfeas = False
        obj1 = None
        obj2 = None
        if isfeas:
            z1 = rng.normalvariate(0, 1)
            z2 = rng.normalvariate(0, 1)
            z3 = rng.normalvariate(0, 1)
            xi = [z1**2, z2**2, z3**2]
            obj1 = (x[0]/10.0 - 2.0*xi[0])**2 + (x[1]/10.0 - xi[1])**2
            obj2 = (x[0]**2)/100.0 + (x[1]/10.0 - 2.0*xi[2])**2
        return isfeas, (obj1, obj2)
