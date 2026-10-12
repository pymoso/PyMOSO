"""
Per-call cost of Oracle.hit() and of the stream operations under it.

Companion to docs/bench_parallel_dispatch.py: that script times whole
--simpar/--proc runs; this one times a single hit() call in one process,
with a g() that does no work, so what is left is the framework's own
coordinate cost. Results are recorded in docs/hit-cost-baseline.md.

    python docs/bench_hit_cost.py

Absolute timings, machine-dependent, not enforced by the test suite.
"""
import sys
import time

from pymoso.chnbase import Oracle
from pymoso.prng import mrg32k3a as M

ROOT = M.DEFAULT_SEED
ITERATION = 7  # a mid-run RA iteration; stream_at's cost does not depend on it much


class FreeOracle(Oracle):
    """g() draws one value and does nothing else."""

    def __init__(self, rng):
        self.num_obj = 1
        self.dim = 1
        super().__init__(rng)

    def g(self, x, rng):
        return True, (rng.random(),)


def per_call_us(func, repeats):
    start = time.perf_counter()
    for _ in range(repeats):
        func()
    return (time.perf_counter() - start) / repeats * 1e6


def fresh_oracle(crn):
    orc = FreeOracle(M.MRG32k3a(ROOT))
    orc.set_crnflag(crn)
    orc.simpar = 1
    for _ in range(ITERATION):
        orc._advance_iteration()
    return orc


def main():
    rows = []
    stream = M.stream_at(ROOT, ITERATION, 0)
    rows.append(('stream_at(root, stream, 0)', per_call_us(lambda: M.stream_at(ROOT, ITERATION, 0), 2000)))
    rows.append(('stream_at(root, stream, point offset)', per_call_us(lambda: M.stream_at(ROOT, ITERATION, 12345 << 52), 2000)))
    rows.append(('Stream.advance(REPL_STRIDE)', per_call_us(lambda: stream.advance(M.REPL_STRIDE), 2000)))
    rows.append(('Stream.advance(REPL_RESERVE_STRIDE)', per_call_us(lambda: stream.advance(M.REPL_RESERVE_STRIDE), 2000)))
    for crn in (True, False):
        for m in (1, 8, 64):
            orc = fresh_oracle(crn)
            label = 'hit(x, m={0}), crn={1}'.format(m, crn)
            rows.append((label, per_call_us(lambda: orc.hit((3,), m), 500)))
    print('Python {0}, mrg32k3a'.format(sys.version.split()[0]))
    print('| operation | microseconds per call |')
    print('|---|---|')
    for label, us in rows:
        print('| `{0}` | {1:,.0f} |'.format(label, us))


if __name__ == '__main__':
    main()
