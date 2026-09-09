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

EXPECTED_SOLUTIONS = {
    0: {(38, 0), (41, 4)},
    1: {(16, 6), (16, 7)},
    2: {(5, 6), (6, 4)},
    3: {(18, 19)},
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
    # end seed is identical to the ranx0=False testsolve_tpa golden and
    # unaffected by which x0 was picked -- see docs/end-seed-scope.md.
    assert end_seed == (756192979, 932320642, 4060792417, 2566056172, 2930731408, 2805199130)
