"""
Regression tests for the error-handling fix: library code must raise real,
chained exceptions instead of calling sys.exit(), and a bare except: must
not re-swallow the exception one level up (chnbase.py's former
estimate()/RLESolver.spsolve bare excepts).

Adapted for the pymoso/master base (post-917bf06): chnutils.solve/testsolve
no longer default budget/seed/simpar/crn (see the phase-7 kwarg-defaults
fix, not yet applied when this file was written), so every call here
supplies them explicitly. MRG32k3a's cache switch is now an instance
method (post-dfd2a30), not a classmethod -- calls updated accordingly.
"""
import pytest

from pymoso.chnbase import Oracle
from pymoso.chnutils import solve
from pymoso.prng.mrg32k3a import MRG32k3a
from pymoso.solvers.rspline import RSPLINE
from pymoso.solvers.rperle import RPERLE

SOLVE_KWARGS = dict(budget=100, seed=(12345,) * 6, simpar=1, crn=False)


class BrokenOracle(Oracle):
    """An oracle whose g() has the wrong signature -- exactly the kind of
    user mistake estimate()'s except TypeError clause exists to explain."""
    num_obj = 1
    dim = 1

    def g(self, x):
        return True, (x[0],)


def test_broken_oracle_raises_real_exception_not_generic_message():
    """A hard TypeError deep in Oracle.hit() must surface as a real,
    catchable exception with the original TypeError attached as its
    cause -- not a printed 'Unable to simulate' followed by sys.exit()."""
    with pytest.raises(RuntimeError) as exc_info:
        solve(BrokenOracle, RSPLINE, (1,), **SOLVE_KWARGS)
    assert 'Unable to simulate' in str(exc_info.value)
    assert isinstance(exc_info.value.__cause__, TypeError)


def test_broken_oracle_raises_through_rlesolver_too():
    """The same must hold for an RLESolver (RPERLE), whose spsolve() has
    its own try/except around accel() -- this is the exact call site
    where a SystemExit used to be re-caught by a bare except: and
    reported as a second, unrelated 'Unable to run accel()' message.
    Now both layers wrap-and-chain (via `raise ... from e`) instead of
    printing and exiting, so the original TypeError is still findable by
    walking __cause__, and nothing is silently discarded."""

    class BrokenOracle2(Oracle):
        num_obj = 2
        dim = 2

        def g(self, x):
            return True, (x[0], x[1])

    with pytest.raises(RuntimeError) as exc_info:
        solve(BrokenOracle2, RPERLE, (1, 1), **SOLVE_KWARGS)
    assert 'Unable to run accel()' in str(exc_info.value)
    cause = exc_info.value.__cause__
    seen_types = []
    while cause is not None:
        seen_types.append(type(cause))
        cause = cause.__cause__
    assert TypeError in seen_types, seen_types


def test_missing_sprn_or_x0_raises_typeerror():
    rng = MRG32k3a((12345,) * 6)

    class TinyOracle(Oracle):
        num_obj = 1
        dim = 1

        def g(self, x, rng):
            return True, (x[0],)

    orc = TinyOracle(rng)
    with pytest.raises(TypeError):
        RSPLINE(orc)


def test_bump_m_less_than_one_raises_valueerror():
    rng = MRG32k3a((12345,) * 6)
    rng.set_class_cache(False)

    class TinyOracle(Oracle):
        num_obj = 1
        dim = 1

        def g(self, x, rng):
            return True, (x[0],)

    orc = TinyOracle(rng)
    with pytest.raises(ValueError):
        orc.bump((1,), 0)


def test_hit_m_less_than_one_raises_assertionerror():
    """FINDING, not part of our fix: upstream's own 917bf06 rewrite
    replaced hit()'s sys.exit() on m<1 with `assert(m >= 1)` -- a real
    raise, unlike the old sys.exit(), but AssertionError rather than the
    ValueError bump()'s equivalent check raises (ours, and unchanged from
    our fork). The two checks now disagree on exception type for the
    same precondition on sibling methods of the same class. Noting the
    inconsistency here rather than silently reconciling it -- see the
    migration report."""
    rng = MRG32k3a((12345,) * 6)
    rng.set_class_cache(False)

    class TinyOracle(Oracle):
        num_obj = 1
        dim = 1

        def g(self, x, rng):
            return True, (x[0],)

    orc = TinyOracle(rng)
    with pytest.raises(AssertionError):
        orc.hit((1,), 0)
