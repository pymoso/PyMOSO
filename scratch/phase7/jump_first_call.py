"""Phase 7 step 3: what a fresh process pays for the lazily built power
tables. Each measurement is a new interpreter (as a worker is under
forkserver and spawn): import the generator, then time the first
stream_at(root, 20, 0) (builds both tables to 132 bits), a second one,
and the first and second hit()-shaped advance by a 75-bit point offset.

    python scratch/phase7/jump_first_call.py GENERATOR [PROCESSES]
"""
import json
import subprocess
import sys

CHILD = '''
import time
t0 = time.perf_counter()
from pymoso.prng import {0} as mod
t1 = time.perf_counter()
root = mod.DEFAULT_SEED
a = time.perf_counter(); s = mod.stream_at(root, 20, 0); b = time.perf_counter()
mod.stream_at(root, 21, 0); c = time.perf_counter()
off = ((1 << 74) | 0x123456789abcdef) << 52
s.advance(off); d = time.perf_counter()
s.advance(off + (1 << 52)); e = time.perf_counter()
print(1e6 * (t1 - t0), 1e6 * (b - a), 1e6 * (c - b), 1e6 * (d - c), 1e6 * (e - d), len(mod._powers1.powers))
'''

gen = sys.argv[1]
n = int(sys.argv[2]) if len(sys.argv) > 2 else 15
rows = []
for _ in range(n):
    out = subprocess.run([sys.executable, '-c', CHILD.format(gen)], capture_output=True, text=True, check=True).stdout.split()
    rows.append([float(v) for v in out])
med = lambda i: sorted(r[i] for r in rows)[len(rows) // 2]
print(json.dumps(dict(python=sys.version.split()[0], generator=gen, processes=n,
                      import_us=med(0), first_stream_at_us=med(1), second_stream_at_us=med(2),
                      first_offset_advance_us=med(3), second_offset_advance_us=med(4),
                      table_length_after=int(rows[0][5]))))
