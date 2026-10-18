"""Phase 7: what R-SPLINE's x0 re-estimation (commit 00c3dea, reverted)
did, measured against R-SPLINE without it.

    python scratch/phase7/rspline_x0_measure.py > OUT.txt

`WithX0` is that commit's spsolve, verbatim apart from the class. The
problems, starts and seeds are docs/bench_ne_quadratic.py's (20 seeds,
starts drawn by each problem's tester, budget 5,000). Quality is the gap
between the true first objective of the solution and the problem's true
minimum, at the last RA iteration at or under each count of
simulations. Counted, not timed.
"""
import contextlib
import io
import itertools
import os
import random
import statistics
import types

from pymoso.chnbase import _check_warm_start
from pymoso.layout import get_solv_prnstreams
from pymoso.paths import isp_run
from pymoso.prng import mrg32k3a
from pymoso.problems.probsimpleso import ProbSimpleSO
from pymoso.problems.probtpa import ProbTPA
from pymoso.problems.probtpb import ProbTPB
from pymoso.problems.probtpc import ProbTPC
from pymoso.solvers.rspline import RSPLINE
from pymoso.testers import simplesotester, tpatester, tpbtester, tpctester

# The same problems, feasible boxes, seeds and starts as
# docs/bench_ne_quadratic.py (Phase 7 step 4), stated here so this
# script stands alone.
PROBLEMS = {
    'ProbSimpleSO': (ProbSimpleSO, simplesotester, [range(-100, 101)]),
    'ProbTPA': (ProbTPA, tpatester, [range(0, 51)] * 2),
    'ProbTPB': (ProbTPB, tpbtester, [range(0, 101)] * 2),
    'ProbTPC': (ProbTPC, tpctester, [range(-10, 11)] * 3),
}


def seed_for(rep):
    return (1000 + rep,) * 6


def x0_for(problem, rep):
    return PROBLEMS[problem][1].get_ranx0(random.Random(rep))


def true_first_min(problem):
    _, tester, box = PROBLEMS[problem]
    return min(tester.true_g(x)[0] for x in itertools.product(*box))


bench = types.SimpleNamespace(PROBLEMS=PROBLEMS, seed_for=seed_for, x0_for=x0_for, true_first_min=true_first_min)


class WithX0(RSPLINE):
    def spsolve(self, warm_start):
        candidate = next(iter(warm_start))
        candidates = {candidate, self.x0}
        feasible = self.upsample(candidates)
        _check_warm_start(self, candidates)
        if not feasible:
            raise ValueError(
                'x0={0} is infeasible. RA solvers require a feasible starting point.'.format(self.x0)
            )
        ws = candidate
        if self.gbar[self.x0][0] < self.gbar[ws][0]:
            ws = self.x0
        _, xmin, _, _ = self.spline(ws)
        return {xmin}


def runs(solver, prob, reps=20, budget=5000, record=None):
    cls, tester, _ = bench.PROBLEMS[prob]
    out = []
    for rep in range(reps):
        orcstream, solvstream = get_solv_prnstreams(bench.seed_for(rep), mrg32k3a)
        orc = cls(orcstream)
        orc.set_crnflag(False)
        with contextlib.redirect_stdout(io.StringIO()), orc.set_simpar(1):
            out.append(isp_run(solver, budget, orc, solvprn=solvstream, x0=bench.x0_for(prob, rep)))
    return out


def gaps(results, prob, fmin, checkpoints=(1000, 2500, 5000)):
    tester = bench.PROBLEMS[prob][1]
    g = {c: [] for c in checkpoints}
    for r in results:
        it = sorted(r['itersoln'])
        for c in checkpoints:
            done = [k for k in it if r['simcalls'][k] <= c and k > 0]
            g[c].append(min(tester.true_g(x)[0] for x in r['itersoln'][done[-1]]) - fmin)
    return g


def main():
    print('load average', os.getloadavg())
    print('\nGap to the true minimum of the first objective (median of 20 seeds), and by seed with x0 '
          're-estimation against without: better / same / worse')
    for prob in ('ProbTPA', 'ProbTPB', 'ProbTPC', 'ProbSimpleSO'):
        fmin = bench.true_first_min(prob)
        a = gaps(runs(WithX0, prob), prob, fmin)
        b = gaps(runs(RSPLINE, prob), prob, fmin)
        for c in a:
            print('{0:12s} at {1:5d}: with {2:6.2f}  without {3:6.2f}  {4}/{5}/{6}'.format(
                prob, c, statistics.median(a[c]), statistics.median(b[c]),
                sum(x < y for x, y in zip(a[c], b[c])), sum(x == y for x, y in zip(a[c], b[c])),
                sum(x > y for x, y in zip(a[c], b[c]))))
    print('\nWith x0 re-estimation, iterations after the first: how often the search restarted from x0, '
          'and how often the warm start it gave up was truly better (by the tester\'s true first objective)')
    for prob in ('ProbTPA', 'ProbTPB', 'ProbTPC', 'ProbSimpleSO'):
        tester = bench.PROBLEMS[prob][1]
        rec = []

        class Spy(WithX0):
            def spsolve(self, warm_start):
                self._ws = next(iter(warm_start))
                return super().spsolve(warm_start)

            def spline(self, start, *a, **k):
                if self.nu > 1:
                    rec.append((self._ws == self.x0, start == self.x0 and self._ws != self.x0,
                                tester.true_g(self._ws)[0] < tester.true_g(self.x0)[0]))
                return super().spline(start, *a, **k)
        runs(Spy, prob)
        n = len(rec)
        diff = n - sum(r[0] for r in rec)
        chose = sum(r[1] for r in rec)
        wrong = sum(r[1] and r[2] for r in rec)
        print('{0:12s} iterations {1:4d}, warm start not x0 {2:4d}, restarted from x0 {3:4d} ({4:.0f}%), '
              'of which the warm start was truly better {5:4d} ({6:.0f}%)'.format(
                  prob, n, diff, chose, 100 * chose / diff if diff else 0, wrong, 100 * wrong / chose if chose else 0))
    print('load average', os.getloadavg())


if __name__ == '__main__':
    main()
