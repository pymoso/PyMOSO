"""
Layer 1 (making the README's executable content testable): every
template and snippet in the README that a user would copy exists as a
real file under pymoso/examples/, is exercised here at a small budget,
and is checked byte-identical to its README code block so the two
cannot silently drift apart.

Convention for fragments (blocks that are not a whole file):
  - The two metric examples are standalone top-level functions, byte-
    identical to their file (imports are scaffolding outside the
    compared fragment, extracted via inspect.getsource).
  - The seven "Template MOSO Solver" snippets share variables across
    sub-sections (x, nbors, sorted_feas, xmin, nondom) and are stored
    concatenated, in README order, in one file
    (algorithm_snippets.py), split back into per-section pieces by the
    '##### <title>' markers also used to regenerate the README's
    separate code fences for each sub-section.
  - myproblem.py/mytester.py/myaccel.py/myraalg.py/mymosoalg.py are
    whole-file blocks: the entire file is the block. None of these
    carry a module docstring (matching this codebase's current,
    unconverted docstring style throughout) -- explanatory prose for
    MyRAAlg/MyMOSOAlg lives in the README text around their code
    blocks instead, not duplicated into the files.
  - solve_example.py/testsolve_example.py are each the concatenation
    of two README blocks; split back on a fixed marker line.

Two C/ctypes examples ("Example Oracle that Wraps a C Simulation",
"Example Wrapper with PyMOSO Random Numbers") need a compiled library
and are intentionally NOT exercised -- see test_c_wrapper_examples_are_
intentionally_untested below. Do not fake these.
"""
import inspect
import re
import sys

import pytest

sys.path.insert(0, "pymoso/examples")

README = open("README.md", encoding="utf-8").read()
PY_BLOCKS = re.findall(r"```python\n(.*?)```", README, re.DOTALL)
assert len(PY_BLOCKS) == 20, f"expected 20 python blocks in README, found {len(PY_BLOCKS)}"


def read_file(name):
    with open(f"pymoso/examples/{name}", encoding="utf-8") as f:
        return f.read()


def split_marked_sections(text):
    """Split algorithm_snippets.py on '##### <title>' markers, dropping
    the markers themselves and the leading module docstring."""
    body = text.split("'''", 2)[2]
    parts = re.split(r"^##### .*\n", body, flags=re.MULTILINE)
    return [p.strip("\n") for p in parts if p.strip("\n")]


# ---------------------------------------------------------------------------
# Byte-identity: each README code block matches its source file exactly.
# ---------------------------------------------------------------------------

def test_myproblem_block_matches_file():
    assert PY_BLOCKS[0] == read_file("myproblem.py")


def test_mytester_block_matches_file():
    assert PY_BLOCKS[1] == read_file("mytester.py")


@pytest.mark.parametrize("idx", [2, 3])
def test_c_wrapper_examples_are_intentionally_untested(idx):
    """These need a compiled C library (mysim.so) and are not exercised
    -- noted here explicitly rather than silently skipped or faked."""
    assert "ctypes" in PY_BLOCKS[idx]
    pytest.skip("C/ctypes wrapper example: needs a compiled library, not exercised")


def test_metric_example_1_block_matches_function_source():
    import metric_example1
    assert PY_BLOCKS[4] == inspect.getsource(metric_example1.metric)


def test_metric_example_2_block_matches_function_source():
    import metric_example2
    assert PY_BLOCKS[5] == inspect.getsource(metric_example2.metric)


def test_myaccel_block_matches_file():
    assert PY_BLOCKS[6] == read_file("myaccel.py")


def test_myraalg_block_matches_file():
    assert PY_BLOCKS[7] == read_file("myraalg.py")


def test_mymosoalg_block_matches_file():
    assert PY_BLOCKS[8] == read_file("mymosoalg.py")


def test_algorithm_snippets_blocks_match_file_sections():
    sections = split_marked_sections(read_file("algorithm_snippets.py"))
    assert len(sections) == 7
    for block, section in zip(PY_BLOCKS[9:16], sections):
        assert block.strip("\n") == section


