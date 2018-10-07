#!/usr/bin/env python
from ..chnbase import Oracle


class ProbSimpleSO(Oracle):
    """x^2 + noise."""
    def __init__(self, rng):
        self.num_obj = 1
        self.dim = 1
        super().__init__(rng)

    def g(self, x, rng):
        """Estimate g(x)."""
        xr = range(-100, 101)
        isfeas = True
        for xi in x:
            if not xi in xr:
                isfeas = False
        obj1 = []
        if isfeas:
            z1 = rng.normalvariate(0, 3)
            obj1 = x[0]**2 + z1
        return isfeas, (obj1, )
