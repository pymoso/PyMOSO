"""
Live, ongoing end-to-end contract for the pymoso CLI, independent of
which argument-parsing library backs it. Originally split off from
tests/test_cli_characterization.py's docopt-specific tests once
pymoso/cli.py moved to argparse; that file was later deleted (it was
the only thing in this suite with a live `docopt` import, an
undeclared test-time dependency -- see docs/phase2c-cli-migration.md
and KNOWN_ISSUES.md issue 6, which preserve what it demonstrated). The
subprocess-level checks here describe how the real `pymoso` command
behaves today, and should be updated deliberately (with the reason
recorded) whenever that behavior legitimately changes.

See docs/phase2c-cli-migration.md for the full, reasoned list of
differences from the pre-migration (docopt) behavior that this file's
expectations encode.

Every test here spawns the real `pymoso` subprocess, so a hang in the
CLI (see tests/test_simpar_worker_lifecycle.py for the specific bug
this guards against) would otherwise hang the whole suite.
pytest-timeout's module-level marker below forces any such hang to
fail after 60 seconds -- generous over every real test's ~1-3s
runtime -- instead of consuming the run indefinitely.
"""
import subprocess

import pytest

from pymoso import __version__

pytestmark = pytest.mark.timeout(60)


def run(args, cwd):
    """Run the real `pymoso` console script as a subprocess."""
    return subprocess.run(["pymoso"] + args, cwd=cwd, capture_output=True, text=True)


# ---------------------------------------------------------------------------
# The 8 literal "Examples:" lines from the README. Unaffected by the
# parser migration -- none of them exercise an edge case whose behavior
# changed as a result of switching parsers. solve_simpar_param DOES
# differ from the equivalent test on the earlier fork, though, for an
# unrelated reason: --simpar was fixed upstream (917bf06, see
# docs/upstream-simpar.md) before this migration ever touched this base.
# ---------------------------------------------------------------------------
README_EXAMPLES = {
    "listitems": (["listitems"], 0),
    "solve_basic": (["solve", "ProbTPA", "RPERLE", "4", "14"], 0),
    "solve_budget_odir": (
        ["solve", "--budget=100000", "--odir=test1", "ProbTPB", "RMINRLE", "3", "12"],
        0,
    ),
    "solve_seed": (
        ["solve", "--seed", "12345,32123,5322,2,9543,666666666",
         "ProbTPC", "RPERLE", "5", "5", "5"],
        0,  # was x0=(31,21,11), infeasible for ProbTPC ([-10,10] per
            # component at the default density_factor=2) -- a real,
            # pre-existing README bug, unrelated to CLI parsing, fixed
            # in Layer 2 (docs/phase2c-cli-migration.md and this
            # migration's Layer 2 commit). (5,5,5) is feasible with the
            # same seed, confirmed directly.
    ),
    "solve_simpar_param": (
        ["solve", "--simpar=4", "--param", "betaeps", "0.4", "ProbTPA", "RPERLE", "30", "30"],
        0,  # --simpar now works on this base (fixed upstream by 917bf06,
            # independently of anything this project has done) -- this
            # used to fail (KNOWN_ISSUES.md issue 2) on the earlier fork.
    ),
    "solve_param": (
        ["solve", "--param", "radius", "3", "ProbTPA", "RPERLE", "45", "45"],
        0,
    ),
    "testsolve_no_x": (
        ["testsolve", "--isp=16", "--proc=4", "TPATester", "RPERLE"],
        0,
    ),
    "testsolve_full": (
        ["testsolve", "--isp=20", "--proc=10", "--metric", "--crn", "TPBTester",
         "RMINRLE", "9", "9"],
        0,
    ),
}


@pytest.mark.parametrize("name", sorted(README_EXAMPLES))
def test_readme_example_end_to_end(name, tmp_path):
    argv, expected_exit = README_EXAMPLES[name]
    proc = run(argv, tmp_path)
    assert proc.returncode == expected_exit, (proc.stdout, proc.stderr)


def test_readme_example_details_solve_basic(tmp_path):
    proc = run(README_EXAMPLES["solve_basic"][0], tmp_path)
    assert "** Solving  ProbTPA  using  RPERLE  **" in proc.stdout
    assert "-- Done!" in proc.stdout


def test_readme_example_details_seed_now_succeeds(tmp_path):
    """Was x0=(31,21,11), infeasible for ProbTPC -- fixed to (5,5,5) in
    Layer 2. Confirmed here rather than assumed: this example actually
    runs to completion now."""
    proc = run(README_EXAMPLES["solve_seed"][0], tmp_path)
    assert proc.returncode == 0
    assert "-- Done!" in proc.stdout


