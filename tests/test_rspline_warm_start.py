"""R-SPLINE starts each RA iteration's search from its warm start, the
previous iteration's minimizer, and does not estimate x0 again.

Phase 7 briefly made it re-estimate x0 every iteration and restart from
x0 when x0's estimate was better, as R-PE, R-PERLE and R-MinRLE keep x0
as a candidate. That was measured to make R-SPLINE worse at practical
budgets and reverted (docs/phase7-plan.md, step 7, "x0 re-estimation";
the measurement is scratch/phase7/rspline_x0_measure.py). This holds
R-SPLINE to the reverted behaviour."""
import contextlib
import io

from pymoso.layout import get_solv_prnstreams
from pymoso.paths import isp_run
from pymoso.prng import mrg32k3a
from pymoso.problems.probsimpleso import ProbSimpleSO
from pymoso.problems.probtpa import ProbTPA
from pymoso.solvers.rspline import RSPLINE

SEED = (12345,) * 6
NEAR = (20, 10)         # near ProbTPA's first objective's minimum
FAR = (50, 50)


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


def test_the_search_starts_from_the_warm_start_even_when_x0_is_better():
    solver = _solver(NEAR, 2)
    starts = []
    real = solver.spline
    solver.spline = lambda x0, *a, **k: (starts.append(x0), real(x0, *a, **k))[1]
    solver.spsolve({FAR})
    assert starts == [FAR]


def test_x0_is_not_estimated_after_iteration_1():
    seen = []
    real = RSPLINE.spsolve

    def spsolve(self, warm_start):
        before = set(self.gbar)
        out = real(self, warm_start)
        if self.nu > 1 and self.x0 not in warm_start:
            seen.append(self.x0 in self.gbar and self.x0 not in before)
        return out
    orcstream, solvstream = get_solv_prnstreams(SEED, mrg32k3a)
    orc = ProbSimpleSO(orcstream)
    orc.set_crnflag(False)
    solver = type('Spy', (RSPLINE,), {'spsolve': spsolve})
    with orc.set_simpar(1):
        isp_run(solver, 2000, orc, solvprn=solvstream, x0=(97,))
    assert len(seen) > 10 and not any(seen)
