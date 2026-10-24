"""
R-SPLINE on a multi-objective problem minimizes the first objective
(README, "R-SPLINE"), silently: it is documented, so it is not
announced at run time.
"""
from pymoso.chnutils import solve
from pymoso.oracle import Oracle
from pymoso.prng import mrg32k3a
from pymoso.problems.probtpa import ProbTPA
from pymoso.solvers.rspline import RSPLINE


class _FirstOfTPA(Oracle):
    """ProbTPA's first objective alone, from the same random numbers."""
    def __init__(self, rng):
        self.num_obj = 1
        self.dim = 2
        self._tpa = ProbTPA(rng)
        super().__init__(rng)

    def g(self, x, rng):
        isfeas, objs = self._tpa.g(x, rng)
        return isfeas, (objs[0],) if isfeas else (None,)


def test_rspline_minimizes_the_first_objective_of_a_multi_objective_problem():
    for seed in range(1, 6):
        kw = dict(budget=2000, seed=(seed,) * 6, simpar=1, crn=False)
        both, _ = solve(ProbTPA, RSPLINE, (20, 20), **kw)
        first, _ = solve(_FirstOfTPA, RSPLINE, (20, 20), **kw)
        assert both == first, seed


def test_rspline_says_nothing_about_a_multi_objective_problem(capsys):
    RSPLINE(ProbTPA(mrg32k3a.stream_at(mrg32k3a.DEFAULT_SEED, 1, 0)), sprn=None, x0=(20, 20))
    assert capsys.readouterr().out == ''
