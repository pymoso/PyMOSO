# Single-file custom problem fixture -- mirrors pymoso/examples/myproblem.py
# exactly (the project's own reference example for how a user supplies a
# custom problem), used as-is to keep the "easy case" honest rather than
# simplified further.
from pymoso.chnbase import Oracle

class MyProblem(Oracle):
    '''Example implementation of a user-defined MOSO problem.'''
    def __init__(self, rng):
        self.num_obj = 2
        self.dim = 1
        super().__init__(rng)

    def g(self, x, rng):
        feas_range = range(-100, 101)
        obj = []
        is_feas = False
        if len(x) == self.dim:
            is_feas = True
            for i in x:
                if not i in feas_range:
                    is_feas = False
        if is_feas:
            z0 = rng.normalvariate(0, 1)
            z1 = rng.normalvariate(0, 1)
            obj1 = x[0]**2 + z0
            obj2 = (x[0] - 2)**2 + z1
            obj = (obj1, obj2)
        return is_feas, obj
