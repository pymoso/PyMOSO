"""
Layer 2 (making the README's executable content testable): every
`pymoso ...` invocation shown in the README, parsed from the README
text itself (not transcribed by hand) so a newly-added example is
picked up automatically, run with a small budget/isp/proc and asserted
to exit 0.

This checks invocability only -- that the command parses and the run
completes without error -- not correctness of the result. This file
would not notice a wrong answer. tests/test_golden.py's end-seed
baselines cover a narrower and different property for the 8 (of 20+)
examples they happen to overlap with: that the reported run lands on
the same stream-allocation schedule position as before, not that the
computed solution/objective values are correct -- see
docs/end-seed-scope.md for why those are different claims. Most of the
examples here have no correctness check of any kind today.

Parsing rule: a "real" example is a line (whether a bare fenced-block
line or a single-backtick inline code span) that, once any markdown
wrapping is stripped, starts with `pymoso ` and contains none of
`<`, `[`, or `...` -- which excludes the abstract Usage: template
(placeholders) while keeping every concrete invocation, in the help
text's own Examples: section and in prose. A command whose backtick
span ends in a backslash is joined with the next one (the README's two
line-continuation examples).

Unlike the equivalent file on the earlier fork, --simpar examples are
NOT marked xfail here: --simpar works on this base (917bf06, upstream,
unrelated to and predating this migration -- see
docs/upstream-simpar.md, KNOWN_ISSUES.md issue 2), confirmed directly
below rather than assumed from the diff.

Fixed by Layer 3 (next commit after this file was first written): a
bare `content == "pymoso"` branch used to also match a line that is
literally just the word "pymoso" -- which Layer 3's regenerated --help
text now contains (argparse's top-level description, cli.py's own
docstring first line), extracting a bogus zero-argument "pymoso"
example that naturally fails ("the following arguments are required:
<command>"). Removed; a bare "pymoso" was never a real invocation.
"""
import re
import shlex
import shutil
import subprocess
import sys
import multiprocessing

_NON_FORK = multiprocessing.get_start_method() != "fork"

import pytest

from _pymoso_cli import pymoso_argv

pytestmark = pytest.mark.timeout(90)

README = open("README.md", encoding="utf-8").read()


def extract_cli_examples(readme_text):
    """Parse every concrete `pymoso ...` invocation out of the README
    text, joining backslash-continued lines. Returns a de-duplicated
    list preserving first-seen order."""
    candidates = []
    pending = None
    for raw in readme_text.splitlines():
        line = raw.strip()
        m = re.match(r"^`(.*)`$", line)
        content = (m.group(1) if m else line).rstrip()
        if pending is not None:
            pending = pending[:-1].rstrip() + " " + content.lstrip()
            if pending.endswith("\\"):
                continue
            candidates.append(pending)
            pending = None
            continue
        if content.startswith("pymoso "):
            if "<" in content or "[" in content or "..." in content or " | " in content:
                continue
            if content.endswith("\\"):
                pending = content
                continue
            candidates.append(content)
    seen = set()
    deduped = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            deduped.append(c)
    return deduped


CLI_EXAMPLES = extract_cli_examples(README)
assert len(CLI_EXAMPLES) >= 20, f"expected at least 20 CLI examples, parsed {len(CLI_EXAMPLES)}"

SIMPAR_EXAMPLES = [c for c in CLI_EXAMPLES if "--simpar" in c]
assert SIMPAR_EXAMPLES, "expected at least one --simpar example"


def _prepare_argv(cmd, small_budget=200, small_isp=2, small_proc=2):
    """Parse a command string into argv (without 'pymoso'), replacing
    any --budget/--isp/--proc with small values so the test suite stays
    fast; solve/testsolve without an explicit --budget get one added.
    This is exactly the "run with a small budget" adjustment -- it does
    not change which options are present, only their values.
    """
    argv = shlex.split(cmd)[1:]
    subcommand = argv[0] if argv else None
    out = []
    has_budget = False
    skip_next = False
    for tok in argv:
        if skip_next:
            skip_next = False
            continue
        if tok.startswith("--budget="):
            out.append(f"--budget={small_budget}")
            has_budget = True
        elif tok == "--budget":
            out.append(f"--budget={small_budget}")
            has_budget = True
            skip_next = True
        elif tok.startswith("--isp="):
            out.append(f"--isp={small_isp}")
        elif tok.startswith("--proc="):
            out.append(f"--proc={small_proc}")
        else:
            out.append(tok)
    if subcommand in ("solve", "testsolve") and not has_budget:
        out = [out[0], f"--budget={small_budget}"] + out[1:]
    return out


def _run_example(cmd, tmp_path):
    argv = _prepare_argv(cmd)
    if any("myproblem.py" in a or "mytester.py" in a for a in argv):
        shutil.copy("pymoso/examples/myproblem.py", tmp_path)
        shutil.copy("pymoso/examples/mytester.py", tmp_path)
    return subprocess.run(pymoso_argv(["pymoso"] + argv), cwd=tmp_path, capture_output=True, text=True, timeout=60)


@pytest.mark.parametrize("cmd", CLI_EXAMPLES, ids=range(len(CLI_EXAMPLES)))
def test_readme_cli_example_is_invocable(cmd, tmp_path):
    # KNOWN_ISSUES.md issue 7: testsolve()'s --proc path ships a live,
    # already-seeded Oracle instance per job, not a class reference, so
    # the --simpar source-bundle transport fix doesn't cover it -- it
    # still hangs on Python 3.14+ (forkserver) for a dynamically-loaded
    # file. chnutils.par_runs uses multiprocessing.Pool unconditionally
    # (not gated behind --proc > 1), so this isn't limited to examples
    # that spell out --proc: confirmed directly, two examples with no
    # --proc at all (just `testsolve ... mytester.py RPERLE`, relying
    # on the default) also hang on 3.14 during a real matrix run, not
    # just the one that says --proc=20. Checked before running, not
    # after timing out at 60s. See
    # tests/test_multifile_transport.py::test_multifile_problem_under_proc_matches_serial,
    # which reproduces this exact gap on demand.
    if "testsolve" in cmd and (".py" in cmd) and _NON_FORK:
        pytest.xfail(
            "KNOWN_ISSUES.md issue 7: testsolve() + a dynamically-loaded "
            "file hangs on Python 3.14+ (forkserver), regardless of --proc "
            "-- see "
            "tests/test_multifile_transport.py::test_multifile_problem_under_proc_matches_serial"
        )
    proc = _run_example(cmd, tmp_path)
    assert proc.returncode == 0, (cmd, proc.stdout, proc.stderr)


@pytest.mark.parametrize("cmd", SIMPAR_EXAMPLES, ids=range(len(SIMPAR_EXAMPLES)))
def test_simpar_examples_specifically_confirmed_to_succeed(cmd, tmp_path):
    """Redundant with test_readme_cli_example_is_invocable above for
    these same commands, but explicit: these are the exact examples the
    earlier fork's equivalent test had to xfail (KNOWN_ISSUES.md issue
    2). If --simpar ever regresses, this fails with the specific old
    signature named below, not just a generic "not zero" failure."""
    proc = _run_example(cmd, tmp_path)
    assert proc.returncode == 0, (cmd, proc.stdout, proc.stderr)
    assert "get_next_prnstream() missing 1 required positional argument" not in proc.stdout
