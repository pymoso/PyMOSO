"""
PE's traceback (R-PERLE preprint, Algorithm 2, steps 20-24) stops at
the larger of L, the constrained objective's lower start, and the
highest upper bound, below the current epsilon, of the intervals on
the constrained objective -- the objective k_opt constrains. Until
2.0 the code read the intervals left over from the last pass of the
loop over objectives, which are the other objective's whenever k_opt
is not the last one (docs/algorithm-audit.md, finding 1).

The scenario has three points with no sampling error, so the intervals
are their values, and both objectives get two epsilon values, so
k_opt is objective 0 and the traceback constrains objective 1:

    point   objective 0   objective 1
    P            0            20
    Q            3             7
    R           10             0

On objective 1 the epsilons are 7 and 20 and the bounds below them
are none (so L = 0) and 7. On objective 0 the bounds are 3 and 10. A
stub SPLINE returns a point 2 below the constraint each time, and the
step back is the 1e-6 used when the standard error is 0, so the
traceback from 7 calls SPLINE at 7, 5, 3 and 1 (stopping at 0) and
from 20 at 20, 18, ..., 8 (stopping at 7). Reading objective 0's
bounds stops them at 3 and 10 instead.

The same scenario has tied counts, so it also checks the tie-break
(Algorithm 2, steps 13-14: "ties are broken randomly"): until 2.0 a
tie always went to objective 0 (docs/algorithm-audit.md, finding 7).
It now draws from the solver's stream, and only on a tie.
"""
import pytest

from pymoso.solvers.rpe import RPE
from pymoso.solvers.rperle import RPERLE

P, Q, R = (0,), (1,), (2,)
VALUES = {P: (0.0, 20.0), Q: (3.0, 7.0), R: (10.0, 0.0)}


class _Scripted:
    """A solver stream that returns the given values, and counts."""
    def __init__(self, *values):
        self.values = list(values)
        self.drawn = 0

    def random(self):
        self.drawn += 1
        return self.values.pop(0)


def _solver(cls, sprn=None):
    solver = cls.__new__(cls)
    solver.sprn = sprn if sprn is not None else _Scripted(0.25)
    solver.x0 = P
    solver.nu = 1
    solver.m = 10
    solver.num_obj = 2
    solver.betaeps = 0.5
    solver.gbar = dict(VALUES)
    solver.sehat = {x: (0.0, 0.0) for x in VALUES}
    solver.upsample = lambda points: None
    solver.get_min = lambda points: {P, Q, R}
    solver.remove_nlwep = lambda points: (set(), set())
    solver.calls = []

    def spline(x, eps, k_opt, k_con):
        solver.minimized = k_opt
        assert k_con == 1 - k_opt
        solver.calls.append(eps)
        found = (100 + len(solver.calls),)
        solver.gbar[found] = (eps - 2, 50.0) if k_con == 0 else (50.0, eps - 2)
        solver.sehat[found] = (0.0, 0.0)
        return set(), found, solver.gbar[found], solver.sehat[found]
    solver.spline = spline
    return solver


@pytest.mark.parametrize('cls', (RPERLE, RPE))
def test_traceback_stops_at_the_constrained_objectives_bound(cls):
    solver = _solver(cls)
    solver.pe(set())
    assert solver.minimized == 0
    from_7 = [e for e in solver.calls if e <= 7]
    from_20 = [e for e in solver.calls if e > 7]
    assert from_7 == pytest.approx([7, 5, 3, 1], abs=1e-4)
    assert from_20 == pytest.approx([20, 18, 16, 14, 12, 10, 8], abs=1e-4)


@pytest.mark.parametrize('cls', (RPERLE, RPE))
@pytest.mark.parametrize('draw, minimized', ((0.25, 0), (0.75, 1)))
def test_a_tie_is_broken_by_one_draw_from_the_solver_stream(cls, draw, minimized):
    sprn = _Scripted(draw)
    solver = _solver(cls, sprn)
    solver.pe(set())
    assert solver.minimized == minimized
    assert sprn.drawn == 1


@pytest.mark.parametrize('cls', (RPERLE, RPE))
def test_no_draw_without_a_tie(cls):
    # Q at (3, 19) with a standard error of 2 on objective 1 (a
    # relaxation of 2 at the default beta): its interval there, (17, 21],
    # holds P's 20, so objective 1 has one epsilon, 17, against objective
    # 0's two. Objective 0 is minimized without a tie, and nothing is drawn
    sprn = _Scripted()
    solver = _solver(cls, sprn)
    solver.gbar[Q] = (3.0, 19.0)
    solver.sehat[Q] = (0.0, 2.0)
    solver.pe(set())
    assert solver.minimized == 0
    assert sprn.drawn == 0
