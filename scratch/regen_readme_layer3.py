#!/usr/bin/env python
"""One-off script: regenerate README.md's two plain (non-python) fenced
blocks -- CLI help and listitems output -- from live `pymoso` output.
Not part of the permanent test suite; see tests/test_readme_help_text.py
for the ongoing check."""
import re
import subprocess

README_PATH = "README.md"

HELP_COMMANDS = [
    ["pymoso", "--help"],
    ["pymoso", "solve", "--help"],
    ["pymoso", "testsolve", "--help"],
    ["pymoso", "listitems", "--help"],
]


def run(argv):
    proc = subprocess.run(argv, capture_output=True, text=True)
    assert proc.returncode == 0, (argv, proc.stderr)
    return proc.stdout.rstrip("\n")


def build_help_block():
    parts = []
    for argv in HELP_COMMANDS:
        parts.append(f"$ {' '.join(argv)}\n{run(argv)}")
    return "\n\n".join(parts) + "\n"


def build_listitems_block():
    return run(["pymoso", "listitems"]) + "\n"


readme = open(README_PATH, encoding="utf-8").read()
lines = readme.split("\n")

# sequential fence scan: pair each opening fence line with the next
# closing "```" line, tracking whether the opening was plain ``` or
# ```python -- a regex alone can't tell a python block's closing ```
# apart from a plain block's opening ```.
plain_spans = []  # list of (start_index, end_index) line indices, inclusive of fence lines
i = 0
while i < len(lines):
    line = lines[i]
    if line == "```" or line == "```python":
        is_plain = line == "```"
        start = i
        j = i + 1
        while j < len(lines) and lines[j] != "```":
            j += 1
        if is_plain:
            plain_spans.append((start, j))
        i = j + 1
    else:
        i += 1

assert len(plain_spans) == 2, f"expected exactly 2 plain fenced blocks, found {len(plain_spans)}"

help_block = build_help_block()
listitems_block = build_listitems_block()

(h_start, h_end), (l_start, l_end) = plain_spans
new_lines = (
    lines[: h_start + 1]
    + help_block.rstrip("\n").split("\n")
    + lines[h_end : l_start + 1]
    + listitems_block.rstrip("\n").split("\n")
    + lines[l_end:]
)
new_readme = "\n".join(new_lines)

with open(README_PATH, "w", encoding="utf-8") as f:
    f.write(new_readme)

print("README.md CLI help / listitems blocks regenerated.")
