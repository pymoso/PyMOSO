"""
Layer 3 (making the README's executable content testable): the CLI
help text and listitems output shown in the README are generated
output, not hand-written prose -- this test regenerates both from the
live `pymoso` command and fails with a readable diff if the README is
stale.

Since argparse splits help across the top-level parser and each
subcommand (there is no single combined screen the way docopt had),
the "CLI help" section shows all four -- `pymoso --help`,
`pymoso solve --help`, `pymoso testsolve --help`,
`pymoso listitems --help` -- concatenated in one fenced block, each
labeled with a `$ <command>` prompt line, in that order. The prompt
lines are generated as part of the expected output (build_expected_help_
block below), not stripped and diffed around separately, so the actual
comparison stays a single clean byte-comparison of the whole block.

Checked and confirmed: the README does not reproduce `pymoso --version`'s
literal output anywhere (the old docopt Usage/Options text just
mentioned the -v/--version flag exists, no version *string* was ever
embedded) -- nothing to generate or exclude for that here.

Note: this branch has not done the numpy-docstring conversion the
earlier fork did, so `pymoso listitems`' docstrings stay single-line
and its output stays a clean table -- unlike that fork, where the
conversion garbled this same output into a multi-line mess. Confirmed
directly (see the output this test's build_expected_listitems_block()
produces), not assumed.
"""
import difflib
import subprocess

from _pymoso_cli import CLI_TIMEOUT, pymoso_argv

HELP_COMMANDS = [
    ["pymoso", "--help"],
    ["pymoso", "solve", "--help"],
    ["pymoso", "testsolve", "--help"],
    ["pymoso", "listitems", "--help"],
]


def run(argv):
    proc = subprocess.run(pymoso_argv(argv), capture_output=True, text=True, timeout=CLI_TIMEOUT)
    assert proc.returncode == 0, (argv, proc.stderr)
    return proc.stdout.rstrip("\n")


def build_expected_help_block():
    parts = [f"$ {' '.join(argv)}\n{run(argv)}" for argv in HELP_COMMANDS]
    return "\n\n".join(parts)


def build_expected_listitems_block():
    return run(["pymoso", "listitems"])


def extract_plain_fenced_blocks(readme_text):
    """Sequentially scan for fenced blocks of any kind, pairing each
    opening fence with the next closing ``` line. A block is plain only
    if its opening fence carries no language tag. Fence lines may be
    indented, e.g. inside a list item. Returns the content of each plain
    block, in order."""
    lines = readme_text.split("\n")
    blocks = []
    i = 0
    while i < len(lines):
        fence = lines[i].strip()
        if fence.startswith("```"):
            is_plain = fence == "```"
            j = i + 1
            while j < len(lines) and lines[j].strip() != "```":
                j += 1
            if is_plain:
                blocks.append("\n".join(lines[i + 1 : j]))
            i = j + 1
        else:
            i += 1
    return blocks


def _assert_matches(actual, expected, label):
    if actual != expected:
        diff = "\n".join(difflib.unified_diff(
            expected.splitlines(), actual.splitlines(),
			fromfile=f"{label} (live pymoso output)",
			tofile=f"README.md ({label}, current)",
            lineterm="",
        ))
        raise AssertionError(f"README's {label} block is stale:\n{diff}")


def test_readme_cli_help_block_matches_live_output():
    readme = open("README.md", encoding="utf-8").read()
    blocks = extract_plain_fenced_blocks(readme)
    assert len(blocks) == 2, f"expected exactly 2 plain fenced blocks, found {len(blocks)}"
    help_block = blocks[0]
    _assert_matches(help_block, build_expected_help_block(), "CLI help")


def test_readme_listitems_block_matches_live_output():
    readme = open("README.md", encoding="utf-8").read()
    blocks = extract_plain_fenced_blocks(readme)
    assert len(blocks) == 2, f"expected exactly 2 plain fenced blocks, found {len(blocks)}"
    listitems_block = blocks[1]
    _assert_matches(listitems_block, build_expected_listitems_block(), "listitems")
