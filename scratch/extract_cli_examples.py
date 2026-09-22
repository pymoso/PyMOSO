import re

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
        if '<' in content or '[' in content or '...' in content:
            continue
        if content.endswith('\\'):
            pending = content
            continue
        candidates.append(content)

for c in candidates:
    print(repr(c))
print(len(candidates))
