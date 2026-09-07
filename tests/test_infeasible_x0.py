"""
Regression tests: an infeasible x0 must produce the same clear "Is x0
feasible?" ValueError for all four built-in solvers, raised from a
direct feasibility check at the point of failure (RASolver.get_min /
RSPLINE.spsolve) -- not guessed from an incidental exception type.
docs/phase2a-verification.md (item 4) showed the old `except ValueError`
in rperle.py/rpe.py was unreachable dead code: the real failure was an
unhandled KeyError (RPE) or one masked behind a generic "Unable to run
accel()" message (RPERLE, RMINRLE).
"""
import pytest

from pymoso.chnutils import solve
from pymoso.problems.probtpa import ProbTPA
from pymoso.problems.probsimpleso import ProbSimpleSO
from pymoso.solvers.rperle import RPERLE
from pymoso.solvers.rpe import RPE
from pymoso.solvers.rminrle import RMINRLE
from pymoso.solvers.rspline import RSPLINE

INFEASIBLE_TPA_X0 = (-100, -100)  # ProbTPA is feasible on [0, 50]^2
INFEASIBLE_SIMPLESO_X0 = (-1000,)  # ProbSimpleSO is feasible on [-100, 100]

SOLVE_KWARGS = dict(budget=500, seed=(12345,) * 6, simpar=1, crn=False)

BIOBJECTIVE_CASES = [
    ("RPERLE", RPERLE),
    ("RPE", RPE),
    ("RMINRLE", RMINRLE),
]


@pytest.mark.parametrize("name,solver", BIOBJECTIVE_CASES, ids=[c[0] for c in BIOBJECTIVE_CASES])
def test_infeasible_x0_raises_clear_valueerror(name, solver):
    with pytest.raises(ValueError) as exc_info:
        solve(ProbTPA, solver, INFEASIBLE_TPA_X0, **SOLVE_KWARGS)
    msg = str(exc_info.value)
    assert 'infeasible' in msg
    assert str(INFEASIBLE_TPA_X0) in msg


def test_infeasible_x0_raises_clear_valueerror_rspline():
    with pytest.raises(ValueError) as exc_info:
        solve(ProbSimpleSO, RSPLINE, INFEASIBLE_SIMPLESO_X0, **SOLVE_KWARGS)
    msg = str(exc_info.value)
    assert 'infeasible' in msg
    assert str(INFEASIBLE_SIMPLESO_X0) in msg


def test_all_biobjective_solvers_give_the_same_message():
    messages = set()
    for _, solver in BIOBJECTIVE_CASES:
        with pytest.raises(ValueError) as exc_info:
            solve(ProbTPA, solver, INFEASIBLE_TPA_X0, **SOLVE_KWARGS)
        messages.add(str(exc_info.value))
    assert len(messages) == 1, messages
