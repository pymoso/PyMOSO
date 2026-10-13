"""Problem classes for tests/test_executor.py's pool tests. In a module
of their own so that a worker started by spawn or forkserver can import
them by name."""
from pymoso.chnbase import Oracle


class _OneObjective(Oracle):
    def __init__(self, rng):
        self.num_obj = 1
        self.dim = 1
        super().__init__(rng)


class RaisesAtThirteen(_OneObjective):
    def g(self, x, rng):
        if x == (13,):
            raise ZeroDivisionError("boom at {0}".format(x))
        return True, (rng.random(),)


class DrawsNine(_OneObjective):
    def g(self, x, rng):
        for _ in range(9):
            rng.random()
        return True, (0.0,)
