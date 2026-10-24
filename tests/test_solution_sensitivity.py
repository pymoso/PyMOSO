"""
Candidate A from the RNG-consumption-blind-spot investigation
(docs/end-seed-scope.md): golden the actual returned solution set, not
just the end seed. Confirmed sensitive to the getrandbits() change before
being added here -- with ranx0=True (get_ranx0 picks x0 via choice()),
the same seed/budget/isp under the pre-getrandbits _randbelow fallback
returned solution sets of size {0: 3, 1: 5, 2: 3, 3: 3} where this
baseline has {0: 1, 1: 2, 2: 1, 3: 3}. This scenario mirrors
tests/test_golden.py's testsolve_tpa case but with ranx0=True (the CLI
case's actual behavior: testsolve_tpa passes no <x>, so
commands/testsolve.py sets ranx0=True -- see docs/end-seed-scope.md) so
it exercises the exact path that end-seed matching cannot see.

IMPORTANT: unlike end-seed matching, these goldens are not a pure RNG
regression check. res['itersoln'] reflects the solver's actual search
path, so a legitimate change to RPERLE/RASolver's algorithm (a tie-
breaking rule, a convergence criterion, an upsample/neighbor change --
anything that affects which points get visited) can also legitimately
move these values. A failure here means "read the diff and work out
whether the RNG or the solver changed," not "restore the old tuple."
That is a real cost relative to end-seed goldens, accepted deliberately
because end-seed goldens cannot detect this class of change at all.

itersoln entries are plain Python sets, compared with == below --
Python set equality (unlike a list/tuple comparison) does not depend on
iteration order, so there is no ordering fragility to work around here.
"""
import pytest

from pymoso.chnutils import solve, testsolve
from pymoso.problems.probsimpleso import ProbSimpleSO
from pymoso.problems.probtpa import ProbTPA
from pymoso.solvers.mocompass import ExampleSearchSolver
from pymoso.solvers.mopbnb import ExampleBnBSolver
from pymoso.solvers.rminrle import RMINRLE
from pymoso.solvers.rpe import RPE
from pymoso.solvers.rspline import RSPLINE
from pymoso.testers.tpatester import TPATester
from pymoso.solvers.rperle import RPERLE

# EXPECTED_SOLUTIONS recaptured once, for docs/rng-interface-design.md
# §12's unnumbered prerequisite-fix entry (immediately before step 8):
# offset_within_iteration's replication field had stride 1, so
# replications sharing more than one raw draw per g() call (every
# built-in problem, including ProbTPA/TPATester here) were not actually
# independent -- fixed via a real per-replication reserve
# (REPL_RESERVE_BITS, pymoso/prng/base.py). This is exactly the class of
# change this golden exists to catch (its own module docstring): a
# solver search path shifting because the underlying replications
# changed, invisible to end-seed matching alone (docs/end-seed-scope.md).
# end_seed (below, in the test itself) has moved separately since then,
# for an unrelated reason -- see its own comment.
#
# Recaptured a second time for the testsolve() role-layout fix
# (KNOWN_ISSUES.md issue 10; tests/golden/README.md has the prior
# values): both defects it fixed were in where each path's oracle
# streams start, so every path's replications -- and therefore its
# search path -- changed. Again the class of change this golden exists
# to catch, and again deliberate.
#
# Recaptured a third time for the relaxation fix (docs/algorithm-audit.md
# finding 2): R-PERLE's relaxation is now the preprint's, so every
# path's search changed. A solver change, which the module docstring
# says this golden also sees; tests/golden/README.md has the prior
# values.
#
# And a fourth time for the tie-break fix (finding 7): PE breaks ties
# between objectives with a draw from the solver's stream now.
#
# And a fifth time for the SPLINE stop (finding 14): SPLINE takes one
# more pass when its calls land exactly on b. Paths 0 and 3 moved.
#
# And a sixth time for PE's LWEP filter (finding 3): epsilons are
# placed from the LWEPs among Min's output. Every path moved.
#
# And a seventh time for SPLI's return at an infeasible line-search point
# (finding 5). Path 0 moved; the end seed below did not.
#
# And an eighth time for SPLI's nearest-integer line search (finding 4).
# Every path moved.
EXPECTED_SOLUTIONS = {
    0: {(36, 2), (36, 3), (37, 5)},
    1: {(14, 6), (15, 8)},
    2: {(12, 4), (12, 5)},
    3: {(15, 12), (16, 14)},
}