def test_solve_example_blocks_match_file():
    content = read_file("solve_example.py")
    split_point = content.index("# example for specifying budget and seed")
    part1 = content[:split_point].rstrip("\n") + "\n"
    part2 = content[split_point:]
    assert PY_BLOCKS[16] == part1
    assert PY_BLOCKS[17] == part2


def test_testsolve_example_blocks_match_file():
    content = read_file("testsolve_example.py")
    split_point = content.index("iter5_soln =")
    part1 = content[:split_point].rstrip("\n") + "\n"
    part2 = content[split_point:]
    assert PY_BLOCKS[18] == part1
    assert PY_BLOCKS[19] == part2


# ---------------------------------------------------------------------------
# Execution: each template/snippet actually runs against the current API.
# ---------------------------------------------------------------------------

BUDGET = 300


def test_myproblem_solves_with_each_applicable_solver():
    from pymoso.chnutils import solve
    from pymoso.solvers.rperle import RPERLE
    from pymoso.solvers.rminrle import RMINRLE
    from pymoso.solvers.rpe import RPE
    from pymoso.solvers.rspline import RSPLINE
    import myproblem as mp

    x0 = (0,)
    for solver in (RPERLE, RMINRLE, RPE, RSPLINE):
        res, endseed = solve(mp.MyProblem, solver, x0, budget=BUDGET)
        assert res


def test_mytester_runs_through_testsolve_with_metric():
    from pymoso.chnutils import testsolve
    from pymoso.solvers.rperle import RPERLE
    from mytester import MyTester

    run_data, endseed = testsolve(MyTester, RPERLE, (1,), isp=2, crn=True, radius=2, budget=BUDGET)
    assert len(run_data) == 2  # run_data is a dict keyed 0..isp-1, not a list
    tester = MyTester()
    for isp_result in run_data.values():
        last_iter = max(isp_result["itersoln"])
        m = tester.metric(isp_result["itersoln"][last_iter])
        assert isinstance(m, float)


def test_myaccel_instantiates_and_runs():
    from pymoso.chnutils import solve
    import myproblem as mp
    from myaccel import MyAccel

    res, endseed = solve(mp.MyProblem, MyAccel, (0,), budget=BUDGET)
    assert res


def test_myraalg_spsolve_runs_directly():
    """MyRAAlg cannot reach a normal solve() completion as written: its
    spsolve never calls self.estimate, so self.num_calls never advances
    and the RA loop cannot terminate via budget exhaustion (as of
    docs/rng-interface-design.md §12 step 4b, it instead runs ~3882
    fast, simulation-free iterations before RASolver.rasolve's own
    calc_b overflows Python's float range and raises OverflowError --
    KNOWN_ISSUES.md's MyRAAlg entry, see README's "Template RA Solver"
    prose). Test the actual contract instead: spsolve is callable and
    returns its input unchanged."""
    from pymoso.prng.mrg32k3a import MRG32k3a
    from pymoso.problems.probtpa import ProbTPA
    from myraalg import MyRAAlg

    rng = MRG32k3a((12345,) * 6)
    rng.set_class_cache(False)
    orc = ProbTPA(rng)
    orc.set_crnflag(False)
    orc.simpar = 1
    solver = MyRAAlg(orc, sprn=MRG32k3a((1, 2, 3, 4, 5, 6)), x0=(1, 1))
    warm_start = {(1, 1)}
    assert solver.spsolve(warm_start) == warm_start


def test_mymosoalg_parses_and_subclasses_mososolver():
    """Illustrative only -- see README's "Template MOSO Solver" prose.
    Confirm it is valid Python and a real MOSOSolver subclass; do not
    call solve()."""
    import ast
    import mymosoalg
    from pymoso.chnbase import MOSOSolver

    ast.parse(read_file("mymosoalg.py"))
    assert issubclass(mymosoalg.MyMOSOAlg, MOSOSolver)


