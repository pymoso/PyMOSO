"""
What bounds a --simpar run's speedup, and what batching across hit()
calls does to that bound.

Companion to docs/bench_parallel_dispatch.py (which times whole runs)
and docs/bench_hit_cost.py (which times one hit() call). For each
workload this script

- runs it serially once and records every call the solver makes to the
  executor: which solver routine made it, and how many replications of
  how many points it carried;
- computes from that record the best speedup the simulation work can
  get if replications may only run alongside others of the same hit()
  call ("intra-hit"), and if they may run alongside everything
  submitted with them ("batched");
- times the run under --simpar with batching on, and again with the
  solver's estimate_many() replaced by a one-point-at-a-time loop, so
  that what batching buys is measured and not only bounded.

Results are recorded in docs/simpar-ceiling.md.

    python docs/bench_simpar_ceiling.py

Absolute timings, machine-dependent, and not enforced by the test
suite. tests/test_benchmark_scripts.py runs this script on a trivial
workload so that it keeps working; it checks no timings.
"""
import math
import sys
import time

from pymoso.chnbase import RASolver, RLESolver
from pymoso.chnutils import get_solv_prnstreams, isp_run
from pymoso.executor import SerialExecutor
from pymoso.prng import mrg32k3a as M
from pymoso.problems.probexpensive import (
    ProbExpensiveBiHeavy, ProbExpensiveBiLight, ProbExpensiveBiModerate,
    ProbExpensiveHeavy, ProbExpensiveLight, ProbExpensiveModerate,
)
from pymoso.solvers.rperle import RPERLE
from pymoso.solvers.rspline import RSPLINE

SEED = (12345,) * 6
# (label, problem class, solver class, x0, budget). The first three are
# docs/bench_parallel_dispatch.py's --simpar sweep: one dimension, and
# so no batching to observe. The last three are the same cost tiers in
# two dimensions under a bi-objective solver, where there is.
TIERS = [
    ("Light, 1-D", ProbExpensiveLight, RSPLINE, (97,), 500),
    ("Moderate, 1-D", ProbExpensiveModerate, RSPLINE, (97,), 200),
    ("Heavy, 1-D", ProbExpensiveHeavy, RSPLINE, (97,), 80),
    ("Light, 2-D", ProbExpensiveBiLight, RPERLE, (30, 30), 3000),
    ("Moderate, 2-D", ProbExpensiveBiModerate, RPERLE, (30, 30), 1000),
    ("Heavy, 2-D", ProbExpensiveBiHeavy, RPERLE, (30, 30), 400),
]
WORKERS = (2, 4, 6, 12)

# Solver routines that reach the oracle, innermost first wins. The
# first three estimate a set of points before looking at any result;
# the last two choose each point from the previous result.
BATCHING_SITES = [("upsample", RASolver), ("pli", RASolver), ("get_ncn", RLESolver)]
SEQUENTIAL_SITES = [("ne", RASolver), ("spli", RASolver)]


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


class Patches:
    """Attribute replacements, undone on exit."""

    def __init__(self):
        self._undo = []

    def set(self, owner, name, value):
        self._undo.append((owner, name, getattr(owner, name)))
        setattr(owner, name, value)

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        for owner, name, value in reversed(self._undo):
            setattr(owner, name, value)
        return False


def one_at_a_time(self, points):
    """estimate_many as it would be without batching."""
    return [self.estimate(x) for x in points]


def solve(problem_cls, solver_cls, x0, budget, simpar):
    orcstream, solvstream = get_solv_prnstreams(SEED, M)
    orc = problem_cls(orcstream)
    orc.set_crnflag(False)
    start = time.perf_counter()
    with orc.set_simpar(simpar):
        isp_run(solver_cls, budget, orc, sprn=solvstream, x0=x0)
    return time.perf_counter() - start, orc


def run_serial(problem_cls, solver_cls, x0, budget):
    """One serial run with everything recorded.

    Returns the elapsed time, the time inside g() and inside the
    coordinate-to-stream step, and `calls`: one (site, [replications
    per point]) entry per executor call."""
    jump, sim = Timer(), Timer()
    calls = []
    sites = []
    with Patches() as patches:
        for name, cls in BATCHING_SITES + SEQUENTIAL_SITES:
            def tagged(self, *args, _real=getattr(cls, name), _name=name, **kwargs):
                sites.append(_name)
                try:
                    return _real(self, *args, **kwargs)
                finally:
                    sites.pop()
            patches.set(cls, name, tagged)
        real_run = SerialExecutor.run

        def run(self, blocks):
            calls.append((sites[-1] if sites else "other", [block.count for block in blocks]))
            return real_run(self, blocks)

        patches.set(SerialExecutor, "run", run)
        patches.set(SerialExecutor, "streams", jump.wrap(SerialExecutor.streams))
        patches.set(problem_cls, "g", sim.wrap(problem_cls.g))
        elapsed, _ = solve(problem_cls, solver_cls, x0, budget, 1)
    return dict(elapsed=elapsed, sim=sim.seconds, sim_calls=sim.calls, jump=jump.seconds, calls=calls)


