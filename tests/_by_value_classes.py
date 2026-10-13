"""Classes in a module the test process can import and a fresh
interpreter elsewhere cannot: tests/ is on sys.path only because
pytest put it there. This is the "importable on the driver, not on the
executor" case for a remote backend."""
from pymoso.chnbase import Oracle
from pymoso.solvers.rperle import RPERLE
from pymoso.testers.tpatester import TPATester

OFFSET = 7


def shifted(x):
    return x[0] ** 2 + OFFSET


class DriverOnlyProblem(Oracle):
    def __init__(self, rng):
        self.num_obj = 2
        self.dim = 2
        super().__init__(rng)

    def g(self, x, rng):
        if not all(-50 <= xi <= 50 for xi in x):
            return False, ()
        z = rng.normalvariate(0, 1)
        return True, (shifted(x) + x[1] ** 2 + z, (x[0] - 10) ** 2 + (x[1] - 10) ** 2 + z)


class DriverOnlyTester(TPATester):
    def __init__(self):
        super().__init__()
        self.ranorc = DriverOnlyProblem


class DriverOnlySolver(RPERLE):
    pass
