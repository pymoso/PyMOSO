"""
Compatibility regression tests for the two in-tree MOCOMPASS/MOPBnB
solvers: this is *not* a check on their algorithmic correctness (not
yet reviewed against the source papers -- see
docs/mocompass-mopbnb-known-issues.md), only that they run on the
current branch and fail predictably rather than crash or silently
corrupt output.

Three things this file pins:

1. Both solvers now run to completion via the library API -- the thing
   that was actually broken before this fix (random.sample() no longer
   accepts a set argument on Python 3.11+, and both solvers called it
   on sets throughout).
2. Missing --param lb/ub/sprn raises a real, chained TypeError (the
   RASolver.__init__ idiom) instead of the bare sys.exit() both files
   called directly before this fix -- library-hostile, and the exact
   anti-pattern KNOWN_ISSUES.md issue 4 already eliminated elsewhere.
3. crn=True is refused with a clear RuntimeError, at construction time,
   both via the library and via the CLI -- see
   docs/rng-interface-design.md sections 4.2-4.3 for why: both solvers
   call orc.crn_advance() exactly once, at the end of solve(), which
   silently makes every hit() call in the run replay identical draws
   under --crn.
"""
import subprocess

import pytest

from pymoso.chnutils import solve, testsolve
from pymoso.problems.probtpa import ProbTPA
from pymoso.solvers.mocompass import MOCOMPASS
from pymoso.solvers.mopbnb import MOPBnB
from pymoso.testers.tpatester import TPATester

pytestmark = pytest.mark.timeout(90)

SOLVERS = [("MOCOMPASS", MOCOMPASS), ("MOPBnB", MOPBnB)]
BOX_KWARGS = dict(lb=0, ub=50)
SOLVE_KWARGS = dict(budget=300, seed=(12345,) * 6, simpar=1, crn=False, **BOX_KWARGS)


@pytest.mark.parametrize("name,cls", SOLVERS, ids=[c[0] for c in SOLVERS])
def test_solver_runs_to_completion(name, cls):
    res, end_seed = solve(ProbTPA, cls, (40, 40), **SOLVE_KWARGS)
    assert res is not None
    assert len(end_seed) == 6


@pytest.mark.parametrize("name,cls", SOLVERS, ids=[c[0] for c in SOLVERS])
def test_missing_lb_ub_raises_chained_typeerror(name, cls):
    kwargs = dict(SOLVE_KWARGS)
    del kwargs["lb"]
    del kwargs["ub"]
    with pytest.raises(TypeError) as exc_info:
        solve(ProbTPA, cls, (40, 40), **kwargs)
    assert "requires an upper and lower bound" in str(exc_info.value)
    assert isinstance(exc_info.value.__cause__, KeyError)


@pytest.mark.parametrize("name,cls", SOLVERS, ids=[c[0] for c in SOLVERS])
def test_crn_refused_at_construction(name, cls):
    kwargs = dict(SOLVE_KWARGS)
    kwargs["crn"] = True
    with pytest.raises(RuntimeError) as exc_info:
        solve(ProbTPA, cls, (40, 40), **kwargs)
    msg = str(exc_info.value)
    assert name in msg
    assert "--crn" in msg
    assert "docs/mocompass-mopbnb-known-issues.md" in msg


@pytest.mark.parametrize("name,cls", SOLVERS, ids=[c[0] for c in SOLVERS])
@pytest.mark.parametrize("simpar", [2, 4])
def test_simpar_results_match_serial(name, cls, simpar):
    """Both solvers call hit() with replication counts > 1 in normal
    operation (MOCOMPASS's ax can exceed 1 comparing against neighbors;
    MOPBnB's R0/rdiff start at 20 and only grow), so Oracle.hit()'s
    parallel branch (simpar > 1 and m > 1) is genuinely exercised here,
    not vacuous."""
    serial = solve(ProbTPA, cls, (40, 40), **SOLVE_KWARGS)
    parallel_kwargs = dict(SOLVE_KWARGS, simpar=simpar)
    parallel = solve(ProbTPA, cls, (40, 40), **parallel_kwargs)
    assert parallel == serial


@pytest.mark.parametrize("name,cls", SOLVERS, ids=[c[0] for c in SOLVERS])
@pytest.mark.parametrize("proc", [1, 2])
def test_proc_results_match_serial(name, cls, proc):
    """Registered in pymoso/solvers/__init__.py, MOCOMPASS/MOPBnB are
    real installed modules like RSPLINE, not dynamically-loaded custom
    files -- the forkserver/--proc transport gap (KNOWN_ISSUES.md issue
    9) is specific to the latter, so this is expected to pass under
    forkserver on 3.14, the same as test_parallel_dispatch.py's
    equivalent RSPLINE/ExpensiveTester case."""
    kwargs = dict(budget=300, seed=(12345,) * 6, isp=2, crn=False, **BOX_KWARGS)
    serial_res, serial_endseed = testsolve(TPATester, cls, (40, 40), proc=1, **kwargs)
    res, endseed = testsolve(TPATester, cls, (40, 40), proc=proc, **kwargs)
    assert res == serial_res
    assert endseed == serial_endseed


@pytest.mark.parametrize("name", ["MOCOMPASS", "MOPBnB"])
def test_crn_refused_via_cli(name, tmp_path):
    cmd = [
        "pymoso", "solve", "--budget=300", "--crn",
        "--param", "lb", "0", "--param", "ub", "50",
        "ProbTPA", name, "40", "40",
    ]
    proc = subprocess.run(cmd, cwd=tmp_path, capture_output=True, text=True)
    assert proc.returncode != 0
    assert "does not support --crn" in proc.stdout
    assert "Traceback" not in proc.stdout
