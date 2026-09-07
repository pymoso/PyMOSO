"""
Characterization tests for the docopt-based CLI PyMOSO used before the
docopt->argparse migration. These are frozen: DOC below is a literal
copy of pymoso/cli.py's docstring as it stood immediately before that
migration on this branch -- confirmed byte-identical to the docstring
characterized against the earlier fork in 5d7813a, since cli.py was
never touched by any of the 13 commits between the shared merge-base
and github.com/pymoso/PyMOSO's current master. Not a live import from
pymoso.cli -- cli.py's own docstring changes as part of this migration,
and freezing this copy is what lets these tests keep documenting
docopt's specific parsing behavior indefinitely, independent of
anything pymoso/cli.py does today.

They document what docopt did, not what should happen -- see
tests/test_cli.py for the live, ongoing contract on pymoso's actual CLI
behavior (parser-agnostic, via subprocess), and docs/phase2c-cli-migration.md
for the deliberate differences between the two.

`docopt` itself is not a runtime dependency of pymoso after the
migration (see setup.py); it remains a test-only dependency so this
historical record keeps working.
"""
import pytest
from docopt import docopt

DOC = """
pymoso

Usage:
  pymoso listitems
  pymoso solve [--budget=B] [--odir=D] [--crn] [--simpar=P]
    [(--seed <s> <s> <s> <s> <s> <s>)] [(--param <param> <val>)]...
    <problem> <solver> <x>...
  pymoso testsolve [--budget=B] [--odir=D] [--crn] [--isp=T] [--proc=Q]
    [--metric] [(--seed <s> <s> <s> <s> <s> <s>)] [(--param <param> <val>)]...
    <tester> <solver> [<x>...]
  pymoso -h | --help
  pymoso -v | --version

Options:
  --budget=B                Set the simulation budget [default: 200]
  --odir=D                  Set the output file directory name. [default: testrun]
  --crn                     Set if common random numbers are desired.
  --simpar=P                Set number of parallel processes for simulation replications. [default: 1]
  --isp=T                   Set number of algorithm instances to solve. [default: 1]
  --proc=Q                  Set number of parallel processes for the algorithm instances. [default: 1]
  --metric                  Set if metric computation is desired.
  --seed                    Set the random number seed with 6 spaced integers.
  --param                   Specify a solver-specific parameter <param> <val>.
  -h --help                 Show this screen.
  -v --version              Show version.

Examples:
  pymoso listitems
  pymoso solve ProbTPA RPERLE 4 14
  pymoso solve --budget=100000 --odir=test1  ProbTPB RMINRLE 3 12
  pymoso solve --seed 12345 32123 5322 2 9543 666666666 ProbTPC RPERLE 31 21 11
  pymoso solve --simpar=4 --param betaeps 0.4 ProbTPA RPERLE 30 30
  pymoso solve --param radius 3 ProbTPA RPERLE 45 45
  pymoso testsolve --isp=16 --proc=4 TPATester RPERLE
  pymoso testsolve --isp=20 --proc=10 --metric --crn TPBTester RMINRLE 9 9

Help:
  Use the listitems command to view a list of available solvers, problems, and
  test problems.
"""
VERSION = "test"


def parse(argv):
    """Call docopt directly (no subprocess), returning the options dict."""
    return docopt(DOC, argv=argv, version=VERSION)


# ---------------------------------------------------------------------------
# The 8 literal "Examples:" lines above -- argument-structure-level check
# only (does the parser accept the shape); actually running these lives in
# tests/test_cli.py.
# ---------------------------------------------------------------------------
README_EXAMPLES = {
    "listitems": ["listitems"],
    "solve_basic": ["solve", "ProbTPA", "RPERLE", "4", "14"],
    "solve_budget_odir": ["solve", "--budget=100000", "--odir=test1", "ProbTPB", "RMINRLE", "3", "12"],
    "solve_seed": ["solve", "--seed", "12345", "32123", "5322", "2", "9543", "666666666",
                   "ProbTPC", "RPERLE", "31", "21", "11"],
    "solve_simpar_param": ["solve", "--simpar=4", "--param", "betaeps", "0.4", "ProbTPA", "RPERLE", "30", "30"],
    "solve_param": ["solve", "--param", "radius", "3", "ProbTPA", "RPERLE", "45", "45"],
    "testsolve_no_x": ["testsolve", "--isp=16", "--proc=4", "TPATester", "RPERLE"],
    "testsolve_full": ["testsolve", "--isp=20", "--proc=10", "--metric", "--crn", "TPBTester",
                       "RMINRLE", "9", "9"],
}


@pytest.mark.parametrize("name", sorted(README_EXAMPLES))
def test_readme_example_parses_with_docopt(name):
    argv = README_EXAMPLES[name]
    opts = parse(argv)
    assert opts[argv[0]] is True


# ---------------------------------------------------------------------------
# --seed: exactly 6 integers, as a single option group
# ---------------------------------------------------------------------------

