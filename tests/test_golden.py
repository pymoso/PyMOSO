import re
import subprocess

import pytest

from _pymoso_cli import CLI_TIMEOUT, pymoso_argv
from pymoso.chnutils import solve, testsolve
from pymoso.problems.probtpa import ProbTPA
from pymoso.solvers.rperle import RPERLE
from pymoso.testers.tpatester import TPATester

# Recaptured against the exact-integer jump-ahead fix (see
# KNOWN_ISSUES.md issue 1), then again for every crnflag=False case,
# a third time for a replication-independence fix, a fourth time for
# Oracle.get_endseed() being wired into RASolver.solve/rasolve, and a
# fifth time -- this capture -- for testsolve()'s own endseed becoming
# the real aggregated high-water mark across every isp path
# (chnutils.testsolve, after par_runs() returns each path's own
# oracle_high_water_mark), replacing get_testsolve_prnstreams's
# reservation value. Only testsolve_tpa and the testsolve() library
# case moved this time -- solve()'s own cases (already on the real
# formula since the fourth capture) are untouched. All five sets of
# prior values are preserved in tests/golden/README.md for historical
# reference -- none are restorable defaults; each prior mechanism (the
# jump-ahead bug, the pre-fix order-dependence defect, the
# replication-collision defect, and call-count-only endseed reporting,
# at both the solve() and testsolve() layers) was wrong in its own way.
# These values are now a fully settled baseline.
#
# Excluded from this release (branched at the RNG-redesign's own
# 6c-completion point): MOCOMPASS/MOPBnB, real MOSOSolvers whose
# algorithmic correctness against their source papers has not been
# reviewed -- shipping them is a deliberate 2.0.0 decision, not a side
# effect of where this release's version line falls. Their own golden
# cases (mocompass_tpa/mopbnb_tpa/testsolve_mocompass/testsolve_mopbnb)
# are removed from CASES below; the values remain in tests/golden/
# README.md's own historical record. docs/rng-interface-design.md
# itself (design rationale for the RNG redesign these values reflect)
# ships as development documentation regardless.

SEED_RE = re.compile(r"^--\s+(?:next|ending) seed:\s+(.+)$", re.M)

CASES = {
    "rperle_tpa": (
        ["pymoso", "solve", "--budget=1000", "ProbTPA", "RPERLE", "40", "40"],
        (900181699, 3252648471, 384599192, 813079481, 747618736, 882165191),
    ),
    "rminrle_tpa": (
        ["pymoso", "solve", "--budget=1000", "ProbTPA", "RMINRLE", "40", "40"],
        (3101702307, 2274224287, 2252695779, 2887425027, 4188880773, 159891216),
    ),
    # rpe_tpa coincides with rperle_tpa again -- not an error, checked
    # directly: a crnflag=False end seed depends only on (Oracle.
    # _iteration, m) at the last hit() call (§12 step 8's own high-water
    # mark, oracle-role only), and calc_m(nu) is the same function of nu
    # for every RASolver-family solver; both solvers ended this run at
    # the same nu (13), so both land on the same coordinate.
    "rpe_tpa": (
        ["pymoso", "solve", "--budget=1000", "ProbTPA", "RPE", "40", "40"],
        (900181699, 3252648471, 384599192, 813079481, 747618736, 882165191),
    ),
    "rspline_simpleso": (
        ["pymoso", "solve", "--budget=1000", "ProbSimpleSO", "RSPLINE", "40"],
        (2327071160, 589288757, 3791179983, 1866895284, 2094692759, 3256882931),
    ),
    # testsolve_tpa's own value moved because it now reflects the real
    # aggregated oracle-role high-water mark across every isp path, not
    # a reservation-based value.
    "testsolve_tpa": (
        ["pymoso", "testsolve", "--budget=1000", "--isp=4", "--metric",
         "TPATester", "RPERLE"],
        (3654817394, 2187457693, 4207556677, 3585739323, 608476310, 697649114),
    ),
    # rperle_tpa_crn moved too, contrary to this golden's own long-
    # standing expectation of staying fixed while the crnflag=False
    # cases moved around it -- a real finding, not absorbed silently:
    # see docs/rng-interface-design.md §8.2's "Wired in as of step 8
    # stage 1" note for the full trace (rasolve()'s own trailing,
    # unconditional crn_advance() call past the last iteration that
    # actually ran). The new value is a correct tightening, not a
    # regression -- confirmed nothing beyond it was ever touched.
    "rperle_tpa_crn": (
        ["pymoso", "solve", "--budget=1000", "--crn", "ProbTPA", "RPERLE", "40", "40"],
        (1128359308, 3860538173, 798726527, 4016157990, 1667726745, 709835043),
    ),
    "rperle_tpa_seed2": (
        ["pymoso", "solve", "--budget=1000", "--seed", "1", "2", "3", "4", "5", "6",
         "ProbTPA", "RPERLE", "40", "40"],
        (2175629958, 147802191, 2425104019, 853609596, 4132240727, 4089413332),
    ),
    "rperle_tpa_simpar2": (
        ["pymoso", "solve", "--budget=1000", "--simpar=2", "ProbTPA", "RPERLE", "40", "40"],
        (900181699, 3252648471, 384599192, 813079481, 747618736, 882165191),
    ),
}


def end_seed(cmd, cwd):
    proc = subprocess.run(pymoso_argv(cmd), cwd=cwd, capture_output=True, text=True,
                          timeout=CLI_TIMEOUT)
    assert proc.returncode == 0, proc.stderr
    match = SEED_RE.search(proc.stdout)
    assert match, f"no seed line found in:\n{proc.stdout}"
    return tuple(int(v) for v in match.group(1).split())


@pytest.mark.parametrize("name", sorted(CASES))
def test_end_seed_matches_baseline(name, tmp_path):
    cmd, expected = CASES[name]
    assert end_seed(cmd, tmp_path) == expected


# ---------------------------------------------------------------------------
# Library-level calls: never exercised by any test before this migration
# (only the CLI path, which always passes every kwarg explicitly, has ever
# been under regression coverage). Same problem/solver/budget/seed as
# rperle_tpa/testsolve_tpa above -- confirmed to produce identical end
# seeds to their CLI counterparts, as expected since the CLI is a thin
# wrapper over these same functions.
# ---------------------------------------------------------------------------

def test_library_solve_end_seed_matches_baseline():
    res, end_seed = solve(
        ProbTPA, RPERLE, (40, 40),
        budget=1000, seed=(12345,) * 6, simpar=1, crn=False,
    )
    assert end_seed == (900181699, 3252648471, 384599192, 813079481, 747618736, 882165191)


def test_library_testsolve_end_seed_matches_baseline():
    res, end_seed = testsolve(
        TPATester, RPERLE, (40, 40),
        budget=1000, seed=(12345,) * 6, isp=4, proc=1, crn=False, ranx0=False,
    )
    assert end_seed == (1744404958, 3393812160, 2418775421, 509218500, 1460079748, 3249260099)
