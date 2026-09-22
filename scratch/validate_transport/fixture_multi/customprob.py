# Multi-file custom problem fixture -- imports a sibling helper module,
# the realistic shape for any nontrivial simulation (objective logic
# factored out, not inlined). This is the fixture that's expected to
# separate option 4 (ship one file's source) from option 5 (cloudpickle).
from pymoso.chnbase import Oracle
from helper import noisy_quadratic, PENALTY

class MyProblem(Oracle):
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
            obj1 = noisy_quadratic(x[0], rng)
            z1 = rng.normalvariate(0, 1)
            obj2 = (x[0] - 2)**2 + z1 + 0*PENALTY
            obj = (obj1, obj2)
        return is_feas, obj
