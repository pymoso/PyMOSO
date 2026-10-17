"""R-SPLINE estimates x0 again in every RA iteration and starts its
search from x0 when x0's estimate is better than the warm start's, as
R-PE, R-PERLE and R-MinRLE already do through get_min. Before Phase 7
its warm start was the previous minimizer alone (docs/phase7-plan.md,
step 7)."""
import contextlib
import io

import pytest

from pymoso.layout import get_solv_prnstreams
from pymoso.paths import isp_run
from pymoso.prng import mrg32k3a
from pymoso.problems.probsimpleso import ProbSimpleSO
from pymoso.problems.probtpa import ProbTPA
from pymoso.solvers.rspline import RSPLINE

SEED = (12345,) * 6
NEAR = (20, 10)         # near ProbTPA's first objective's minimum
FAR = (50, 50)          # far from it


def _solver(x0, nu):
    orcstream, solvstream = get_solv_prnstreams(SEED, mrg32k3a)
    orc = ProbTPA(orcstream)
    orc.set_crnflag(False)
    orc.set_simpar(1)
    with contextlib.redirect_stdout(io.StringIO()):     # the single-objective warning
        solver = RSPLINE(orc, sprn=solvstream, x0=x0)
    solver.nu = nu
    solver.m = solver.calc_m(nu)
    solver.b = solver.calc_b(nu)
    solver.gbar = {}
    solver.sehat = {}
    return solver


def _start(solver, warm_start):
    """The point spline was started from."""
    starts = []
    real = solver.spline
    solver.spline = lambda x0, *a, **k: (starts.append(x0), real(x0, *a, **k))[1]
    solver.spsolve({warm_start})
    assert len(starts) == 1
    return starts[0]


@pytest.mark.parametrize("x0, warm_start, expected", [
    (NEAR, FAR, NEAR),      # x0 better: start from x0
    (FAR, NEAR, NEAR),      # warm start better: keep it
])
def test_the_search_starts_from_the_better_of_x0_and_the_warm_start(x0, warm_start, expected):
    solver = _solver(x0, 2)
    assert _start(solver, warm_start) == expected
    assert solver.gbar[x0][0] != solver.gbar[warm_start][0]


def test_iteration_1_starts_from_x0():
    assert _start(_solver(NEAR, 1), NEAR) == NEAR


def test_x0_is_estimated_in_every_iteration():
    seen = []
    real = RSPLINE.spsolve

    def spsolve(self, warm_start):
        out = real(self, warm_start)
        seen.append(self.x0 in self.gbar)
        return out
    orcstream, solvstream = get_solv_prnstreams(SEED, mrg32k3a)
    orc = ProbSimpleSO(orcstream)
    orc.set_crnflag(False)
    solver = type('Spy', (RSPLINE,), {'spsolve': spsolve})
    with orc.set_simpar(1):
        isp_run(solver, 2000, orc, solvprn=solvstream, x0=(97,))
    assert len(seen) > 10 and all(seen)
