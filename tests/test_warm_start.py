"""A warm start is the previous RA iteration's solution, every point of
which that iteration estimated feasible; x0 was estimated feasible in
iteration 1. When g() decides feasibility from x alone, neither can be
found infeasible later. WarmStartInfeasible is raised where the solvers
that rely on this re-estimate their warm start (KNOWN_ISSUES.md issue
19).

Before it, such a warm start was reported as something else: R-MinRLE
read its estimate anyway and failed with a bare KeyError ("Unable to
run accel(). Message: (2, 17)"), and R-SPLINE said "x0=(4, 9) is
infeasible" of a point the caller never passed. R-PE and R-PERLE
dropped it without a word: pe replaced its warm start with the part of
it that came back feasible.

The tests inject the warm start: a point outside ProbTPA's box, handed
to spsolve as if the previous iteration had returned it. The whole runs
use RandomEdgeBi, a g() whose feasibility depends on its random
numbers, which is the only way it has been seen to happen."""
import multiprocessing
import pickle

import pytest

from pymoso.chnbase import WarmStartInfeasible
from pymoso.chnutils import solve, testsolve
from pymoso.layout import get_solv_prnstreams
from pymoso.prng import mrg32k3a
from pymoso.problems.probtpa import ProbTPA
from pymoso.solvers.rminrle import RMINRLE
from pymoso.solvers.rpe import RPE
from pymoso.solvers.rperle import RPERLE
from pymoso.solvers.rspline import RSPLINE

from _random_feasibility import RandomEdgeBi, RandomEdgeTester

SEED = (12345,) * 6
OUTSIDE = (-1, 5)       # not in ProbTPA's box at any sample size


def _solver(cls, x0, nu):
    """A solver as rasolve leaves it at the start of iteration nu."""
    orcstream, solvstream = get_solv_prnstreams(SEED, mrg32k3a)
    orc = ProbTPA(orcstream)
    orc.set_crnflag(False)
    orc.set_simpar(1)
    solver = cls(orc, sprn=solvstream, x0=x0)
    solver.nu = nu
    solver.m = solver.calc_m(nu)
    solver.b = solver.calc_b(nu)
    solver.gbar = {}
    solver.sehat = {}
    return solver


def _check(e, points, iteration, solver):
    assert (e.points, e.iteration, e.solver) == (points, iteration, solver)
    message = str(e)
    assert message.startswith('{0}: the point {1}'.format(solver, points[0]))
    assert 'carried into iteration {0} as feasible'.format(iteration) in message
    # the likelier cause first, a defect in PyMOSO second
    assert message.index('depends on its random numbers') < message.index('defect in PyMOSO')
    assert 'x0=' not in message


def test_rspline_reports_an_infeasible_warm_start_as_that_not_as_x0():
    solver = _solver(RSPLINE, (40, 40), 2)
    with pytest.raises(WarmStartInfeasible) as info:
        solver.spsolve({OUTSIDE})
    _check(info.value, (OUTSIDE,), 2, 'RSPLINE')


@pytest.mark.parametrize("cls", [RMINRLE, RPE, RPERLE])
def test_a_set_warm_start_with_an_infeasible_point_is_reported_not_dropped(cls):
    """R-MinRLE used to fail with a KeyError, R-PE and R-PERLE to drop
    the point. R-MinRLE and R-PERLE go through RLESolver.spsolve, whose
    wrapper would otherwise report it as "Unable to run accel()"."""
    solver = _solver(cls, (40, 40), 3)
    with pytest.raises(WarmStartInfeasible) as info:
        solver.spsolve({OUTSIDE, (40, 41)})
    _check(info.value, (OUTSIDE,), 3, cls.__name__)


@pytest.mark.parametrize("cls", [RMINRLE, RPE, RPERLE])
def test_x0_found_infeasible_after_iteration_1_is_the_same_invariant(cls):
    """x0 was estimated feasible in iteration 1 and is re-estimated in
    every later one; "RA solvers require a feasible starting point"
    would misdirect."""
    solver = _solver(cls, OUTSIDE, 2)
    with pytest.raises(WarmStartInfeasible) as info:
        solver.spsolve({(40, 40)})
    _check(info.value, (OUTSIDE,), 2, cls.__name__)


@pytest.mark.parametrize("cls", [RSPLINE, RMINRLE, RPE, RPERLE])
def test_an_infeasible_x0_in_iteration_1_is_still_the_callers_error(cls):
    solver = _solver(cls, OUTSIDE, 1)
    with pytest.raises(ValueError, match=r"x0=\(-1, 5\) is infeasible"):
        solver.spsolve({OUTSIDE})


def test_several_points_are_all_recorded_and_the_first_named():
    e = WarmStartInfeasible([(-2, 5), (-1, 5), (60, 0)], 4, 'RMINRLE')
    assert str(e).startswith('RMINRLE: the point (-2, 5) (and 2 others), carried into iteration 4')


@pytest.mark.parametrize("solver, x0", [(RSPLINE, (6, 20)), (RMINRLE, (6, 20)), (RPE, (3, 20)), (RPERLE, (3, 20))])
def test_a_whole_run_with_random_feasibility_raises_it(solver, x0):
    """The runs that failed with "x0=(4, 10) is infeasible" and with a
    KeyError for (2, 17), and two whose warm start pe used to filter."""
    with pytest.raises(WarmStartInfeasible) as info:
        solve(RandomEdgeBi, solver, x0, budget=3000, seed=SEED, crn=False)
    e = info.value
    assert e.iteration > 1 and e.solver == solver.__name__
    assert all(0 <= x[0] <= 5 for x in e.points)


def test_it_survives_pickling_with_its_attributes():
    e = WarmStartInfeasible([(2, 17)], 8, 'RMINRLE')
    back = pickle.loads(pickle.dumps(e))
    assert type(back) is WarmStartInfeasible
    assert (back.points, back.iteration, back.solver, str(back)) == (e.points, e.iteration, e.solver, str(e))


@pytest.mark.timeout(120)
@pytest.mark.parametrize("method", multiprocessing.get_all_start_methods())
def test_it_reaches_the_caller_from_a_path_worker(method, monkeypatch):
    kwargs = dict(budget=3000, seed=SEED, isp=2, crn=False)
    with pytest.raises(WarmStartInfeasible) as serial:
        testsolve(RandomEdgeTester, RMINRLE, (6, 20), proc=1, **kwargs)
    monkeypatch.setattr(multiprocessing, "get_context",
                        lambda m=None, _real=multiprocessing.get_context: _real(m or method))
    with pytest.raises(WarmStartInfeasible) as parallel:
        testsolve(RandomEdgeTester, RMINRLE, (6, 20), proc=2, **kwargs)
    assert str(parallel.value) == str(serial.value)