def test_readme_example_details_simpar_now_succeeds(tmp_path):
    """Confirmed, not assumed: --simpar=4 completes a real solve on this
    base. See docs/upstream-simpar.md for why (917bf06's persistent-
    worker-pool rework, upstream, predates and is unrelated to this
    migration)."""
    proc = run(README_EXAMPLES["solve_simpar_param"][0], tmp_path)
    assert proc.returncode == 0
    assert "-- Done!" in proc.stdout
    assert "get_next_prnstream() missing 1 required positional argument" not in proc.stdout


def test_readme_example_details_testsolve_full(tmp_path):
    proc = run(README_EXAMPLES["testsolve_full"][0], tmp_path)
    assert "-- Done!" in proc.stdout
    assert "-- Metric run time" in proc.stdout


# ---------------------------------------------------------------------------
# --seed: one comma-separated token, arity/content validated by the
# selected generator's own validate_seed at runtime (§3.7/§12 step 6b)
# -- not argparse's nargs=6/type=int arity enforcement any more (that
# mechanism could not survive generator selection: MRG31k3p is also 6
# integers, but Philox4x32 is 2 -- a single hardcoded arity can't serve
# more than one generator). The two tests below intentionally REPLACE
# (not adjust) test_seed_with_too_few_values_is_now_cleanly_rejected/
# test_seed_with_too_many_values_still_fails_loudly_but_not_cleanly:
# those pinned specific quirks of the nargs=6 mechanism itself (a
# silent misparse at 5 values, an overflow into <problem> at 7+) that
# have no equivalent once that mechanism is gone -- this is not a
# regression in what they covered, it's a genuine improvement: both
# the too-few and too-many cases now get the identical, correctly-
# scoped "mrg32k3a expects 6 integers, got N" message, where the old
# mechanism could only sometimes catch undercounts cleanly and never
# caught overcounts cleanly at all.
# ---------------------------------------------------------------------------

def test_seed_with_six_values_still_works(tmp_path):
    proc = run(["solve", "--seed", "1,2,3,4,5,6",
                "ProbTPA", "RPERLE", "4", "14"], tmp_path)
    assert proc.returncode == 0
    assert "-- Done!" in proc.stdout


@pytest.mark.parametrize("n_values", [0, 1, 3, 5])
def test_seed_with_too_few_values_is_cleanly_rejected_by_validate_seed(n_values, tmp_path):
    seed_arg = ",".join(str(i) for i in range(1, n_values + 1))
    # "".split(",") == [''] -- one blank token, not zero -- so compute
    # the expected count from the same split validate_seed itself does,
    # rather than assume it always equals n_values.
    expected_count = len(seed_arg.split(","))
    proc = run(["solve", "--seed", seed_arg, "ProbTPA", "RPERLE", "4", "14"], tmp_path)
    assert "mrg32k3a expects 6 integers, got {0}".format(expected_count) in proc.stdout
    assert "Traceback" not in proc.stdout


@pytest.mark.parametrize("n_values", [7, 8])
def test_seed_with_too_many_values_is_also_cleanly_rejected_by_validate_seed(n_values, tmp_path):
    """The old nargs=6 mechanism could never cleanly catch this case at
    all (the overflow silently shifted into <problem>, confirmed on
    the old mechanism by this same test's own prior version) --
    validate_seed catches it exactly the same way it catches
    undercounts. A genuine fix, not a residual gap carried forward."""
    seed_arg = ",".join(str(i) for i in range(1, n_values + 1))
    proc = run(["solve", "--seed", seed_arg, "ProbTPA", "RPERLE", "4", "14"], tmp_path)
    assert "mrg32k3a expects 6 integers, got {0}".format(n_values) in proc.stdout
    assert "Traceback" not in proc.stdout


# ---------------------------------------------------------------------------
# --param: repeatable, each occurrence takes exactly 2 values
# ---------------------------------------------------------------------------

