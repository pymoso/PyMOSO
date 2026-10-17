"""
`bestimprove`: NE scans every neighbour and takes the best, as the
MATLAB R-SPLINE does (docs/RSPLINE.m, NE, lines 239-291), instead of
returning at the first improving one, which is PyMOSO's own rule and
stays the default (docs/phase7-plan.md, step 5).

Off by default: no golden moves (tests/test_golden.py). The comparison
is PyMOSO's strict `<`, not the MATLAB's `+ 0.00005 <`, so the scan rule
is the only difference (step 7's audit has why).

The estimates are planted in `gbar`, which `estimate` returns without
simulating, so each answer below is known exactly.
"""
import sys

import pytest

from pymoso.chnutils import solve
from pymoso.layout import get_solv_prnstreams
from pymoso.prng import mrg32k3a
from pymoso.problems.probtpa import ProbTPA
from pymoso.problems.probtpc import ProbTPC
from pymoso import chnbase
from pymoso.solvers.rminrle import RMINRLE
from pymoso.solvers.rpe import RPE
from pymoso.solvers.rperle import RPERLE
from pymoso.solvers.rspline import RSPLINE

CENTRE = (10, 10)


def _solver(radius=1, **kwargs):
    orcstream, solvstream = get_solv_prnstreams((12345,) * 6, mrg32k3a)
    orc = ProbTPA(orcstream)
    orc.set_crnflag(False)
    solver = RMINRLE(orc, sprn=solvstream, x0=CENTRE, radius=radius, **kwargs)
    solver.m = 3
    solver.gbar, solver.sehat = {}, {}
    return solver


def _plant(solver, values):
    for x, f in values.items():
        solver.gbar[x] = (f, 0.0)
        solver.sehat[x] = (0.1, 0.1)


# Visiting order at radius 1: (11,10), (9,10), (10,11), (10,9).
NEIGHBOURS = {(11, 10): 4.0, (9, 10): 6.0, (10, 11): 2.0, (10, 9): 1.0}


@pytest.mark.parametrize("best, expected, evaluated", [
    (0, (11, 10), 1),       # the first that improves on 5.0
    (1, (10, 9), 4),        # the best of all four
])
def test_first_or_best_improvement_at_radius_1(best, expected, evaluated):
    solver = _solver(bestimprove=best)
    _plant(solver, NEIGHBOURS)
    xs, fxs, _, n = solver.ne(CENTRE, (5.0, 0.0), (0.1, 0.1), 0)
    assert (xs, fxs[0]) == (expected, NEIGHBOURS[expected])
    assert n == evaluated * solver.m


def test_best_improvement_keeps_the_first_of_equal_bests():
    solver = _solver(bestimprove=1)
    _plant(solver, {(11, 10): 7.0, (9, 10): 1.0, (10, 11): 1.0, (10, 9): 3.0})
    assert solver.ne(CENTRE, (5.0, 0.0), (0.1, 0.1), 0)[0] == (9, 10)


def test_best_improvement_goes_on_past_an_improving_minus_neighbour():
    """(9, 10), x - e_1, improves first; (10, 9) is better still."""
    solver = _solver(bestimprove=1)
    _plant(solver, {(11, 10): 7.0, (9, 10): 3.0, (10, 11): 8.0, (10, 9): 1.0})
    assert solver.ne(CENTRE, (5.0, 0.0), (0.1, 0.1), 0)[0] == (10, 9)


def test_best_improvement_with_no_improving_neighbour_returns_the_centre():
    solver = _solver(bestimprove=1)
    _plant(solver, {x: 9.0 for x in NEIGHBOURS})
    xs, fxs, _, n = solver.ne(CENTRE, (5.0, 0.0), (0.1, 0.1), 0)
    assert xs == CENTRE and n == 4 * solver.m


def test_an_infeasible_neighbour_is_skipped_and_not_charged():
    """Infeasible by the constraint: objective 1 above e."""
    solver = _solver(bestimprove=1)
    values = dict(NEIGHBOURS)
    _plant(solver, values)
    solver.gbar[(10, 9)] = (1.0, 99.0)
    xs, _, _, n = solver.ne(CENTRE, (5.0, 0.0), (0.1, 0.1), 0, e=10.0, kcon=1)
    assert xs == (10, 11) and n == 3 * solver.m


@pytest.mark.parametrize("best, expected", [(0, None), (1, 'best')])
def test_best_improvement_at_radius_2(best, expected):
    solver = _solver(radius=2, bestimprove=best)
    nbors = list(chnbase.get_nbors(CENTRE, 2))
    values = {x: 9.0 - 0.1 * k for k, x in enumerate(nbors)}   # every one improves on 9.5
    _plant(solver, values)
    xs, _, _, n = solver.ne(CENTRE, (9.5, 0.0), (0.1, 0.1), 0)
    if expected is None:
        assert xs == nbors[0] and n == solver.m
    else:
        assert xs == nbors[-1] and n == len(nbors) * solver.m


@pytest.mark.parametrize("bad", [2, 0.5, -1, float('nan')])
def test_the_toggle_is_0_or_1(bad):
    with pytest.raises(ValueError, match='bestimprove'):
        _solver(bestimprove=bad)


def test_off_is_the_default_and_the_same_state_as_passing_it():
    assert _solver().bestimprove is False
    assert _solver(bestimprove=0).bestimprove is False
    assert _solver(bestimprove=1.0).bestimprove is True


@pytest.mark.parametrize("solver, problem, x0", [
    (RSPLINE, ProbTPA, (30, 30)), (RPERLE, ProbTPA, (30, 30)),
    (RMINRLE, ProbTPC, (3, 3, 3)), (RPE, ProbTPA, (30, 30)),
])
def test_the_toggle_reaches_ne_through_get_min_and_the_solvers_own_search(solver, problem, x0, monkeypatch):
    """Four solvers reach ne through spline: from RASolver.get_min
    (R-PE, R-PERLE, R-MinRLE) and from each solver's own call (pe in
    R-PE and R-PERLE, spsolve in R-SPLINE)."""
    seen = {}
    real = chnbase.RASolver.ne

    def ne(self, *a, **k):
        caller = sys._getframe(2).f_code.co_name      # ne <- spline <- caller
        seen.setdefault(caller, set()).add(self.bestimprove)
        return real(self, *a, **k)
    monkeypatch.setattr(chnbase.RASolver, 'ne', ne)
    solve(problem, solver, x0, budget=1500, seed=(12345,) * 6, bestimprove=1)
    assert seen and all(v == {True} for v in seen.values()), seen
    if solver is RSPLINE:
        assert 'spsolve' in seen
    else:
        assert 'get_min' in seen
    if solver in (RPE, RPERLE):
        assert 'pe' in seen


def test_on_it_changes_what_a_run_does():
    off = solve(ProbTPA, RPERLE, (30, 30), budget=3000, seed=(12345,) * 6)
    on = solve(ProbTPA, RPERLE, (30, 30), budget=3000, seed=(12345,) * 6, bestimprove=1)
    assert off != on
