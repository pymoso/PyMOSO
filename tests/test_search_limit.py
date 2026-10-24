"""
The search limit b (`RASolver.calc_b`) is positive in one dimension.

The R-SPLINE paper requires a positive sequence b_k -> infinity (§3.2)
and the R-PERLE preprint uses ceil(8 * 1.2**nu) (§9.1). `calc_b` scaled
by (dim - 1), so at dim 1 it was 0 in every iteration: SPLINE stopped
after one SPLI and one NE, and SPLI after its first gradient, before any
line-search step (docs/algorithm-audit.md, finding 9). It now scales by
max(dim - 1, 1). Above dim 2 the (dim - 1) factor is unchanged; whether
the papers mean it is left open.
"""
from math import ceil

import pytest

from pymoso.chnutils import solve
from pymoso.problems.probsimpleso import ProbSimpleSO
from pymoso.solvers.rspline import RSPLINE

SEED = (12345,) * 6


class _Dim:
    def __init__(self, dim):
        self.dim = dim


@pytest.mark.parametrize("nu", range(1, 12))
@pytest.mark.parametrize("dim, factor", [(1, 1), (2, 1), (3, 2), (9, 8)])
def test_calc_b_is_bconst_times_max_dim_minus_one_and_one(dim, factor, nu):
    solver = _Dim(dim)
    solver.bconst = 8
    assert RSPLINE.calc_b(solver, nu) == ceil(8 * factor * 1.2 ** nu)


class _CountingRSPLINE(RSPLINE):
    """Counts estimates SPLI makes outside its gradients: line-search steps."""
    steps = 0
    _in_spli = _in_pli = False

    def spli(self, *args, **kwargs):
        self._in_spli = True
        try:
            return super().spli(*args, **kwargs)
        finally:
            self._in_spli = False

    def pli(self, *args, **kwargs):
        self._in_pli = True
        try:
            return super().pli(*args, **kwargs)
        finally:
            self._in_pli = False

    def estimate(self, *args, **kwargs):
        if self._in_spli and not self._in_pli:
            type(self).steps += 1
        return super().estimate(*args, **kwargs)


def test_spli_takes_line_search_steps_in_one_dimension():
    _CountingRSPLINE.steps = 0
    solve(ProbSimpleSO, _CountingRSPLINE, (40,), budget=1000, seed=SEED, simpar=1)
    assert _CountingRSPLINE.steps > 0