def test_repeated_param_still_works(tmp_path):
    """x0=(40, 40), not the (97, 97) used in the equivalent test on the
    earlier fork: (97, 97) is infeasible for ProbTPA ([0, 50] per
    component). That was invisible there because --simpar=4 always
    crashed first (KNOWN_ISSUES.md issue 2, fixed upstream since --
    see docs/upstream-simpar.md). On THIS base --simpar actually runs,
    which surfaces a separate, serious bug: an infeasible x0 raises
    after Oracle.set_simpar() has already spawned worker processes but
    before chnutils.solve() reaches orc.mp_cleanup() (skipped on any
    exception), leaking non-daemon Process objects blocked forever on
    queue.get(). Python's multiprocessing atexit machinery then blocks
    the whole CLI process trying to join them, hanging indefinitely
    instead of exiting -- confirmed directly: this exact command with
    (97, 97) hung for 57 minutes before being killed. Not fixed here
    (chnbase.py/chnutils.py are out of scope for this migration); see
    docs/phase2c-cli-migration.md for the writeup. Using a feasible x0
    avoids the exception entirely, exercising --param without
    triggering the hang."""
    proc = run([
        "solve", "--crn", "--simpar=4", "--budget=10000",
        "--seed", "1,2,3,4,5,6", "--odir=Exp1",
        "--param", "mconst", "4", "--param", "betadel", "0.7",
        "ProbTPA", "RPERLE", "40", "40",
    ], tmp_path)
    assert proc.returncode == 0
    assert "-- Done!" in proc.stdout


def test_param_missing_second_value_fails_loudly_but_not_cleanly(tmp_path):
    """Same residual class as the too-many-seed-values case: omitting
    --param's value shifts 'ProbTPA' into <val> and everything after it
    down by one slot, reliably surfacing as a "Problem name is not
    valid" error (here '45' ends up as <problem>) rather than a clean
    "--param requires 2 arguments" message."""
    proc = run(["solve", "--param", "radius", "ProbTPA", "RPERLE", "45", "45"], tmp_path)
    assert "Problem name is not valid" in proc.stdout


# ---------------------------------------------------------------------------
# <x>: one or more components for solve; zero or more for testsolve
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("x", [["4"], ["4", "14"]])
def test_solve_multiple_x_components_still_works(x, tmp_path):
    proc = run(["solve", "ProbTPA", "RPERLE"] + x, tmp_path)
    assert proc.returncode == 0


def test_solve_requires_at_least_one_x(tmp_path):
    proc = run(["solve", "ProbTPA", "RPERLE"], tmp_path)
    assert proc.returncode == 2
    assert "<x>" in proc.stderr


def test_testsolve_x_is_still_optional(tmp_path):
    proc = run(["testsolve", "TPATester", "RPERLE"], tmp_path)
    assert proc.returncode == 0


def test_testsolve_x_may_still_be_given(tmp_path):
    proc = run(["testsolve", "TPBTester", "RMINRLE", "9", "9"], tmp_path)
    assert proc.returncode == 0


# ---------------------------------------------------------------------------
# --help / --version: still exit 0, stdout only. Content is materially
# different in format from docopt's hand-written text (argparse splits
# help across subcommands rather than one combined screen) -- see the
# migration report.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("flag", ["--help", "-h"])
def test_help_exits_zero_and_prints_usage(flag, tmp_path):
    proc = run([flag], tmp_path)
    assert proc.returncode == 0
    assert proc.stderr == ""
    assert "usage:" in proc.stdout
    assert "Examples:" in proc.stdout


@pytest.mark.parametrize("flag", ["--version", "-v"])
def test_version_exits_zero_and_prints_version(flag, tmp_path):
    proc = run([flag], tmp_path)
    assert proc.returncode == 0
    assert proc.stderr == ""
    assert proc.stdout.strip() == __version__


def test_subcommand_help_shows_its_own_options(tmp_path):
    """New capability the monolithic docopt screen didn't have: each
    subcommand has its own --help."""
    proc = run(["solve", "--help"], tmp_path)
    assert proc.returncode == 0
    assert "--simpar" in proc.stdout
    assert "--isp" not in proc.stdout  # testsolve-only option


# ---------------------------------------------------------------------------
# Malformed invocations: missing args, wrong command, bad numeric input.
# Exit code changes from 1 (docopt's sys.exit(usage_string)) to 2
# (argparse's own parser.error(), its standard convention) throughout.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("argv", [
    [],
    ["solve"],
    ["solve", "ProbTPA"],
    ["solve", "ProbTPA", "RPERLE"],
    ["testsolve"],
    ["frobnicate"],
], ids=["empty", "solve-bare", "solve-1arg", "solve-no-x", "testsolve-bare", "unknown-command"])
def test_malformed_invocation_exits_2_with_usage_on_stderr(argv, tmp_path):
    proc = run(argv, tmp_path)
    assert proc.returncode == 2
    assert proc.stdout == ""
    assert "usage:" in proc.stderr


def test_non_integer_budget_is_now_rejected_cleanly_at_parse_time(tmp_path):
    """Improvement over docopt+downstream int(): argparse's type=
    validator catches this before commands/solve.py ever runs, so there
    is no raw traceback -- just a standard argparse error."""
    proc = run(["solve", "--budget=abc", "ProbTPA", "RPERLE", "4", "14"], tmp_path)
    assert proc.returncode == 2
    assert "Traceback" not in proc.stderr
    assert "--budget" in proc.stderr


