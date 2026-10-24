"""
SPLI returns at an infeasible line-search point: "if x1 is infeasible
return" (R-SPLINE, Algorithm 4, step 13). The code ended the line search
there and then started a new gradient whenever the line search had
taken three steps or more (docs/algorithm-audit.md, finding 5).

PLI and the estimates are scripted, in one dimension: the gradient is
always 1, points below 5 are infeasible, and a feasible point's value is
the point itself. From 10 the line search visits 8, 6 and 2.
"""
import random

from pymoso.chnbase import RASolver


class _Scripted:
    def __init__(self, infeasible_below):
        self.sprn = random.Random(0)
        self.m = 1
        self.infeasible_below = infeasible_below
        self.gradients = 0
        self.visited = []

    def pli(self, x, e, nobj, kcon):
        self.gradients += 1
        return [1.0], None, None, None

    def estimate(self, x, e, kcon):
        self.visited.append(x)
        if x[0] < self.infeasible_below:
            return False, None, None
        return True, (float(x[0]),), (0.0,)


def _spli(solver):
    return RASolver.spli(solver, (10,), (10.0,), (0.0,), float('inf'), 0, 0, 100)


def test_an_infeasible_third_step_returns():
    solver = _Scripted(infeasible_below=5)
    xs, fxs, _, n = _spli(solver)
    assert solver.visited == [(8,), (6,), (2,)]
    assert solver.gradients == 1
    assert (xs, fxs, n) == ((6,), (6.0,), 2 + 2)


def test_an_infeasible_first_step_returns_as_before():
    solver = _Scripted(infeasible_below=9)
    xs, _, _, n = _spli(solver)
    assert solver.visited == [(8,)]
    assert solver.gradients == 1
    assert (xs, n) == ((10,), 2)
