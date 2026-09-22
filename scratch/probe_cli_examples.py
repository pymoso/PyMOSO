import re
import shlex
import shutil
import subprocess
import tempfile
import os

readme = open('README.md', encoding='utf-8').read()
lines = readme.splitlines()

candidates = []
pending = None
for raw in lines:
    line = raw.strip()
    m = re.match(r'^`(.*)`$', line)
    content = m.group(1) if m else line
    content = content.rstrip()
    if pending is not None:
        pending = pending[:-1].rstrip() + ' ' + content.lstrip()
        if pending.endswith('\\'):
            continue
        candidates.append(pending)
        pending = None
        continue
    if content == 'pymoso' or content.startswith('pymoso '):
        if '<' in content or '[' in content or '...' in content or ' | ' in content:
            continue
        if content.endswith('\\'):
            pending = content
            continue
        candidates.append(content)

# dedupe, preserve order
seen = set()
deduped = []
for c in candidates:
    if c not in seen:
        seen.add(c)
        deduped.append(c)
candidates = deduped
print(f"{len(candidates)} unique candidates")

for cmd in candidates:
    argv = shlex.split(cmd)
    assert argv[0] == 'pymoso'
    argv = argv[1:]
    subcommand = argv[0]
    # inject/replace a small budget (solve/testsolve only)
    argv2 = []
    has_budget = False
    skip_next = False
    for i, tok in enumerate(argv):
        if skip_next:
            skip_next = False
            continue
        if tok.startswith('--budget='):
            argv2.append('--budget=200')
            has_budget = True
        elif tok == '--budget':
            argv2.append('--budget=200')
            has_budget = True
            skip_next = True
        elif tok.startswith('--isp='):
            argv2.append('--isp=2')
        elif tok.startswith('--proc='):
            argv2.append('--proc=2')
        else:
            argv2.append(tok)
    if subcommand in ('solve', 'testsolve') and not has_budget:
        argv2 = [argv2[0]] + ['--budget=200'] + argv2[1:]

    with tempfile.TemporaryDirectory() as td:
        if any('mytester.py' in a for a in argv2) or any('myproblem.py' in a for a in argv2):
            shutil.copy('pymoso/examples/myproblem.py', td)
            shutil.copy('pymoso/examples/mytester.py', td)
        proc = subprocess.run(['pymoso'] + argv2, cwd=td, capture_output=True, text=True, timeout=60)
        status = 'PASS' if proc.returncode == 0 else f'FAIL(exit={proc.returncode})'
        print(f"{status:16} {cmd}")
        if proc.returncode != 0:
            print('    stdout tail:', proc.stdout[-200:].replace(chr(10), ' | '))
            print('    stderr tail:', proc.stderr[-200:].replace(chr(10), ' | '))