def test_negative_budget_is_rejected_by_argparse_native_validation(tmp_path):
    """Same protection as commit 82c177b's basecomm.validate_positive_int,
    now expressed as argparse's type=positive_int per this migration's
    instructions -- exit code and stream differ (2/stderr vs. 1/stdout),
    message content is materially the same."""
    proc = run(["solve", "--budget=-5", "ProbTPA", "RPERLE", "4", "14"], tmp_path)
    assert proc.returncode == 2
    assert "--budget: must be a positive integer, got -5" in proc.stderr
    assert "Traceback" not in proc.stderr


# ---------------------------------------------------------------------------
# Ordering permissiveness / the docopt fragility bugs: confirming the
# permissive cases still work (no regression) and the fragile ones are
# now fixed outright, not just relocated.
# ---------------------------------------------------------------------------

def test_options_after_positional_args_still_accepted(tmp_path):
    """Matches docopt: this was never actually enforced (contrary to the
    README's prose), so there is nothing to preserve here except not
    accidentally becoming stricter."""
    proc = run(["solve", "ProbTPA", "RPERLE", "4", "14", "--budget=500"], tmp_path)
    assert proc.returncode == 0


def test_param_option_after_other_options_still_accepted(tmp_path):
    proc = run(["solve", "--param", "radius", "3", "--budget=500",
                "ProbTPA", "RPERLE", "45", "45"], tmp_path)
    assert proc.returncode == 0


def test_seed_and_param_interleaved_out_of_order_now_parses_correctly(tmp_path):
    """This is the actual fix for the silent-misparse bug documented in
    KNOWN_ISSUES.md issue 6 and docs/phase2c-cli-migration.md: --seed
    and --param no longer compete for each other's tokens when given in
    an order no example shows, because argparse treats each optional's
    nargs independently of the others, not as one shared token stream."""
    proc = run([
        "solve", "--param", "radius", "3", "--seed",
        "1,2,3,4,5,6", "ProbTPA", "RPERLE", "4", "14",
    ], tmp_path)
    assert proc.returncode == 0
    assert "-- Done!" in proc.stdout
    assert "1            2            3            4            5            6" in proc.stdout


# ---------------------------------------------------------------------------
# Multi-file custom problems (KNOWN_ISSUES.md issue 11): commands/solve.py
# never added a dynamically-loaded file's own directory to sys.path, so a
# sibling import failed outright -- confirmed on this branch and on a real
# PyPI 1.0.8 install, single process, no --simpar/--proc involved. Fixed
# via basecomm.load_user_module. Single process only; the --simpar/3.14
# transport case is covered separately (see the forkserver-hang tests).
# ---------------------------------------------------------------------------

MULTIFILE_HELPER = '''\
PENALTY = 3.0

def noisy_quadratic(x0, rng):
    z = rng.normalvariate(0, 1)
    return x0**2 + PENALTY*z
'''

MULTIFILE_PROBLEM = '''\
from pymoso.chnbase import Oracle
from helper import noisy_quadratic, PENALTY

class MyProblem(Oracle):
    def __init__(self, rng):
        self.num_obj = 2
        self.dim = 1
        super().__init__(rng)

    def g(self, x, rng):
        feas_range = range(-100, 101)
        obj = []
        is_feas = False
        if len(x) == self.dim:
            is_feas = True
            for i in x:
                if not i in feas_range:
                    is_feas = False
        if is_feas:
            obj1 = noisy_quadratic(x[0], rng)
            z1 = rng.normalvariate(0, 1)
            obj2 = (x[0] - 2)**2 + z1 + 0*PENALTY
            obj = (obj1, obj2)
        return is_feas, obj
'''


def test_multifile_custom_problem_loads_and_solves(tmp_path):
    """A custom problem file importing a sibling helper module must
    load and solve in a single process, no --simpar/--proc. Confirmed
    failing before the fix (KNOWN_ISSUES.md issue 11): raw
    ModuleNotFoundError, identical on this branch and a real PyPI 1.0.8
    install."""
    (tmp_path / 'helper.py').write_text(MULTIFILE_HELPER)
    (tmp_path / 'myproblem.py').write_text(MULTIFILE_PROBLEM)
    proc = run(["solve", "--budget=200", "myproblem.py", "RPERLE", "40"], tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert "ModuleNotFoundError" not in proc.stderr
    assert "-- Done!" in proc.stdout
