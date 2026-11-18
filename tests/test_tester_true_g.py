"""
A tester's true_g must be its problem's expected value, objective by
objective, in the same order g() returns them.

ProbTPB's g() returned (front term, linear term) since the first
commit, while TPBTester.true_g and soln -- and the paper -- have
objective 1 the linear term. The tester's metric could not see it:
dominance does not depend on the order of the objectives and swapping
two coordinates preserves Euclidean distance, so every T_B metric value
was the same either way (checked bit for bit on 7,941 solution sets).
What did depend on it: every solver's run (the solvers are not
order-symmetric), and anything reading one objective by index, such as
R-SPLINE (which minimizes objective 1) and the bench scripts' R-SPLINE
quality.

So the check here is direct: sample means of g() against true_g at
points where the objectives differ. Deterministic seed, so not flaky;
the tolerance is 5 standard errors. With the old ProbTPB the worst point
was more than 10 standard errors out.
"""
import math

import pytest

from pymoso.prng.mrg32k3a import MRG32k3a
from pymoso.problems.probtpa import ProbTPA
from pymoso.problems.probtpb import ProbTPB
from pymoso.problems.probtpc import ProbTPC
from pymoso.testers import tpatester, tpbtester, tpctester

SEED = (12345,) * 6
N = 20000

CASES = [
    (ProbTPA, tpatester.true_g, [(10, 20), (40, 5), (0, 50)]),
    (ProbTPB, tpbtester.true_g, [(10, 20), (20, 20), (5, 70), (30, 70), (60, 5)]),
    (ProbTPC, tpctester.true_g, [(-3, 0, -3), (5, -2, 7), (-10, 10, 0)]),
]


@pytest.mark.parametrize("problem, true_g, points", CASES, ids=['TPA', 'TPB', 'TPC'])
def test_true_g_is_the_mean_of_g_in_the_same_order(problem, true_g, points):
    rng = MRG32k3a(SEED)
    orc = problem(rng)
    for x in points:
        expected = true_g(x)
        s = [0.0] * len(expected)
        ss = [0.0] * len(expected)
        for _ in range(N):
            isfeas, obj = orc.g(x, rng)
            assert isfeas
            for k, v in enumerate(obj):
                s[k] += v
                ss[k] += v * v
        for k in range(len(expected)):
            mean = s[k] / N
            se = math.sqrt(max(ss[k] / N - mean * mean, 0.0) / N)
            assert abs(mean - expected[k]) <= 5 * se + 1e-12, (
                f"{problem.__name__} at {x}, objective {k + 1}: mean of g() {mean:.4f} "
                f"(SE {se:.4f}), true_g {expected[k]:.4f}; true_g gives {expected}")
