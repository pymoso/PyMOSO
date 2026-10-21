"""
R-PERLE and R-PE are defined for two objectives, and do not police the
problems they are given (docs/algorithm-audit.md, finding 10). Until
2.0, a one-objective problem made them call sys.exit() from library
code; now whatever the algorithm raises reaches the caller. Three
objectives ran before and still do.
"""
import pytest

from pymoso.chnutils import solve
from pymoso.oracle import Oracle
from pymoso.problems.probsimpleso import ProbSimpleSO
from pymoso.solvers.rpe import RPE
from pymoso.solvers.rperle import RPERLE


class _Three(Oracle):
    def __init__(self, rng):
        self.num_obj = 3
        self.dim = 2
        super().__init__(rng)

    def g(self, x, rng):
        if not all(-10 <= v <= 10 for v in x):
            return False, ()
        z = rng.normalvariate(0, 1)
        return True, ((x[0] - 3) ** 2 + z, (x[1] + 2) ** 2 + z, (x[0] + x[1]) ** 2 + z)


@pytest.mark.parametrize('cls', (RPERLE, RPE))
def test_one_objective_raises_and_does_not_exit(cls):
    # SystemExit is not an Exception, so an exit escapes this and fails
    with pytest.raises(Exception):
        solve(ProbSimpleSO, cls, (5,), budget=300, seed=(1,) * 6)


@pytest.mark.parametrize('cls', (RPERLE, RPE))
def test_three_objectives_run(cls):
    res, _ = solve(_Three, cls, (0, 0), budget=500, seed=(1,) * 6)
    assert res
