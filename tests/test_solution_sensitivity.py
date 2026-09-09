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
from pymoso.chnutils import testsolve
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
EXPECTED_SOLUTIONS = {
    0: {(31, 6), (32, 6)},
    1: {(1, 8), (17, 7)},
    2: {(7, 4), (8, 4), (9, 3)},
    3: {(26, 16), (26, 17)},
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
    assert end_seed == (3654817394, 2187457693, 4207556677, 3585739323, 608476310, 697649114)
