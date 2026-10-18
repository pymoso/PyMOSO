"""
`quadratic`: NE's quadratic candidate, from the MATLAB R-SPLINE
(docs/RSPLINE.m, NE, lines 216-312; docs/phase7-plan.md, step 4).

Enumeration evaluates x + e_i and x - e_i for each coordinate i; with
the centre that is three points on a parabola. Where both neighbours
are feasible and the parabola is convex (a - 0.00005 > 0), the
coordinate takes the vertex, cast as MATLAB's int32() casts; otherwise
the centre's coordinate. ONE candidate is assembled from all
coordinates and evaluated, after every neighbour, so certification is
unchanged.

Under first-improvement (bestimprove off, the default) NE returns at
the first improving neighbour, so the candidate is formed only when
none improved -- and then y1 >= y2 and y3 >= y2 force a >= |b|, so
every vertex is within half a step of the centre. The candidate is the
centre except at exact ties. It is useful with bestimprove on.

Off by default: no golden moves. The estimates are planted in `gbar`.
"""
import math
import sys

import pytest

from pymoso import chnbase
from pymoso.chnbase import _matlab_int32, _quadratic_coordinate
from pymoso.chnutils import solve
from pymoso.layout import get_solv_prnstreams
from pymoso.prng import mrg32k3a
from pymoso.problems.probtpa import ProbTPA
from pymoso.problems.probtpc import ProbTPC
from pymoso.solvers.rminrle import RMINRLE
from pymoso.solvers.rpe import RPE
from pymoso.solvers.rperle import RPERLE
from pymoso.solvers.rspline import RSPLINE

INT32_MAX, INT32_MIN = 2 ** 31 - 1, -2 ** 31


# MATLAB's int32(): round half away from zero, saturate, NaN to 0.
@pytest.mark.parametrize("v, expected", [
    (2.5, 3), (-2.5, -3), (0.5, 1), (-0.5, -1), (4.5, 5), (-4.5, -5),   # Python's round() gives 2, -2, 0, 0, 4, -4
    (2.4, 2), (-2.4, -2), (2.6, 3), (-2.6, -3), (0.0, 0), (-0.0, 0),
    (0.49999999999999994, 0), (-0.49999999999999994, 0),                # floor(v + 0.5) would give 1
    (1.4999999999999998, 1), (7.0, 7),
    (float('nan'), 0), (float('inf'), INT32_MAX), (float('-inf'), INT32_MIN),
    (3e10, INT32_MAX), (-3e10, INT32_MIN),
    (2147483646.5, INT32_MAX), (2147483647.5, INT32_MAX), (-2147483648.5, INT32_MIN),
    (2147483645.4, 2147483645),
])
def test_the_cast_is_matlabs_int32(v, expected):
    r = _matlab_int32(v)
    assert r == expected and type(r) is int


def test_a_convex_parabola_gives_its_vertex():
    # (x - 13)^2 around x = 10: y1 = f(11) = 4, y2 = 9, y3 = f(9) = 16
    assert _quadratic_coordinate(10, 4.0, 9.0, 16.0) == 13


def test_the_vertex_is_rounded_half_away_from_zero():
    # a = 0.5, b = 0.5: vertex 5 - 0.5 = 4.5 -> 5 (Python's round: 4)
    assert _quadratic_coordinate(5, 1.0, 0.0, 0.0) == 5
    # vertex -5 - 0.5 = -5.5 -> -6 (Python's round: -6; and -4.5 -> -5)
    assert _quadratic_coordinate(-5, 1.0, 0.0, 0.0) == -6
    assert _quadratic_coordinate(-4, 1.0, 0.0, 0.0) == -5


def test_the_convexity_tolerance_is_strict_at_0_00005():
    # y1 = s, y3 = -s, y2 = -0.00005: a = 0.00005 exactly, b = s, so a
    # fit would put the vertex at 10 - s / 0.0001 = 0
    s = 0.001
    assert (s + -s) / 2.0 - (-0.00005) == 0.00005
    assert _quadratic_coordinate(10, s, -0.00005, -s) == 10            # not > 0: the centre
    # just below it, as computed: the centre (a > 0 alone would fit)
    assert _quadratic_coordinate(10, 0.00105, 0.0, -0.00095) == 10
    # above it: the vertex, 10 - 0.001 / 0.0002 = 5
    assert _quadratic_coordinate(10, s, -0.0001, -s) == 5


