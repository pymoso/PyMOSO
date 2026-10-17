"""
Per-call cost of Oracle.hit() and of the stream operations under it.

Companion to docs/bench_parallel_dispatch.py: that script times whole
--simpar/--proc runs; this one times a single hit() call in one process,
with a g() that does no work, so what is left is the framework's own
coordinate cost. Results are recorded in docs/hit-cost-baseline.md.

    python docs/bench_hit_cost.py [mrg32k3a|mrg31k3p]

Absolute timings, machine-dependent, not enforced by the test suite.
"""
import sys
import time

from pymoso.chnbase import Oracle
from pymoso.prng import mrg31k3p, mrg32k3a

GENERATORS = {'mrg32k3a': (mrg32k3a, mrg32k3a.MRG32k3a), 'mrg31k3p': (mrg31k3p, mrg31k3p.MRG31k3p)}
ROOT = mrg32k3a.DEFAULT_SEED    # the same for both
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


def fresh_oracle(crn, stream_class):
    orc = FreeOracle(stream_class(ROOT))
    orc.set_crnflag(crn)
    orc.simpar = 1
    for _ in range(ITERATION):
        orc._advance_iteration()
    return orc


def main(repeats=2000, hit_repeats=500, replication_counts=(1, 8, 64), generator='mrg32k3a'):
    """The published measurement by default. The arguments exist so that
    tests/test_benchmark_scripts.py can run a trivial one and prove this
    script still works; they are not timing knobs."""
    M, stream_class = GENERATORS[generator]
    rows = []
    stream = M.stream_at(ROOT, ITERATION, 0)
    rows.append(('stream_at(root, stream, 0)', per_call_us(lambda: M.stream_at(ROOT, ITERATION, 0), repeats)))
    rows.append(('stream_at(root, stream, point offset)', per_call_us(lambda: M.stream_at(ROOT, ITERATION, 12345 << 52), repeats)))
    # Added in Phase 7 step 3: a point code filling its 75-bit field,
    # the longest offset the default branch makes.
    rows.append(('stream_at(root, stream, 75-bit point offset)',
                 per_call_us(lambda: M.stream_at(ROOT, ITERATION, ((1 << 74) | 0x123456789abcdef) << 52), repeats)))
    rows.append(('Stream.advance(REPL_STRIDE)', per_call_us(lambda: stream.advance(M.REPL_STRIDE), repeats)))
    rows.append(('Stream.advance(REPL_RESERVE_STRIDE)', per_call_us(lambda: stream.advance(M.REPL_RESERVE_STRIDE), repeats)))
    for crn in (True, False):
        for m in replication_counts:
            orc = fresh_oracle(crn, stream_class)
            label = 'hit(x, m={0}), crn={1}'.format(m, crn)
            rows.append((label, per_call_us(lambda: orc.hit((3,), m), hit_repeats)))
    print('Python {0}, {1}'.format(sys.version.split()[0], generator))
    print('| operation | microseconds per call |')
    print('|---|---|')
    for label, us in rows:
        print('| `{0}` | {1:,.0f} |'.format(label, us))


if __name__ == '__main__':
    main(generator=sys.argv[1] if len(sys.argv) > 1 else 'mrg32k3a')