def run_parallel(problem_cls, solver_cls, x0, budget, workers, batching):
    with Patches() as patches:
        if not batching:
            patches.set(RASolver, "estimate_many", one_at_a_time)
        elapsed, _ = solve(problem_cls, solver_cls, x0, budget, workers)
    return elapsed


def bound(groups, workers):
    """Best speedup of the simulation work alone if the replications of
    each group can run in parallel with each other and with nothing
    else: each group of n takes ceil(n / workers) replication-times."""
    total = sum(groups)
    return total / sum(math.ceil(n / workers) for n in groups)


def site_table(calls):
    """Per solver routine: executor calls, points per call, and its
    share of all replications."""
    total = sum(sum(counts) for _, counts in calls)
    rows = []
    for name in [n for n, _ in BATCHING_SITES + SEQUENTIAL_SITES] + ["other"]:
        mine = [counts for site, counts in calls if site == name]
        if not mine:
            continue
        points = [len(counts) for counts in mine]
        rows.append((name, len(mine), sum(points) / len(points), max(points),
                     100.0 * sum(sum(counts) for counts in mine) / total))
    return rows


def main(tiers=None, workers=None):
    """The published measurement by default. The arguments exist so that
    tests/test_benchmark_scripts.py can run a trivial one and prove this
    script still works; they are not timing knobs."""
    tiers = TIERS if tiers is None else tiers
    workers = WORKERS if workers is None else workers
    print('Python {0}, mrg32k3a'.format(sys.version.split()[0]))
    for label, problem_cls, solver_cls, x0, budget in tiers:
        run_serial(problem_cls, solver_cls, x0, budget)                      # warm-up
        serial = run_serial(problem_cls, solver_cls, x0, budget)
        calls = serial['calls']
        per_hit = [n for _, counts in calls for n in counts]
        per_call = [sum(counts) for _, counts in calls]
        reps = sum(per_hit)
        sequential = sum(sum(counts) for site, counts in calls if site in [n for n, _ in SEQUENTIAL_SITES])
        print('\n{0}: {1}, budget {2}'.format(label, solver_cls.__name__, budget))
        print('  {0} hit()s, {1} replications ({2:.1f} per hit); {3} executor calls ({4:.2f} points, {5:.1f} replications per call)'.format(
            len(per_hit), reps, reps / len(per_hit), len(calls), len(per_hit) / len(calls), reps / len(calls)))
        print('  serial: {0:.3f}s total | g() {1:.3f}s, {2:.2f} ms each | coordinates {3:.3f}s ({4:.0f}% of the run)'.format(
            serial['elapsed'], serial['sim'], 1000 * serial['sim'] / max(serial['sim_calls'], 1),
            serial['jump'], 100 * serial['jump'] / serial['elapsed']))
        print('  by solver routine:')
        for name, count, mean_points, max_points, share in site_table(calls):
            print('    {0:9s} {1:5d} calls | points per call: mean {2:5.2f}, max {3:3d} | {4:5.1f}% of replications'.format(
                name, count, mean_points, max_points, share))
        print('  replications that cannot be batched (ne + spli): {0:.1f}%'.format(100.0 * sequential / reps))
        for count in workers:
            unbatched = run_parallel(problem_cls, solver_cls, x0, budget, count, batching=False)
            batched = run_parallel(problem_cls, solver_cls, x0, budget, count, batching=True)
            print('  workers={0}: bound, intra-hit {1:.2f}x | bound, batched {2:.2f}x | observed, one point at a time {3:.3f}s, {4:.2f}x'
                  ' | observed, batched {5:.3f}s, {6:.2f}x'.format(
                      count, bound(per_hit, count), bound(per_call, count),
                      unbatched, serial['elapsed'] / unbatched, batched, serial['elapsed'] / batched))
        print('  infinite workers: bound, intra-hit {0:.2f}x | bound, batched {1:.2f}x'.format(
            bound(per_hit, 10 ** 9), bound(per_call, 10 ** 9)))


if __name__ == '__main__':
    main()
