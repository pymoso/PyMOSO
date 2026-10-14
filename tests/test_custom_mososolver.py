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

from _custom_solvers import DocumentedKeysOnly, NoConstructor, ReportsItsHighWaterMark
from pymoso.chnbase import MOSOSolver
from pymoso.prng import mrg32k3a

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


# ---------------------------------------------------------------------------
# x0 and sprn reach a MOSOSolver through the base class (Phase 6). solve()
# and testsolve() always pass both. MOSOSolver.__init__ took only the
# oracle, so a subclass that did not take them itself failed with
# "unexpected keyword argument 'x0'" -- in every released version.
# ---------------------------------------------------------------------------

def test_a_solver_with_no_constructor_receives_x0_and_sprn():
    soln, _ = solve(ProbTPA, NoConstructor, (40, 40), budget=50, seed=SEED)
    assert soln == {(40, 40)}
    res, _ = testsolve(TPATester, NoConstructor, (40, 40), budget=50, seed=SEED, isp=2, proc=2)
    assert res[1]['itersoln'][0] == {(40, 40)}


def test_it_computes_what_a_solver_taking_them_itself_computes():
    kwargs = dict(budget=50, seed=SEED, isp=2)
    assert testsolve(TPATester, NoConstructor, (40, 40), **kwargs) == \
        testsolve(TPATester, DocumentedKeysOnly, (40, 40), **kwargs)


def _oracle():
    orc = ProbTPA(mrg32k3a.MRG32k3a(SEED))
    orc.set_crnflag(False)
    return orc


def test_the_base_sets_them_and_leaves_them_none_when_not_given():
    sprn = mrg32k3a.MRG32k3a((1, 2, 3, 4, 5, 6))
    solver = MOSOSolver(_oracle(), x0=(40, 40), sprn=sprn)
    assert solver.x0 == (40, 40) and solver.sprn is sprn
    bare = MOSOSolver(_oracle())
    assert bare.x0 is None and bare.sprn is None


def test_a_value_a_subclass_set_before_calling_the_base_is_kept():
    """How MOCOMPASS, MOPBnB, RASolver and 1.x custom solvers are
    written: take x0 and sprn out of kwargs, set them, then call the
    base without them."""
    sprn = mrg32k3a.MRG32k3a((1, 2, 3, 4, 5, 6))
    solver = DocumentedKeysOnly(_oracle(), x0=(40, 40), sprn=sprn)
    assert solver.x0 == (40, 40) and solver.sprn is sprn


def test_an_unknown_parameter_is_still_refused_by_name():
    with pytest.raises(TypeError, match="radius"):
        solve(ProbTPA, NoConstructor, (40, 40), budget=50, seed=SEED, radius=2)