def test_seed_with_six_values_parses():
    opts = parse(["solve", "--seed", "1", "2", "3", "4", "5", "6",
                  "ProbTPA", "RPERLE", "4", "14"])
    assert opts["<s>"] == ["1", "2", "3", "4", "5", "6"]
    assert opts["--seed"] is True


@pytest.mark.parametrize("n_values", [0, 1, 3])
def test_seed_with_too_few_values_is_rejected(n_values):
    """Too few tokens overall to satisfy --seed's fixed 6-slot group plus
    the required <problem> <solver> <x>... that follow -- docopt can't
    find any satisfying assignment, so this really is rejected."""
    seed_vals = [str(i) for i in range(1, n_values + 1)]
    with pytest.raises(SystemExit) as exc_info:
        parse(["solve", "--seed"] + seed_vals + ["ProbTPA", "RPERLE", "4", "14"])
    assert "Usage:" in exc_info.value.code


@pytest.mark.parametrize("n_values,expected_s,expected_rest", [
    # 5 seed values + 4 trailing tokens = 9 total, exactly the minimum
    # (6 for <s> + 1 <problem> + 1 <solver> + 1 <x>) -- docopt does NOT
    # reject this for being short one seed value. It silently borrows
    # the next token ('ProbTPA') to fill <s> to 6, then reassigns
    # everything after that by position, with no semantic check at all.
    (5, ["1", "2", "3", "4", "5", "ProbTPA"], {"<problem>": "RPERLE", "<solver>": "4", "<x>": ["14"]}),
    # 7 seed values: <s> still only ever takes exactly 6 (the first 6
    # tokens after --seed); the 7th value and everything meant to be
    # <problem>/<solver>/<x> silently shift down by one slot instead of
    # being rejected as "too many seed values".
    (7, ["1", "2", "3", "4", "5", "6"], {"<problem>": "7", "<solver>": "ProbTPA", "<x>": ["RPERLE", "4", "14"]}),
    (8, ["1", "2", "3", "4", "5", "6"], {"<problem>": "7", "<solver>": "8", "<x>": ["ProbTPA", "RPERLE", "4", "14"]}),
])
def test_seed_with_5_or_more_than_6_values_silently_misparses(n_values, expected_s, expected_rest):
    """This is not a rejection at all -- '--seed' with the wrong count
    (as long as enough total tokens remain) is silently accepted with
    <s>, <problem>, <solver>, and <x> all holding tokens the user did not
    intend for them, and no error of any kind."""
    seed_vals = [str(i) for i in range(1, n_values + 1)]
    opts = parse(["solve", "--seed"] + seed_vals + ["ProbTPA", "RPERLE", "4", "14"])
    assert opts["<s>"] == expected_s
    for key, val in expected_rest.items():
        assert opts[key] == val


# ---------------------------------------------------------------------------
# --param: repeatable, each occurrence takes exactly 2 values
# ---------------------------------------------------------------------------

def test_single_param_parses():
    opts = parse(["solve", "--param", "radius", "3", "ProbTPA", "RPERLE", "45", "45"])
    assert opts["<param>"] == ["radius"]
    assert opts["<val>"] == ["3"]


def test_repeated_param_parses():
    """From the README's "any number of options" example."""
    opts = parse([
        "solve", "--crn", "--simpar=4", "--budget=10000",
        "--seed", "1", "2", "3", "4", "5", "6", "--odir=Exp1",
        "--param", "mconst", "4", "--param", "betadel", "0.7",
        "ProbTPA", "RPERLE", "97", "97",
    ])
    assert opts["<param>"] == ["mconst", "betadel"]
    assert opts["<val>"] == ["4", "0.7"]
    assert opts["--param"] == 2  # docopt's [...] repeat count
    assert opts["<x>"] == ["97", "97"]


def test_param_missing_second_value_silently_misparses():
    """Same fragility as --seed above: --param's group is a fixed 2-slot
    repeat, not a validated (name, value) pair tied to that specific
    --param occurrence. Omitting the value does not raise -- it borrows
    the next token ('ProbTPA') as the value and shifts everything after
    it down by one slot."""
    opts = parse(["solve", "--param", "radius", "ProbTPA", "RPERLE", "45", "45"])
    assert opts["<param>"] == ["radius"]
    assert opts["<val>"] == ["ProbTPA"]
    assert opts["<problem>"] == "RPERLE"
    assert opts["<solver>"] == "45"
    assert opts["<x>"] == ["45"]


# ---------------------------------------------------------------------------
# <x>: one or more components for solve; zero or more for testsolve
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("x", [["4"], ["4", "14"], ["31", "21", "11"]])
def test_solve_multiple_x_components(x):
    opts = parse(["solve", "ProbTPA", "RPERLE"] + x)
    assert opts["<x>"] == x


def test_solve_requires_at_least_one_x():
    with pytest.raises(SystemExit):
        parse(["solve", "ProbTPA", "RPERLE"])


