"""
Where a --simpar run's wall time goes, and what bounds its speedup.

Companion to docs/bench_parallel_dispatch.py (which times whole runs)
and docs/bench_hit_cost.py (which times one hit() call). This script
puts timers around the three things the parent process does during a
--simpar run -- turning coordinates into streams, sending jobs, and waiting for
results -- and separately computes the best speedup that parallelising
*within one hit() call* can give, from the run's own distribution of
replications per call. Results are recorded in docs/simpar-ceiling.md.

    python docs/bench_simpar_ceiling.py

Absolute timings, machine-dependent, and not enforced by the test
suite. tests/test_benchmark_scripts.py runs this script on a trivial
workload so that it keeps working; it checks no timings.
"""
import math
import sys
import time

from pymoso.chnutils import get_solv_prnstreams, isp_run
from pymoso.executor import SerialExecutor
from pymoso.prng import mrg32k3a as M
from pymoso.problems.probexpensive import ProbExpensiveHeavy, ProbExpensiveLight, ProbExpensiveModerate
from pymoso.solvers.rspline import RSPLINE

SEED = (12345,) * 6
X0 = (97,)
# Same tiers and budgets as docs/bench_parallel_dispatch.py's --simpar sweep.
TIERS = [("Light", ProbExpensiveLight, 500), ("Moderate", ProbExpensiveModerate, 200), ("Heavy", ProbExpensiveHeavy, 80)]
WORKERS = (2, 4, 6)


class Timer:
    def __init__(self):
        self.seconds = 0.0
        self.calls = 0

    def wrap(self, func):
        def timed(*args, **kwargs):
            start = time.perf_counter()
            try:
                return func(*args, **kwargs)
            finally:
                self.seconds += time.perf_counter() - start
                self.calls += 1
        return timed


def run(problem_cls, simpar, budget):
    jump, send, wait, sim = Timer(), Timer(), Timer(), Timer()
    replications_per_hit = []
    # Everything that turns a block's coordinate into streams -- the
    # jump from the root, the jump to the block's offset, the
    # per-replication advances -- happens in SerialExecutor.streams,
    # in the parent, for serial and --simpar runs alike.
    real_streams = SerialExecutor.streams
    SerialExecutor.streams = jump.wrap(real_streams)
    try:
        orcstream, solvstream = get_solv_prnstreams(SEED, M)
        orc = problem_cls(orcstream)
        orc.set_crnflag(False)
        orc.g = sim.wrap(orc.g)
        real_hit = orc.hit

        def hit(x, m, *args, **kwargs):
            replications_per_hit.append(m)
            return real_hit(x, m, *args, **kwargs)

        orc.hit = hit
        with orc.set_simpar(simpar):
            if simpar > 1:
                orc.req_q.put = send.wrap(orc.req_q.put)
                orc.res_q.get = wait.wrap(orc.res_q.get)
            start = time.perf_counter()
            isp_run(RSPLINE, budget, orc, sprn=solvstream, x0=X0)
            elapsed = time.perf_counter() - start
    finally:
        SerialExecutor.streams = real_streams
    return dict(elapsed=elapsed, jump=jump.seconds, send=send.seconds, wait=wait.seconds,
                sim=sim.seconds, sim_calls=sim.calls, per_hit=replications_per_hit)


def intra_hit_bound(per_hit, workers):
    """Best speedup of the simulation work alone if replications can only
    run in parallel with others from the same hit() call."""
    rounds = sum(math.ceil(m / workers) for m in per_hit)
    return sum(per_hit) / rounds


def main(tiers=None, workers=None):
    """The published measurement by default. The arguments exist so that
    tests/test_benchmark_scripts.py can run a trivial one and prove this
    script still works; they are not timing knobs."""
    tiers = TIERS if tiers is None else tiers
    workers = WORKERS if workers is None else workers
    print('Python {0}, mrg32k3a, RSPLINE'.format(sys.version.split()[0]))
    for label, problem_cls, budget in tiers:
        run(problem_cls, 1, budget)                      # warm-up
        serial = run(problem_cls, 1, budget)
        per_hit = serial['per_hit']
        reps = sum(per_hit)
        g_each = serial['sim'] / serial['sim_calls']
        print('\n{0}: {1} hit() calls, {2} replications ({3:.1f} per call), g() {4:.2f} ms each'.format(
            label, len(per_hit), reps, reps / len(per_hit), 1000 * g_each))
        print('  serial: {0:.3f}s total | g() {1:.3f}s | coordinates {2:.3f}s ({3:.0f}% of the run)'.format(
            serial['elapsed'], serial['sim'], serial['jump'], 100 * serial['jump'] / serial['elapsed']))
        for count in workers:
            par = run(problem_cls, count, budget)
            rounds = sum(math.ceil(m / count) for m in per_hit)
            bound_with_jump = serial['elapsed'] / (rounds * g_each + serial['jump'])
            print('  workers={0}: {1:.3f}s, {2:.2f}x | coordinates {3:.3f}s | queue sends {4:.4f}s | waiting {5:.3f}s'
                  ' | bound, intra-hit only: {6:.2f}x | bound, intra-hit + serial coordinates: {7:.2f}x'.format(
                      count, par['elapsed'], serial['elapsed'] / par['elapsed'], par['jump'], par['send'],
                      par['wait'], intra_hit_bound(per_hit, count), bound_with_jump))
        print('  infinite workers, intra-hit only: {0:.2f}x'.format(intra_hit_bound(per_hit, 10 ** 9)))


if __name__ == '__main__':
    main()
