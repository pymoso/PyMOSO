import re
import subprocess

import pytest

from pymoso.chnutils import solve, testsolve
from pymoso.problems.probtpa import ProbTPA
from pymoso.solvers.rperle import RPERLE
from pymoso.testers.tpatester import TPATester

# Captured from github.com/pymoso/PyMOSO's master (commit a8242f2 on this
# migration branch), from the source tree directly -- not a PyPI wheel;
# see tests/golden/README.md for why. This is the PRE jump-ahead-fix
# baseline for this base: the float64 mat333mult/mat311mod precision loss
# (KNOWN_ISSUES.md issue 1) is still present here. A later commit in this
# migration applies the fix and recaptures these values separately.

SEED_RE = re.compile(r"^--\s+(?:next|ending) seed:\s+(.+)$", re.M)

CASES = {
    "rperle_tpa": (
        ["pymoso", "solve", "--budget=1000", "ProbTPA", "RPERLE", "40", "40"],
        (738848768, 2094673920, 3003824128, 304680960, 1844190720, 1414365184),
    ),
    "rminrle_tpa": (
        ["pymoso", "solve", "--budget=1000", "ProbTPA", "RMINRLE", "40", "40"],
        (351780864, 2663153664, 3654082560, 106530816, 1144764416, 1616205824),
    ),
    "rpe_tpa": (
        ["pymoso", "solve", "--budget=1000", "ProbTPA", "RPE", "40", "40"],
        (3303566336, 4006175744, 3614092288, 1314799616, 1181410816, 4085780480),
    ),
    "rspline_simpleso": (
        ["pymoso", "solve", "--budget=1000", "ProbSimpleSO", "RSPLINE", "40"],
        (703488000, 1321244672, 1775603712, 3804634112, 1506610176, 4268795904),
    ),
    "testsolve_tpa": (
        ["pymoso", "testsolve", "--budget=1000", "--isp=4", "--metric",
         "TPATester", "RPERLE"],
        (4147335168, 2708353024, 1540286464, 2835288064, 3722176512, 2227803136),
    ),
    "rperle_tpa_crn": (
        ["pymoso", "solve", "--budget=1000", "--crn", "ProbTPA", "RPERLE", "40", "40"],
        (3661742080, 1011607552, 2254225408, 2663375872, 466939904, 3186325504),
    ),
    "rperle_tpa_seed2": (
        ["pymoso", "solve", "--budget=1000", "--seed", "1", "2", "3", "4", "5", "6",
         "ProbTPA", "RPERLE", "40", "40"],
        (1248518144, 988284928, 1514053632, 1982265344, 806676480, 2743545856),
    ),
    "rperle_tpa_simpar2": (
        ["pymoso", "solve", "--budget=1000", "--simpar=2", "ProbTPA", "RPERLE", "40", "40"],
        (738848768, 2094673920, 3003824128, 304680960, 1844190720, 1414365184),
    ),
}


def end_seed(cmd, cwd):
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
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
    assert end_seed == (738848768, 2094673920, 3003824128, 304680960, 1844190720, 1414365184)


def test_library_testsolve_end_seed_matches_baseline():
    res, end_seed = testsolve(
        TPATester, RPERLE, (40, 40),
        budget=1000, seed=(12345,) * 6, isp=4, proc=1, crn=False, ranx0=False,
    )
    assert end_seed == (4147335168, 2708353024, 1540286464, 2835288064, 3722176512, 2227803136)
