import re
import subprocess

import pytest

from _pymoso_cli import CLI_TIMEOUT, pymoso_argv
from pymoso.chnutils import solve, testsolve
from pymoso.problems.probtpa import ProbTPA
from pymoso.solvers.rperle import RPERLE
from pymoso.testers.tpatester import TPATester

# Recaptured against the exact-integer jump-ahead fix (see
# KNOWN_ISSUES.md issue 1), then again for every crnflag=False case
# (docs/rng-interface-design.md §12 step 4b), a third time for the
# replication-independence fix (§12's unnumbered prerequisite entry
# before step 8), a fourth time for §12 step 8 stage 1
# (Oracle.get_endseed() wired into RASolver.solve/rasolve and
# MOCOMPASS/MOPBnB's own solve()), and a fifth time -- this capture --
# for step 8 stage 2: testsolve()'s own endseed is now the real
# aggregated high-water mark across every isp path (chnutils.testsolve,
# after par_runs() returns each path's own oracle_high_water_mark),
# replacing get_testsolve_prnstreams's reservation value. Only
# testsolve_tpa/testsolve_mocompass/testsolve_mopbnb and the
# testsolve() library case moved this time -- solve()'s own cases
# (already on the real formula since stage 1) are untouched.
# testsolve_tpa/testsolve_mocompass/testsolve_mopbnb used to be
# bit-identical (the testsolve()-shaped analog of the mocompass_tpa/
# mopbnb_tpa collision stage 1 fixed); the three-way match now breaks,
# as expected going in -- each reflects its own solver's real
# consumption. A sixth time, for the testsolve() role-layout fix
# (KNOWN_ISSUES.md issue 10): get_testsolve_prnstreams used to root the
# oracle role wherever its solver-stream loop ended, which made path
# 0's oracle stream share a seed with the last path's solver stream
# AND made every path's oracle streams depend on --isp. Fixing both
# moved every testsolve oracle root, so the three testsolve_* cases and
# the testsolve() library case moved again; every solve() case is
# untouched (solve() was never affected). All six sets of prior values
# are preserved in
# tests/golden/README.md for historical reference -- none are
# restorable defaults; each prior mechanism (the jump-ahead bug, the
# pre-4b order-dependence defect, the replication-collision defect,
# call-count-only endseed reporting, at both the solve() and
# testsolve() layers, and the testsolve() role layout) was wrong in its
# own way.

# The MOCOMPASS and MOPBnB solvers were renamed ExampleSearchSolver and
# ExampleBnBSolver, and their cases with them: mocompass_tpa ->
# example_search_tpa, mopbnb_tpa -> example_bnb_tpa, testsolve_mocompass
# -> testsolve_example_search, testsolve_mopbnb -> testsolve_example_bnb.
# No value moved (the end seed does not depend on the solver's name;
# checked by running all four under the new names first). The comments
# above and below, and tests/golden/README.md, use the old names for
# what happened under them.

# A seventh capture, for the relaxation fix (docs/algorithm-audit.md
# finding 2: R-PERLE, R-PE and R-MinRLE now relax by se*m**(1/2 - beta),
# the preprint's formula). rperle_tpa, rperle_tpa_simpar2, rpe_tpa,
# rminrle_tpa, testsolve_tpa and the solve() library case moved.
# rperle_tpa_seed2 and rperle_tpa_crn did NOT, although both returned
# different solutions -- seed2's {(28,31),(29,31),(30,31)} became
# {(21,20),(22,16)} with the end seed unchanged. That is the end seed's
# blind spot (docs/end-seed-scope.md, the seventh instance), not
# evidence that those runs were unaffected. tests/golden/README.md has
# the before and after of every case.

# An eighth capture, for the traceback fix (docs/algorithm-audit.md
# finding 1). Only the testsolve() library case moved: its path 3 ran 13
# iterations instead of 12 and returned {(36,29), (39,19)} instead of
# {(21,31)}. Every solve() case returned the same solution, simcalls and
# end seed as before -- checked directly, not inferred from the end
# seeds (tests/golden/README.md).

# A ninth capture, for the tie-break fix (docs/algorithm-audit.md
# finding 7): PE now breaks a tie between the objectives with a draw
# from the solver's stream. Every R-PERLE and R-PE case's solution
# moved. rperle_tpa_crn kept its end seed again, and the testsolve()
# library case's end seed went back to its value from before the
# traceback fix while every one of its four paths returned something
# different from both earlier captures (tests/golden/README.md;
# docs/end-seed-scope.md, the seventh instance).

# A tenth capture, for the search-limit fix (finding 9): only
# rspline_simpleso, the one-dimensional case. An eleventh, for the
# SPLINE stop (finding 14): rminrle_tpa and testsolve_tpa; every other
# case's solution was compared and is unchanged. A twelfth, for PE's
# LWEP filter (finding 3): every R-PERLE and R-PE case's solution moved
# and rperle_tpa, rperle_tpa_simpar2 and the solve() library case kept
# their end seed, a third time for this blind spot (tests/golden/
# README.md; docs/end-seed-scope.md, the seventh instance).
#
# No capture for SPLI's return at an infeasible point (finding 5): five
# solutions moved, in rperle_tpa, rpe_tpa, rperle_tpa_crn and one path
# each of the two testsolve cases, and no end seed did. Only
# tests/test_solution_sensitivity.py failed (tests/golden/README.md).

