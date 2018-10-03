#!/usr/bin/env python
from ..chnbase import Oracle


class ProbSimpleSO(Oracle):
    """x^2 + noise."""
    def __init__(self, rng):
        self.num_obj = 1
        self.dim = 1
        super().__init__(rng)

    def get_feasspace(self):
        """Get an iteratable to represent the feasible space."""
        dim = self.dim
        mcD = dict()
        for i in range(dim):
            mcD[i] = [(-100, 101)]
        return mcD

    def g(self, x, rng):
        """Estimate g(x)."""
        isfeas = self.check_xfeas(x)
        obj1 = []
        obj2 = []
        if isfeas:
            z1 = rng.normalvariate(0, 1)
            obj1 = x[0]**2 + z1
        return isfeas, (obj1, )