@pytest.mark.parametrize("y1, y3", [(4.0, None), (None, 16.0), (None, None)])
def test_an_infeasible_neighbour_means_no_fit(y1, y3):
    assert _quadratic_coordinate(10, y1, 9.0, y3) == 10


def test_a_concave_or_flat_parabola_means_the_centre():
    assert _quadratic_coordinate(10, 1.0, 9.0, 2.0) == 10     # a < 0
    assert _quadratic_coordinate(10, 9.0, 9.0, 9.0) == 10     # a = 0


def test_a_coordinate_that_fails_the_guard_is_0_not_the_centre():
    """Deliberately the MATLAB's (ixquad starts as zeros, line 230, and
    is written only when abs(xqnew) < 2147483646, lines 287-288)."""
    assert _quadratic_coordinate(2147483646, None, 9.0, None) == 0          # the centre's own value
    assert _quadratic_coordinate(-2147483646, 1.0, 9.0, 2.0) == 0
    assert _quadratic_coordinate(2147483645, None, 9.0, None) == 2147483645
    # a vertex past it: a = 0.5, b = -1e15, vertex 10 + 1e15 saturates, then 0
    assert _quadratic_coordinate(10, -1e15 + 0.5, 0.0, 1e15 + 0.5) == 0
    assert _quadratic_coordinate(-10, 1e15 + 0.5, 0.0, -1e15 + 0.5) == 0


def test_a_nan_vertex_is_0():
    assert _quadratic_coordinate(10, float('inf'), 0.0, float('inf')) == 0


# ---- the candidate inside ne, with planted estimates ----

CENTRE = (10, 10)
# f = (x - 13)^2 + (y - 8)^2: vertex (13, 8) in each coordinate
def f(p):
    return float((p[0] - 13) ** 2 + (p[1] - 8) ** 2)


NEIGHBOURS = [(11, 10), (9, 10), (10, 11), (10, 9)]     # visiting order


def _solver(**kwargs):
    orcstream, solvstream = get_solv_prnstreams((12345,) * 6, mrg32k3a)
    orc = ProbTPA(orcstream)
    orc.set_crnflag(False)
    solver = RMINRLE(orc, sprn=solvstream, x0=CENTRE, **kwargs)
    solver.m = 3
    solver.gbar, solver.sehat = {}, {}
    return solver


def _plant(solver, values, nobj=0):
    for x, v in values.items():
        solver.gbar[x] = (v, 0.0) if nobj == 0 else (0.0, v)
        solver.sehat[x] = (0.1, 0.1)


def _spy(solver):
    calls = []
    real = solver.estimate
    solver.estimate = lambda x, *a: (calls.append(x), real(x, *a))[1]
    return calls


def _run_ne(solver, values, nobj=0, **kw):
    _plant(solver, values, nobj)
    calls = _spy(solver)
    fx = (f(CENTRE), 0.0) if nobj == 0 else (0.0, f(CENTRE))
    out = solver.ne(CENTRE, fx, (0.1, 0.1), nobj, **kw)
    return out, calls


@pytest.mark.parametrize("nobj", [0, 1])
def test_with_best_improvement_the_candidate_is_the_vertex_and_wins(nobj):
    solver = _solver(bestimprove=1, quadratic=1)
    values = {p: f(p) for p in NEIGHBOURS + [(13, 8)]}
    (xs, fxs, _, n), calls = _run_ne(solver, values, nobj)
    assert calls == NEIGHBOURS + [(13, 8)]          # every neighbour, then one candidate
    assert xs == (13, 8) and fxs[nobj] == 0.0
    assert n == 5 * solver.m


def test_a_candidate_that_does_not_beat_the_best_is_charged_and_not_taken():
    solver = _solver(bestimprove=1, quadratic=1)
    values = {p: f(p) for p in NEIGHBOURS}
    values[(13, 8)] = 50.0
    (xs, _, _, n), calls = _run_ne(solver, values)
    assert calls[-1] == (13, 8) and xs == (11, 10) and n == 5 * solver.m


def test_a_candidate_that_only_ties_the_best_is_not_taken():
    """The same strict < as a neighbour."""
    solver = _solver(bestimprove=1, quadratic=1)
    values = {p: f(p) for p in NEIGHBOURS}
    values[(13, 8)] = f((11, 10))
    (xs, _, _, _), _ = _run_ne(solver, values)
    assert xs == (11, 10)


