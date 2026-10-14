"""
A MOSOSolver written to the README's contract works with solve() and
testsolve().

The README tells a MOSOSolver author to return three keys: itersoln,
simcalls and endseed. testsolve() also reads a fourth,
oracle_high_water_mark, to compute the run's end seed across sample
paths (docs/rng-interface-design.md §12 step 8). From that change until
Phase 6, a solver returning only the documented three raised KeyError
in testsolve() -- MOCOMPASS and MOPBnB passed only because they add the
key themselves. The framework now fills it in from the oracle it
handed the solver.
"""
import pytest

from pymoso.chnutils import solve, testsolve
from pymoso.problems.probtpa import ProbTPA
from pymoso.testers.tpatester import TPATester

from _custom_solvers import DocumentedKeysOnly, ReportsItsHighWaterMark

SEED = (12345,) * 6


def test_solve_runs_a_solver_returning_the_documented_keys():
    soln, endseed = solve(ProbTPA, DocumentedKeysOnly, (40, 40), budget=50, seed=SEED)
    assert soln == {(40, 40)}


@pytest.mark.parametrize("proc", [1, 2])
def test_testsolve_runs_it_and_computes_the_same_end_seed(proc):
    kwargs = dict(budget=50, seed=SEED, isp=2, proc=proc)
    documented = testsolve(TPATester, DocumentedKeysOnly, (40, 40), **kwargs)
    reporting = testsolve(TPATester, ReportsItsHighWaterMark, (40, 40), **kwargs)
    assert documented[1] == reporting[1]
    assert [documented[0][t]['itersoln'] for t in (0, 1)] == [reporting[0][t]['itersoln'] for t in (0, 1)]