def test_testsolve_ranx0_solution_sets_match_baseline():
    res, end_seed = testsolve(
        TPATester, RPERLE, (0,),
        budget=1000, seed=(12345,) * 6, isp=4, proc=1, crn=False, ranx0=True,
    )
    actual = {
        path: res[path]['itersoln'][max(res[path]['itersoln'])]
        for path in res
    }
    assert actual == EXPECTED_SOLUTIONS
    # end seed matches tests/test_golden.py's testsolve_tpa case exactly
    # -- not a coincidence, and not evidence of x0-invariance: both are
    # the identical computation (same tester/solver/budget/seed/isp/proc/
    # crn, both ranx0=True, so the (0,) passed as x0 here is discarded
    # the same way testsolve_tpa's own missing <x> is -- see
    # docs/end-seed-scope.md, corrected as of docs/rng-interface-
    # design.md §12 step 8: ranx0 CAN now affect end_seed post-stage-2,
    # since it can change which x0 the solver actually searches from,
    # which can change the run's own oracle-role high-water mark. This
    # value moved from the prior baseline for that reason, not from
    # EXPECTED_SOLUTIONS's own defect fix above (a separate, unrelated
    # regeneration).
    #
    # Still true after the testsolve() role-layout fix moved both: this
    # value and testsolve_tpa's moved to the same new value, which is
    # what a uniform change to the layout should do to two runs of the
    # same computation.
    #
    # And after the relaxation fix and the tie-break fix, which moved
    # both again, together, and after the SPLINE stop fix and the
    # LWEP filter fix. Not after the SPLI fix (finding 5), which moved
    # path 0's solution. And after the nearest-integer line search.
    assert end_seed == (4244682198, 3625174356, 12273143, 1664344229, 2348137384, 1201660776)


# ---------------------------------------------------------------------------
# The solution set of every other case in tests/test_golden.py. The end
# seeds there missed every solution finding 5's fix moved (five, in four
# cases) and rperle_tpa's three times before that (docs/end-seed-scope.md,
# the seventh instance). Each call here is its golden case's computation
# through the library; every end seed was checked against the case's
# golden when these were captured (twice on each of .venv-baseline and
# .venv-dev, identical). The same caveat as the module docstring's: a
# solver change can move these legitimately. rperle_tpa stands for the
# solve() library call too, which is the same call.
# ---------------------------------------------------------------------------
EXAMPLE = dict(lb=0, ub=50)

SOLVE_CASES = {
    "rperle_tpa": (ProbTPA, RPERLE, (40, 40), {}, {(23, 38)}),
    "rminrle_tpa": (ProbTPA, RMINRLE, (40, 40), {},
                    {(34, 40), (34, 41), (35, 41), (36, 41)}),
    "rpe_tpa": (ProbTPA, RPE, (40, 40), {}, {(23, 38)}),
    "rspline_simpleso": (ProbSimpleSO, RSPLINE, (40,), {}, {(0,)}),
    "rperle_tpa_crn": (ProbTPA, RPERLE, (40, 40), {"crn": True},
                       {(0, 6), (0, 7), (0, 8), (10, 8), (21, 8)}),
    "rperle_tpa_seed2": (ProbTPA, RPERLE, (40, 40), {"seed": (1, 2, 3, 4, 5, 6)},
                         {(6, 7), (7, 8), (8, 7)}),
    "rperle_tpa_simpar2": (ProbTPA, RPERLE, (40, 40), {"simpar": 2}, {(23, 38)}),
    "example_search_tpa": (ProbTPA, ExampleSearchSolver, (40, 40), EXAMPLE,
                           {(0, 1), (0, 3)}),
    "example_bnb_tpa": (ProbTPA, ExampleBnBSolver, (40, 40), EXAMPLE,
                        {(2, 9), (4, 12), (12, 29), (14, 7), (22, 11), (31, 9)}),
}

TESTSOLVE_CASES = {
    # the testsolve() library call: x0 given, ranx0=False
    "testsolve_library": (RPERLE, (40, 40), False, {}, {
        0: {(27, 33)},
        1: {(30, 36), (32, 37)},
        2: {(30, 38), (31, 38), (31, 39)},
        3: {(7, 25), (7, 26)},
    }),
    "testsolve_example_search": (ExampleSearchSolver, (0,), True, EXAMPLE, {
        0: {(5, 11), (9, 9)},
        1: {(23, 8), (23, 10), (26, 6)},
        2: {(4, 9)},
        3: {(4, 6), (4, 10)},
    }),
    "testsolve_example_bnb": (ExampleBnBSolver, (0,), True, EXAMPLE, {
        0: {(8, 5), (12, 15)},
        1: {(5, 20), (6, 26), (14, 18), (16, 18), (27, 13)},
        2: {(8, 18), (17, 0), (18, 2)},
        3: {(1, 0), (2, 16), (10, 25)},
    }),
}


@pytest.mark.parametrize("name", sorted(SOLVE_CASES))
def test_solve_solution_set_matches_baseline(name):
    problem, solver, x0, kwargs, expected = SOLVE_CASES[name]
    args = dict(budget=1000, seed=(12345,) * 6, simpar=1, crn=False)
    args.update(kwargs)
    res, _ = solve(problem, solver, x0, **args)
    assert res == expected


@pytest.mark.parametrize("name", sorted(TESTSOLVE_CASES))
def test_testsolve_solution_sets_match_baseline(name):
    solver, x0, ranx0, kwargs, expected = TESTSOLVE_CASES[name]
    res, _ = testsolve(
        TPATester, solver, x0,
        budget=1000, seed=(12345,) * 6, isp=4, proc=1, crn=False, ranx0=ranx0, **kwargs,
    )
    actual = {
        path: res[path]['itersoln'][max(res[path]['itersoln'])]
        for path in res
    }
    assert actual == expected