def test_an_infeasible_candidate_is_not_charged():
    solver = _solver(bestimprove=1, quadratic=1)
    values = {p: f(p) for p in NEIGHBOURS}
    _plant(solver, values)
    solver.gbar[(13, 8)] = (0.0, 99.0)                # infeasible by the constraint below
    solver.sehat[(13, 8)] = (0.1, 0.1)
    calls = _spy(solver)
    xs, _, _, n = solver.ne(CENTRE, (f(CENTRE), 0.0), (0.1, 0.1), 0, e=10.0, kcon=1)
    assert calls[-1] == (13, 8) and xs == (11, 10) and n == 4 * solver.m


def test_without_best_improvement_ne_returns_before_any_candidate():
    solver = _solver(quadratic=1)
    (xs, _, _, n), calls = _run_ne(solver, {p: f(p) for p in NEIGHBOURS + [(13, 8)]})
    assert calls == [(11, 10)] and xs == (11, 10) and n == solver.m


def test_without_best_improvement_and_nothing_improving_the_candidate_is_the_centre():
    """y1 >= y2 and y3 >= y2 force a >= |b|: each vertex within half a
    step. The centre is in gbar, so this costs no simulation; it is
    charged, as the MATLAB charges it."""
    solver = _solver(quadratic=1)
    values = {p: f(CENTRE) + 1.0 + k for k, p in enumerate(NEIGHBOURS)}
    values[CENTRE] = f(CENTRE)
    (xs, _, _, n), calls = _run_ne(solver, values)
    assert calls == NEIGHBOURS + [CENTRE] and xs == CENTRE and n == 5 * solver.m


def test_the_candidate_is_evaluated_even_when_it_is_the_centre():
    """No coordinate convex: the candidate is the centre, evaluated
    anyway (as specified; skipping it is a candidate improvement)."""
    solver = _solver(bestimprove=1, quadratic=1)
    values = {(11, 10): 1.0, (9, 10): 1.0, (10, 11): 1.0, (10, 9): 1.0, CENTRE: 5.0}
    (xs, _, _, _), calls = _run_ne(solver, values)
    assert calls[-1] == CENTRE and xs == (11, 10)


def test_an_infeasible_neighbour_keeps_the_centres_coordinate():
    solver = _solver(bestimprove=1, quadratic=1)
    values = {p: f(p) for p in NEIGHBOURS if p != (9, 10)}
    _plant(solver, values)
    solver.gbar[(9, 10)] = (0.0, 99.0)
    solver.sehat[(9, 10)] = (0.1, 0.1)
    values2 = {(10, 8): 4.0}
    _plant(solver, values2)
    calls = _spy(solver)
    solver.ne(CENTRE, (f(CENTRE), 0.0), (0.1, 0.1), 0, e=10.0, kcon=1)
    assert calls[-1] == (10, 8)                       # coordinate 0 unfitted: the centre's 10


def test_the_quadratic_candidate_needs_radius_1():
    with pytest.raises(ValueError, match='quadratic'):
        _solver(quadratic=1, radius=2)


@pytest.mark.parametrize("bad", [2, 0.5, -1])
def test_the_toggle_is_0_or_1(bad):
    with pytest.raises(ValueError, match='quadratic'):
        _solver(quadratic=bad)


def test_off_is_the_default():
    assert _solver().quadratic is False


@pytest.mark.parametrize("solver, problem, x0", [
    (RSPLINE, ProbTPA, (30, 30)), (RPERLE, ProbTPA, (30, 30)),
    (RMINRLE, ProbTPC, (3, 3, 3)), (RPE, ProbTPA, (30, 30)),
])
def test_the_toggle_reaches_ne_through_get_min_and_the_solvers_own_search(solver, problem, x0, monkeypatch):
    seen = {}
    real = chnbase.RASolver.ne

    def ne(self, *a, **k):
        caller = sys._getframe(2).f_code.co_name      # ne <- spline <- caller
        seen.setdefault(caller, set()).add(self.quadratic)
        return real(self, *a, **k)
    monkeypatch.setattr(chnbase.RASolver, 'ne', ne)
    solve(problem, solver, x0, budget=1500, seed=(12345,) * 6, quadratic=1, bestimprove=1)
    assert seen and all(v == {True} for v in seen.values()), seen
    assert ('spsolve' if solver is RSPLINE else 'get_min') in seen


def test_on_with_best_improvement_it_changes_what_a_run_does():
    best = solve(ProbTPA, RPERLE, (30, 30), budget=3000, seed=(12345,) * 6, bestimprove=1)
    both = solve(ProbTPA, RPERLE, (30, 30), budget=3000, seed=(12345,) * 6, bestimprove=1, quadratic=1)
    assert best != both
