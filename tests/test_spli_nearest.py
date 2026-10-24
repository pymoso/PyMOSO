"""
SPLI's line search shifts each point to the nearest integer solution
(R-SPLINE, Algorithm 4, step 12; §6(iii)), rounding halves up as the
MATLAB does, floor(x + 0.5) (RSPLINE.m). The code floored
(docs/algorithm-audit.md, finding 4).

PLI is scripted to give the gradient (3, 4), of length 5, so the first
step of 2 from (10, 10) lands at (8.8, 8.4): (9, 8) to the nearest,
(8, 8) floored. The estimate reports every point infeasible, so SPLI
returns after that one step (finding 5).
"""
import random

from pymoso.chnbase import RASolver


class _Scripted:
    def __init__(self, gradient):
        self.sprn = random.Random(0)
        self.m = 1
        self.gradient = gradient
        self.visited = []

    def pli(self, x, e, nobj, kcon):
        return list(self.gradient), None, None, None

    def estimate(self, x, e, kcon):
        self.visited.append(x)
        return False, None, None


def _first_step(gradient, x0):
    solver = _Scripted(gradient)
    RASolver.spli(solver, x0, (0.0,), (0.0,), float('inf'), 0, 0, 100)
    return solver.visited


def test_the_line_search_goes_to_the_nearest_integer():
    assert _first_step((3.0, 4.0), (10, 10)) == [(9, 8)]


def test_negative_components_round_to_the_nearest_too():
    """From (-10, -10) with the gradient (-3, -4) the step lands at
    (-8.8, -8.4): (-9, -8) to the nearest, (-9, -9) floored."""
    assert _first_step((-3.0, -4.0), (-10, -10)) == [(-9, -8)]


def test_a_half_rounds_up():
    """Sixteen components of 1 have length exactly 4, so a step of 2
    takes each by exactly 0.5: from 1 to 0.5, which rounds up to 1
    (Python's round() would give 0, and floor 0)."""
    assert _first_step((1.0,) * 16, (1,) * 16) == [(1,) * 16]