SEED_RE = re.compile(r"^--\s+(?:next|ending) seed:\s+(.+)$", re.M)

CASES = {
    "rperle_tpa": (
        ["pymoso", "solve", "--budget=1000", "ProbTPA", "RPERLE", "40", "40"],
        (2431818911, 3719736500, 2728328142, 1004091251, 3855901505, 2641704658),
    ),
    "rminrle_tpa": (
        ["pymoso", "solve", "--budget=1000", "ProbTPA", "RMINRLE", "40", "40"],
        (934352227, 2566036280, 3952654006, 4077942181, 2316375006, 212199263),
    ),
    # rpe_tpa coincides with rperle_tpa again (since finding 3's fix):
    # the same solution, simulation calls and end seed, so R-PERLE's RLE,
    # all that separates the two, changed nothing in this run (inferred
    # from the identical results, not traced). From the tie-break fix
    # until then they differed. The end seed is one past the largest
    # coordinate a run touched, which the iteration alone does not fix
    # (it includes the largest point code and its replications).
    "rpe_tpa": (
        ["pymoso", "solve", "--budget=1000", "ProbTPA", "RPE", "40", "40"],
        (2431818911, 3719736500, 2728328142, 1004091251, 3855901505, 2641704658),
    ),
    "rspline_simpleso": (
        ["pymoso", "solve", "--budget=1000", "ProbSimpleSO", "RSPLINE", "40"],
        (1637142171, 3902145111, 18424598, 4071908608, 2396963664, 4071290962),
    ),
    # testsolve_tpa/testsolve_mocompass/testsolve_mopbnb used to be
    # bit-identical -- the testsolve()-shaped analog of the mocompass_tpa/
    # mopbnb_tpa collision, and the concrete gap step 8 stage 2 (docs/
    # rng-interface-design.md §12) closes: each now reflects the real
    # aggregated oracle-role high-water mark across every isp path, so
    # the three-way match breaks, as expected going in.
    "testsolve_tpa": (
        ["pymoso", "testsolve", "--budget=1000", "--isp=4", "--metric",
         "TPATester", "RPERLE"],
        (3152774270, 410798641, 30954636, 1162836765, 3775738568, 4231190908),
    ),
    # rperle_tpa_crn moved too, contrary to this golden's own long-
    # standing expectation of staying fixed while the crnflag=False
    # cases moved around it -- a real finding, not absorbed silently:
    # see docs/rng-interface-design.md §8.2's "Wired in as of step 8
    # stage 1" note for the full trace (rasolve()'s own trailing,
    # unconditional _advance_iteration() call past the last iteration that
    # actually ran). The new value is a correct tightening, not a
    # regression -- confirmed nothing beyond it was ever touched.
    "rperle_tpa_crn": (
        ["pymoso", "solve", "--budget=1000", "--crn", "ProbTPA", "RPERLE", "40", "40"],
        (923826343, 324720588, 3520057607, 2369325274, 481703105, 875203729),
    ),
    "rperle_tpa_seed2": (
        ["pymoso", "solve", "--budget=1000", "--seed", "1,2,3,4,5,6",
         "ProbTPA", "RPERLE", "40", "40"],
        (3017716348, 1164624147, 1959750905, 3905490566, 3460109705, 2293446127),
    ),
    "rperle_tpa_simpar2": (
        ["pymoso", "solve", "--budget=1000", "--simpar=2", "ProbTPA", "RPERLE", "40", "40"],
        (2431818911, 3719736500, 2728328142, 1004091251, 3855901505, 2641704658),
    ),
    # mocompass_tpa and mopbnb_tpa now diverge -- the fix step 8 exists
    # for: previously identical despite verified-different internal
    # consumption (§8.2). Confirmed before regenerating, not assumed.
    "example_search_tpa": (
        ["pymoso", "solve", "--budget=1000", "--param", "lb", "0", "--param", "ub", "50",
         "ProbTPA", "ExampleSearchSolver", "40", "40"],
        (1146796796, 3308305028, 386855827, 2694500999, 2221614380, 1025642763),
    ),
    "example_bnb_tpa": (
        ["pymoso", "solve", "--budget=1000", "--param", "lb", "0", "--param", "ub", "50",
         "ProbTPA", "ExampleBnBSolver", "40", "40"],
        (3809509318, 1900386143, 1103642148, 1010814338, 790187922, 3654332215),
    ),
    "testsolve_example_search": (
        ["pymoso", "testsolve", "--budget=1000", "--isp=4", "--param", "lb", "0",
         "--param", "ub", "50", "TPATester", "ExampleSearchSolver"],
        (2346975725, 1224100873, 2386202199, 4246821866, 1768963681, 2406381760),
    ),
    "testsolve_example_bnb": (
        ["pymoso", "testsolve", "--budget=1000", "--isp=4", "--param", "lb", "0",
         "--param", "ub", "50", "TPATester", "ExampleBnBSolver"],
        (559300817, 691733575, 3730937374, 1133024474, 2779640938, 790303042),
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
    assert end_seed == (2431818911, 3719736500, 2728328142, 1004091251, 3855901505, 2641704658)


def test_library_testsolve_end_seed_matches_baseline():
    res, end_seed = testsolve(
        TPATester, RPERLE, (40, 40),
        budget=1000, seed=(12345,) * 6, isp=4, proc=1, crn=False, ranx0=False,
    )
    assert end_seed == (3821022682, 3698201652, 1914137393, 374897783, 2982944267, 2480987988)
