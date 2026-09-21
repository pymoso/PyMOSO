"""
Regression tests: chnutils.solve/testsolve's documented minimal library
usage -- solve(problem, solver, x0) / testsolve(tester, solver, x0),
with no kwargs at all -- must work, not raise KeyError. Commit 917bf06
on the canonical repository removed the defaults these kwargs.pop()
calls had at the shared merge-base (budget/seed/isp/proc/crn); ranx0
never had one in any version checked. See KNOWN_ISSUES.md issue 6.

Also checks that the restored defaults actually match the CLI's own
documented values, parsed directly from argparse's own parser rather
than re-typed -- a coupling test, not just a comment, so a change to
either side that isn't mirrored in the other fails loudly here instead
of drifting silently. (Originally checked against docopt's parsed
output; rewritten against argparse as part of the docopt->argparse
migration -- same property, different parser.)
"""
import pymoso.cli as cli
from pymoso.chnutils import (
    solve, testsolve,
    DEFAULT_BUDGET, DEFAULT_SEED, DEFAULT_SIMPAR, DEFAULT_ISP,
    DEFAULT_PROC, DEFAULT_CRN, DEFAULT_RANX0,
)
from pymoso.problems.probtpa import ProbTPA
from pymoso.solvers.rperle import RPERLE
from pymoso.testers.tpatester import TPATester


# ---------------------------------------------------------------------------
# The documented minimal calls actually work now.
# ---------------------------------------------------------------------------

def test_solve_with_only_required_arguments():
    res, end_seed = solve(ProbTPA, RPERLE, (40, 40))
    assert res is not None
    assert len(end_seed) == 6


def test_testsolve_with_only_required_arguments():
    res, end_seed = testsolve(TPATester, RPERLE, (40, 40))
    assert res is not None
    assert len(end_seed) == 6


# ---------------------------------------------------------------------------
# Partial kwargs: whatever isn't given still falls back to the default,
# not to a KeyError on the *next* missing key.
# ---------------------------------------------------------------------------

def test_solve_with_partial_kwargs():
    res, end_seed = solve(ProbTPA, RPERLE, (40, 40), budget=300)
    assert res is not None


def test_testsolve_with_partial_kwargs():
    res, end_seed = testsolve(TPATester, RPERLE, (40, 40), budget=300, crn=True)
    assert res is not None


# ---------------------------------------------------------------------------
# The restored defaults match the CLI's own documented values, checked
# against argparse's actual parsed output rather than by re-typing the
# numbers -- so the two genuinely cannot drift apart unnoticed.
# ---------------------------------------------------------------------------

def test_defaults_match_argparse_parsed_values():
    parser = cli.build_parser()

    args = parser.parse_args(['solve', 'ProbTPA', 'RPERLE', '1'])
    assert args.budget == DEFAULT_BUDGET
    assert args.simpar == DEFAULT_SIMPAR

    args = parser.parse_args(['testsolve', 'TPATester', 'RPERLE'])
    assert args.budget == DEFAULT_BUDGET
    assert args.isp == DEFAULT_ISP
    assert args.proc == DEFAULT_PROC


def test_default_seed_matches_cli_fallback_object():
    """commands/solve.py and commands/testsolve.py import DEFAULT_SEED
    directly from chnutils rather than hardcoding their own copy of the
    literal -- this just confirms that import actually happened, not a
    parallel constant of the same value."""
    from pymoso.commands.solve import DEFAULT_SEED as solve_default_seed
    from pymoso.commands.testsolve import DEFAULT_SEED as testsolve_default_seed
    assert solve_default_seed is DEFAULT_SEED
    assert testsolve_default_seed is DEFAULT_SEED


def test_default_values_are_the_documented_ones():
    assert DEFAULT_BUDGET == 200
    assert DEFAULT_SEED == (12345,) * 6
    assert DEFAULT_SIMPAR == 1
    assert DEFAULT_ISP == 1
    assert DEFAULT_PROC == 1
    assert DEFAULT_CRN is False
    assert DEFAULT_RANX0 is False
