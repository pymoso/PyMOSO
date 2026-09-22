#!/usr/bin/env python
"""One-off script: regenerate README.md's Layer-1 code blocks from
pymoso/examples/ files, per the approved fragment conventions. Run once
from the repo root; not part of the permanent test suite."""
import inspect
import re
import sys

sys.path.insert(0, "pymoso/examples")

README_PATH = "README.md"


def read_file(name):
    with open(f"pymoso/examples/{name}", encoding="utf-8") as f:
        return f.read()


def split_marked_sections(text):
    body = text.split('"""', 2)[2]
    parts = re.split(r"^##### .*\n", body, flags=re.MULTILINE)
    return [p.strip("\n") + "\n" for p in parts if p.strip("\n")]


import metric_example1
import metric_example2

readme = open(README_PATH, encoding="utf-8").read()
pattern = re.compile(r"```python\n(.*?)```", re.DOTALL)
blocks = pattern.findall(readme)
assert len(blocks) == 20, len(blocks)

solve_ex = read_file("solve_example.py")
solve_body = solve_ex.split('"""', 2)[2].lstrip("\n")
sp = solve_body.index("# example for specifying budget and seed")
solve_part1 = solve_body[:sp].rstrip("\n") + "\n"
solve_part2 = solve_body[sp:]

testsolve_ex = read_file("testsolve_example.py")
testsolve_body = testsolve_ex.split('"""', 2)[2].lstrip("\n")
tp = testsolve_body.index("iter5_soln =")
testsolve_part1 = testsolve_body[:tp].rstrip("\n") + "\n"
testsolve_part2 = testsolve_body[tp:]

algo_sections = split_marked_sections(read_file("algorithm_snippets.py"))
assert len(algo_sections) == 7, len(algo_sections)

new_blocks = list(blocks)
new_blocks[0] = read_file("myproblem.py")
new_blocks[1] = read_file("mytester.py")
# 2, 3 unchanged (C wrapper examples)
new_blocks[4] = inspect.getsource(metric_example1.metric)
new_blocks[5] = inspect.getsource(metric_example2.metric)
new_blocks[6] = read_file("myaccel.py")
new_blocks[7] = read_file("myraalg.py")
new_blocks[8] = read_file("mymosoalg.py")
for i in range(9, 16):
    new_blocks[i] = algo_sections[i - 9]
new_blocks[16] = solve_part1
new_blocks[17] = solve_part2
new_blocks[18] = testsolve_part1
new_blocks[19] = testsolve_part2

# rebuild the README by replacing each block in order
out = []
last_end = 0
for i, m in enumerate(pattern.finditer(readme)):
    out.append(readme[last_end:m.start()])
    out.append("```python\n" + new_blocks[i] + "```")
    last_end = m.end()
out.append(readme[last_end:])
new_readme = "".join(out)

with open(README_PATH, "w", encoding="utf-8") as f:
    f.write(new_readme)

print("README.md regenerated.")
