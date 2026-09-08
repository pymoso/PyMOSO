"""
Fixture tests for problems.probexpensive: the tunable-cost oracle built
to exercise --simpar/--proc in the regime the README recommends parallel
replication for ("the simulation takes a half second or more to generate
a single observation") -- a regime nothing else in this suite reaches,
since every other test problem is cheap enough that dispatch overhead
dominates its runtime.

Two properties matter here and nowhere else in the suite:

1. g()'s return value is identical regardless of burn_units -- the CPU
   burn must never leak into the objective value. Verified directly
   below, not just claimed in the module docstring.
2. The parallel paths (--simpar via solve(), --proc via testsolve())
   actually complete and match serial output against a non-trivial-cost
   oracle. tests/test_parallel_dispatch.py does the exhaustive worker-
   count sweep and job-count instrumentation; this file just proves the
   fixture itself works.

No wall-clock assertions here -- see docs/parallel-dispatch-baseline.md
for actual timings, captured outside the test suite.
"""
import pytest

from pymoso.chnutils import edist, solve, testsolve
from pymoso.problems.probexpensive import ProbExpensive, ProbExpensiveLight, ProbExpensiveModerate
from pymoso.prng.mrg32k3a import MRG32k3a
from pymoso.solvers.rspline import RSPLINE
from pymoso.testers.expensivetester import ExpensiveTester

pytestmark = pytest.mark.timeout(60)

SEED = (12345,) * 6

# (x, seed) pairs to check determinism across cost tiers on. Includes an
# infeasible point (x=(500,), outside [-100, 100]) since isfeas must also
# be unaffected by burn_units.
DETERMINISM_CASES = [
    ((5,), (1, 2, 3, 4, 5, 6)),
    ((-37,), (11, 22, 33, 44, 55, 66)),
    ((0,), SEED),
    ((500,), SEED),
]


@pytest.mark.parametrize("x,seed", DETERMINISM_CASES, ids=[str(c[0]) for c in DETERMINISM_CASES])
def test_g_output_identical_across_cost_tiers(x, seed):
    rng_light = MRG32k3a(seed)
    rng_moderate = MRG32k3a(seed)
    result_light = ProbExpensiveLight(rng_light).g(x, rng_light)
    result_moderate = ProbExpensiveModerate(rng_moderate).g(x, rng_moderate)
    assert result_light == result_moderate
    # burning CPU must not consume the rng either -- both streams should
    # have advanced identically regardless of burn_units.
    assert rng_light.get_seed() == rng_moderate.get_seed()


def test_uncosted_base_class_also_matches():
    # burn_units=0 is a degenerate case of the same g(): confirms the
    # burn is additive, not a different code path.
    rng_base = MRG32k3a(SEED)
    rng_light = MRG32k3a(SEED)
    assert ProbExpensive(rng_base).g((5,), rng_base) == ProbExpensiveLight(rng_light).g((5,), rng_light)


def test_true_solution_is_recovered():
    # Light tier so a budget generous enough to actually demonstrate
    # convergence (not just "ran without error") stays cheap. This is a
    # fixture-correctness check (true_g/soln/metric are wired to the
    # right problem), not a solver-convergence regression test -- hence
    # the loose bound rather than an exact golden.
    soln, _ = solve(ProbExpensiveLight, RSPLINE, (50,), budget=1000, seed=SEED)
    x = next(iter(soln))[0]
    assert abs(x) <= 20, f"RSPLINE should have moved from x0=50 towards the true minimizer x=0, landed at {x}"
    assert ExpensiveTester().metric({(x,)}) == edist((x,), (0,))


def test_solve_with_simpar_completes_and_matches_serial():
    kwargs = dict(budget=100, seed=SEED, crn=False)
    serial_soln, serial_endseed = solve(ProbExpensiveModerate, RSPLINE, (50,), simpar=1, **kwargs)
    parallel_soln, parallel_endseed = solve(ProbExpensiveModerate, RSPLINE, (50,), simpar=4, **kwargs)
    assert parallel_soln == serial_soln
    assert parallel_endseed == serial_endseed


def test_testsolve_with_proc_completes_and_matches_serial():
    kwargs = dict(budget=100, seed=SEED, isp=2, crn=False)
    serial_res, serial_endseed = testsolve(ExpensiveTester, RSPLINE, (50,), proc=1, **kwargs)
    parallel_res, parallel_endseed = testsolve(ExpensiveTester, RSPLINE, (50,), proc=2, **kwargs)
    assert parallel_res == serial_res
    assert parallel_endseed == serial_endseed
