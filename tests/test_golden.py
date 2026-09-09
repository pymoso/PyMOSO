import re
import subprocess

import pytest

from pymoso.chnutils import solve, testsolve
from pymoso.problems.probtpa import ProbTPA
from pymoso.solvers.rperle import RPERLE
from pymoso.testers.tpatester import TPATester

# Recaptured against the exact-integer jump-ahead fix (see
# KNOWN_ISSUES.md issue 1 and the "Fix MRG32k3a jump-ahead precision
# loss" commit), then recaptured again for every crnflag=False case
# (docs/rng-interface-design.md §12 step 4b: MAX_RI's reservation walk
# removed, the non-CRN default cutover to offset_within_iteration/
# point_code), then recaptured a third time for the cases whose `nu`
# (RA iteration count at budget exhaustion) actually changed once the
# replication-independence fix landed (§12's unnumbered prerequisite
# entry immediately before step 8: offset_within_iteration's
# replication field went from stride-1, colliding whenever g() drew
# more than one raw value, to a real reserved block) -- rperle_tpa,
# rminrle_tpa, rperle_tpa_seed2, rperle_tpa_simpar2 moved on this third
# pass; rpe_tpa/rspline_simpleso/testsolve_*/mocompass_tpa/mopbnb_tpa
# did not, because their own `nu` at budget=1000 happened to be
# unaffected -- checked directly (nu before/after), not assumed, since
# a crnflag=False end seed here is purely a function of `nu`, not of
# what hit() actually drew (the exact scoping gap step 8 exists to
# fix). rperle_tpa_crn is unchanged by any of the three passes,
# deliberately: the CRN branch is untouched by both step 4b and this
# fix. All three sets of prior values are preserved in
# tests/golden/README.md for historical reference -- none are
# restorable defaults; the jump-ahead bug, the pre-4b order-dependence
# defect, and this replication-collision defect were all wrong. Per
# tests/golden/README.md's own note: every crnflag=False value below is
# itself an intermediate state, not a settled baseline -- it will move
# again once docs/rng-interface-design.md §8.2's real endseed formula
# (a tracked high-water mark of actual coordinate consumption) is wired
# into chnutils.py/RASolver.rasolve, a change not yet scheduled to a
# step.

SEED_RE = re.compile(r"^--\s+(?:next|ending) seed:\s+(.+)$", re.M)

CASES = {
    "rperle_tpa": (
        ["pymoso", "solve", "--budget=1000", "ProbTPA", "RPERLE", "40", "40"],
        (596094074, 2279636413, 3050913596, 1739649456, 2368706608, 3058697049),
    ),
    "rminrle_tpa": (
        ["pymoso", "solve", "--budget=1000", "ProbTPA", "RMINRLE", "40", "40"],
        (3224044943, 1227141655, 2220611050, 1504589054, 2829780440, 108189859),
    ),
    # rpe_tpa is unaffected by the replication-independence fix (its own
    # nu@budget=1000 happened to be unchanged, confirmed empirically --
    # see the design doc's step-8-prerequisite entry) -- not moved here.
    "rpe_tpa": (
        ["pymoso", "solve", "--budget=1000", "ProbTPA", "RPE", "40", "40"],
        (596094074, 2279636413, 3050913596, 1739649456, 2368706608, 3058697049),
    ),
    "rspline_simpleso": (
        ["pymoso", "solve", "--budget=1000", "ProbSimpleSO", "RSPLINE", "40"],
        (3728532268, 988545039, 1631700325, 1143954198, 2209269908, 1591407377),
    ),
    "testsolve_tpa": (
        ["pymoso", "testsolve", "--budget=1000", "--isp=4", "--metric",
         "TPATester", "RPERLE"],
        (756192979, 932320642, 4060792417, 2566056172, 2930731408, 2805199130),
    ),
    "rperle_tpa_crn": (
        ["pymoso", "solve", "--budget=1000", "--crn", "ProbTPA", "RPERLE", "40", "40"],
        (3777646647, 1837464056, 4204654757, 664239048, 4190510072, 2959195122),
    ),
    "rperle_tpa_seed2": (
        ["pymoso", "solve", "--budget=1000", "--seed", "1", "2", "3", "4", "5", "6",
         "ProbTPA", "RPERLE", "40", "40"],
        (377212572, 86764798, 2286711681, 1003464262, 2322852652, 1042342679),
    ),
    "rperle_tpa_simpar2": (
        ["pymoso", "solve", "--budget=1000", "--simpar=2", "ProbTPA", "RPERLE", "40", "40"],
        (596094074, 2279636413, 3050913596, 1739649456, 2368706608, 3058697049),
    ),
    "mocompass_tpa": (
        ["pymoso", "solve", "--budget=1000", "--param", "lb", "0", "--param", "ub", "50",
         "ProbTPA", "MOCOMPASS", "40", "40"],
        (1015873554, 1310354410, 2249465273, 994084013, 2912484720, 3876682925),
    ),
    "mopbnb_tpa": (
        ["pymoso", "solve", "--budget=1000", "--param", "lb", "0", "--param", "ub", "50",
         "ProbTPA", "MOPBnB", "40", "40"],
        (1015873554, 1310354410, 2249465273, 994084013, 2912484720, 3876682925),
    ),
    "testsolve_mocompass": (
        ["pymoso", "testsolve", "--budget=1000", "--isp=4", "--param", "lb", "0",
         "--param", "ub", "50", "TPATester", "MOCOMPASS"],
        (756192979, 932320642, 4060792417, 2566056172, 2930731408, 2805199130),
    ),
    "testsolve_mopbnb": (
        ["pymoso", "testsolve", "--budget=1000", "--isp=4", "--param", "lb", "0",
         "--param", "ub", "50", "TPATester", "MOPBnB"],
        (756192979, 932320642, 4060792417, 2566056172, 2930731408, 2805199130),
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
    assert end_seed == (596094074, 2279636413, 3050913596, 1739649456, 2368706608, 3058697049)


def test_library_testsolve_end_seed_matches_baseline():
    res, end_seed = testsolve(
        TPATester, RPERLE, (40, 40),
        budget=1000, seed=(12345,) * 6, isp=4, proc=1, crn=False, ranx0=False,
    )
    assert end_seed == (756192979, 932320642, 4060792417, 2566056172, 2930731408, 2805199130)