def test_metric_example_1_runs():
    import metric_example1

    class FakeTester:
        def __init__(self):
            self.true_g = lambda x: (x[0] ** 2, (x[0] - 2) ** 2)
            self.answer = [{(0, 4)}, {(4, 0)}, {(1, 1)}]

    result = metric_example1.metric(FakeTester(), {(1,), (2,)})
    assert isinstance(result, float)


def test_metric_example_2_runs():
    import metric_example2

    class FakeTester:
        def __init__(self):
            self.true_g = lambda x: x[0] ** 2
            self.answer = 0

    result = metric_example2.metric(FakeTester(), {(3,)})
    assert result == 9


def test_algorithm_snippets_run_against_a_live_solver():
    """A live RASolver instance mid-iteration, matching the snippets'
    own implied shape (3-dimensional, bi-objective -- ProbTPC, not
    MyProblem, which is 1-dimensional)."""
    from pymoso.prng.mrg32k3a import MRG32k3a
    from pymoso.problems.probtpc import ProbTPC
    from myraalg import MyRAAlg

    rng = MRG32k3a((12345,) * 6)
    rng.set_class_cache(False)
    orc = ProbTPC(rng)
    orc.set_crnflag(False)
    orc.simpar = 1
    solver = MyRAAlg(orc, sprn=MRG32k3a((11, 22, 33, 44, 55, 66)), x0=(1, 1, 1))
    solver.nu = 1
    solver.m = solver.calc_m(1)
    solver.b = solver.calc_b(1)
    solver.gbar = {}
    solver.sehat = {}

    ns = {"self": solver}
    src = read_file("algorithm_snippets.py")
    exec(compile(src, "algorithm_snippets.py", "exec"), ns)
    assert "nondom" in ns and len(ns["nondom"]) >= 1


def test_solve_example_runs(tmp_path):
    """Import and call with the file's own logic, at the small BUDGET
    above rather than its literal budget=10000/simpar=4 (the simpar
    line is covered separately below, since --simpar now works on this
    base but the worker-lifecycle context manager makes it slower to
    exercise here than it's worth for a byte-identity/smoke test)."""
    from pymoso.chnutils import solve
    import pymoso.solvers.rperle as rp
    import myproblem as mp

    x0 = (97,)
    soln = solve(mp.MyProblem, rp.RPERLE, x0, budget=BUDGET)
    assert soln

    seed = (111, 222, 333, 444, 555, 666)
    soln1 = solve(mp.MyProblem, rp.RPERLE, x0, budget=BUDGET, seed=seed)
    assert soln1

    soln3 = solve(mp.MyProblem, rp.RPERLE, x0, budget=BUDGET, radius=2, betaeps=0.3, betadel=0.4)
    assert soln3

    soln4 = solve(mp.MyProblem, rp.RPERLE, x0, budget=BUDGET, crn=True, seed=seed, radius=5)
    assert soln4


def test_solve_example_simpar_line_now_succeeds():
    """--simpar now works on this base (fixed upstream by 917bf06,
    unrelated to and predating this migration -- see
    docs/upstream-simpar.md), unlike the equivalent test on the earlier
    fork, which expected this exact call to fail with the pre-existing
    TypeError (KNOWN_ISSUES.md issue 2). x0=(97,) is feasible for
    MyProblem ([-100,100]), so this also isn't the infeasible-x0
    worker-leak hang tests/test_simpar_worker_lifecycle.py covers."""
    from pymoso.chnutils import solve
    import pymoso.solvers.rperle as rp
    import myproblem as mp

    res, endseed = solve(mp.MyProblem, rp.RPERLE, (97,), budget=BUDGET, crn=True, simpar=4)
    assert res


def test_testsolve_example_runs():
    from pymoso.chnutils import testsolve
    import pymoso.solvers.rperle as rp
    from mytester import MyTester

    x0 = (1,)
    run_data, endseed = testsolve(MyTester, rp.RPERLE, x0, isp=2, crn=True, radius=2, budget=BUDGET)
    iter_keys = sorted(run_data[0]["itersoln"])
    last_iter = iter_keys[-1]
    iter_soln = run_data[0]["itersoln"][last_iter]
    metric_val = MyTester().metric(iter_soln)
    assert isinstance(metric_val, float)
