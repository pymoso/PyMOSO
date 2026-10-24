"""
SPLINE stops when its calls exceed the search limit b, not when they
reach it: "n > b_k" in the R-SPLINE paper (Algorithm 2, step 7) and
"b* > b" in the R-PERLE preprint (Algorithm 4, step 8). The code
stopped at n >= b (docs/algorithm-audit.md, finding 14).

SPLI and NE are scripted here so each pass uses a known number of calls
and NE always improves, leaving the limit as the only reason to stop.
"""
import pytest

from pymoso.chnbase import RASolver


class _Scripted:
    """Just what RASolver.spline reads: the cache, b, and SPLI and NE."""

    def __init__(self, b, per_pass):
        self.b = b
        self.per_pass = per_pass
        self.passes = 0
        self.gbar = {(0,): (10.0,)}
        self.sehat = {(0,): (1.0,)}

    def spli(self, x, fx, sex, e, nobj, kcon, b):
        self.passes += 1
        return x, fx, sex, self.per_pass

    def ne(self, x, fx, sex, nobj, e, kcon):
        better = (x[0] + 1,)
        return better, (fx[0] - 1,), sex, 0


@pytest.mark.parametrize("b, per_pass, passes", [
    (6, 3, 3),      # 3, 6 (not over), 9
    (6, 2, 4),      # 2, 4, 6 (not over), 8
    (6, 4, 2),      # 4, 8
    (6, 7, 1),      # 7
])
def test_spline_stops_once_its_calls_exceed_b(b, per_pass, passes):
    solver = _Scripted(b, per_pass)
    RASolver.spline(solver, (0,))
    assert solver.passes == passes
