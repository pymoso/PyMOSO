import re
import subprocess

import pytest

from pymoso.chnutils import solve, testsolve
from pymoso.problems.probtpa import ProbTPA
from pymoso.solvers.rperle import RPERLE
from pymoso.testers.tpatester import TPATester

# Recaptured against the exact-integer jump-ahead fix (see
# KNOWN_ISSUES.md issue 1 and the "Fix MRG32k3a jump-ahead precision
# loss" commit). The pre-fix values these replaced are preserved in
# tests/golden/README.md for historical reference -- they are not
# restorable defaults, the old jump-ahead was wrong.

SEED_RE = re.compile(r"^--\s+(?:next|ending) seed:\s+(.+)$", re.M)

CASES = {
    "rperle_tpa": (
        ["pymoso", "solve", "--budget=1000", "ProbTPA", "RPERLE", "40", "40"],
        (4226535370, 3918856659, 447968167, 400221883, 592996512, 2795685938),
    ),
    "rminrle_tpa": (
        ["pymoso", "solve", "--budget=1000", "ProbTPA", "RMINRLE", "40", "40"],
        (33132303, 325849388, 376624132, 1563924626, 293517807, 795864341),
    ),
    "rpe_tpa": (
        ["pymoso", "solve", "--budget=1000", "ProbTPA", "RPE", "40", "40"],
        (3464732221, 1507014170, 850131796, 3585675128, 2782941437, 844928957),
    ),
    "rspline_simpleso": (
        ["pymoso", "solve", "--budget=1000", "ProbSimpleSO", "RSPLINE", "40"],
        (3294576687, 175234757, 49170740, 679432683, 2711532206, 2761197391),
    ),
    "testsolve_tpa": (
        ["pymoso", "testsolve", "--budget=1000", "--isp=4", "--metric",
         "TPATester", "RPERLE"],
        (1879114232, 1005083882, 2442288136, 348713332, 254370183, 2727774063),
    ),
    "rperle_tpa_crn": (
        ["pymoso", "solve", "--budget=1000", "--crn", "ProbTPA", "RPERLE", "40", "40"],
        (3777646647, 1837464056, 4204654757, 664239048, 4190510072, 2959195122),
    ),
    "rperle_tpa_seed2": (
        ["pymoso", "solve", "--budget=1000", "--seed", "1", "2", "3", "4", "5", "6",
         "ProbTPA", "RPERLE", "40", "40"],
        (4131271395, 3226219906, 777515709, 589263233, 2312345461, 1567227549),
    ),
    "rperle_tpa_simpar2": (
        ["pymoso", "solve", "--budget=1000", "--simpar=2", "ProbTPA", "RPERLE", "40", "40"],
        (4226535370, 3918856659, 447968167, 400221883, 592996512, 2795685938),
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
    assert end_seed == (4226535370, 3918856659, 447968167, 400221883, 592996512, 2795685938)


def test_library_testsolve_end_seed_matches_baseline():
    res, end_seed = testsolve(
        TPATester, RPERLE, (40, 40),
        budget=1000, seed=(12345,) * 6, isp=4, proc=1, crn=False, ranx0=False,
    )
    assert end_seed == (1879114232, 1005083882, 2442288136, 348713332, 254370183, 2727774063)