def test_testsolve_x_is_optional():
    opts = parse(["testsolve", "TPATester", "RPERLE"])
    assert opts["<x>"] == []


def test_testsolve_x_may_be_given():
    opts = parse(["testsolve", "TPBTester", "RMINRLE", "9", "9"])
    assert opts["<x>"] == ["9", "9"]


# ---------------------------------------------------------------------------
# --help / --version, and malformed invocations: SystemExit shape only
# (exit codes and stream routing are a live-CLI concern, in test_cli.py)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("flag", ["--help", "-h"])
def test_help_raises_systemexit_with_no_message(flag):
    """docopt's own -h/--help handling prints the doc itself, then calls
    a bare sys.exit() (code None) -- distinct from a parse-error
    SystemExit, whose code is the usage string."""
    with pytest.raises(SystemExit) as exc_info:
        parse([flag])
    assert exc_info.value.code is None


@pytest.mark.parametrize("flag", ["--version", "-v"])
def test_version_raises_systemexit_with_no_message(flag):
    with pytest.raises(SystemExit) as exc_info:
        parse([flag])
    assert exc_info.value.code is None


@pytest.mark.parametrize("argv", [
    [],
    ["solve"],
    ["solve", "ProbTPA"],
    ["solve", "ProbTPA", "RPERLE"],
    ["testsolve"],
    ["frobnicate"],
], ids=["empty", "solve-bare", "solve-1arg", "solve-no-x", "testsolve-bare", "unknown-command"])
def test_malformed_invocation_raises_systemexit_with_usage(argv):
    with pytest.raises(SystemExit) as exc_info:
        parse(argv)
    assert "Usage:" in exc_info.value.code


def test_non_integer_budget_is_accepted_by_docopt():
    """docopt does not type-check option values at all -- '--budget' is
    just a string until commands/solve.py calls int() on it (which, at
    the time this was frozen, raised an unhandled ValueError with a raw
    traceback -- see test_cli.py for the live behavior)."""
    opts = parse(["solve", "--budget=abc", "ProbTPA", "RPERLE", "4", "14"])
    assert opts["--budget"] == "abc"


def test_negative_budget_is_accepted_by_docopt():
    """Unlike the bare int() crash above, a *valid* integer that is
    non-positive was, at the time this was frozen, caught cleanly by
    basecomm.validate_positive_int (commit 0fa6804) -- not by docopt
    itself, which places no bound on the value at all."""
    opts = parse(["solve", "--budget=-5", "ProbTPA", "RPERLE", "4", "14"])
    assert opts["--budget"] == "-5"


# ---------------------------------------------------------------------------
# Surprising docopt permissiveness / fragility, worth documenting exactly
# because the README's own prose claims otherwise.
# ---------------------------------------------------------------------------

def test_options_after_positional_args_are_currently_accepted():
    """The README states (prose, "Finally, users may specify..."): options
    must come before the problem argument. That is not actually enforced:
    an option placed after <problem>/<solver>/<x> is parsed identically
    to one placed before them."""
    opts_before = parse(["solve", "--budget=500", "ProbTPA", "RPERLE", "4", "14"])
    opts_after = parse(["solve", "ProbTPA", "RPERLE", "4", "14", "--budget=500"])
    assert opts_before["--budget"] == opts_after["--budget"] == "500"
    assert opts_before["<x>"] == opts_after["<x>"] == ["4", "14"]


def test_param_option_after_other_options_is_currently_accepted():
    """The README also states --param must be the last option. Also not
    actually enforced: another option placed after --param's pair still
    parses correctly here."""
    opts = parse(["solve", "--param", "radius", "3", "--budget=500",
                  "ProbTPA", "RPERLE", "45", "45"])
    assert opts["<param>"] == ["radius"]
    assert opts["<val>"] == ["3"]
    assert opts["--budget"] == "500"


def test_seed_and_param_interleaved_out_of_order_silently_misparses():
    """This is the real fragility the README's ordering advice is
    presumably trying to prevent: when a --param group precedes a --seed
    group (an order not shown in any example), docopt's greedy matching
    does not reject the input -- it silently assigns the wrong tokens to
    the wrong slots. This is not a rejection at all, and is worse than
    one: <param>/<val>/<s> end up holding the wrong tokens with no error
    raised (in this particular case <problem>/<solver> still happen to
    land correctly, by luck of the token count -- a different
    interleaving can misassign those too).
    """
    opts = parse([
        "solve", "--param", "radius", "3", "--seed",
        "1", "2", "3", "4", "5", "6", "ProbTPA", "RPERLE", "4", "14",
    ])
    # docopt vacuums 'radius' and '3' into <s> instead of <param>/<val>,
    # even though <problem>/<solver> happen to still land correctly here.
    assert opts["<s>"] == ["radius", "3", "1", "2", "3", "4"]
    assert opts["<param>"] == ["5"]
    assert opts["<val>"] == ["6"]
    assert opts["<problem>"] == "ProbTPA"
