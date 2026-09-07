"""
Regression test: an RA solver that would exceed the reserved random-
stream window (chnutils.MAX_RI, formerly a bare local 200 in
get_testsolve_prnstreams) must raise a clear exception naming the
constant and what to change, instead of silently walking into the next
independent sample path's reserved stream (docs/phase2a-verification.md,
item 3, showed this overlap is exact and silent).

Reaching the real MAX_RI=200 threshold needs billions of simulation calls
at default settings (see docs/phase2a-verification.md), so these tests
patch chnbase.MAX_RI down to a small number to exercise the guard quickly
and deterministically.
"""
import pytest

from pymoso import chnbase
from pymoso.chnutils import solve
from pymoso.problems.probtpa import ProbTPA
from pymoso.solvers.rperle import RPERLE

SOLVE_KWARGS = dict(seed=(12345,) * 6, simpar=1, crn=False)


def test_exceeding_max_ri_raises_clear_exception(monkeypatch):
    monkeypatch.setattr(chnbase, 'MAX_RI', 3)
    with pytest.raises(RuntimeError) as exc_info:
        # budget=50000 with default mconst comfortably needs more than 3
        # RA iterations (Phase 2a: ~11 iterations at budget=1000).
        solve(ProbTPA, RPERLE, (40, 40), budget=50000, **SOLVE_KWARGS)
    msg = str(exc_info.value)
    assert 'MAX_RI=3' in msg
    assert 'chnutils' in msg


def test_staying_within_max_ri_does_not_raise(monkeypatch):
    monkeypatch.setattr(chnbase, 'MAX_RI', 1000)
    # a small budget that finishes well under 1000 RA iterations
    res, end_seed = solve(ProbTPA, RPERLE, (40, 40), budget=1000, **SOLVE_KWARGS)
    assert res is not None
