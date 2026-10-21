#!/usr/bin/env python
"""
Where R-PE's coverage error is smallest as betaeps varies
(docs/beta-sweep-reference.md, the reference figures for the current
code; docs/relaxation-sweep.md is the earlier, withdrawn study).

Written when the relaxation was se/m**beta, to compare that arithmetic
with the preprint's (Cooper, Hunter and Nagaraj, Optimization Online
2018/06/6649, section 3.2), se*m**(1/2 - beta): the two differ by
exactly 1/2 in beta. The code now computes the preprint's, so beta here
is the preprint's beta; the tables in docs/relaxation-sweep.md were run
before that fix, and their "shipped beta" is the old code's. The tables
in docs/beta-sweep-reference.md were run after it.

    python docs/bench_beta_sweep.py [runs] [proc] [crn]   # defaults 100, 6, 1

Runs use CRN by default, as the preprint's do (its listings say "with
CRN"; PyMOSO's default is without). Without CRN, R-PE's coverage error
on TA at this budget is about 4 at every beta, against 0.41 at best
with CRN, so a sweep without it does not reproduce the
experiment; pass 0 as the third argument to see that.

Every beta value uses the same seed, so each run sees the same random
starting point and, because streams are coordinate-derived, the same
random numbers at every (point, iteration) -- the paper's "CRN across
the beta values". The metric is the tester's: the Hausdorff distance
from the true images of the run's final solution to the true efficient
set (TA), or the least such distance over the local efficient sets
(TC); the preprint's Figures 10 and 12, left panels, at
t = 0.4 x 10^6. Counted results only; the elapsed time printed at the
end is for planning the next run, not a finding.
"""
import json
import sys
import time

from pymoso.chnutils import testsolve
from pymoso.solvers.rpe import RPE
from pymoso.testers.tpatester import TPATester
from pymoso.testers.tpctester import TPCTester

BETAS = tuple(round(0.1 + 0.1 * i, 1) for i in range(15))        # 0.1 .. 1.5, the published axis
TESTERS = (('TA', TPATester), ('TC', TPCTester))
BUDGET = 400000
SEED = (12345,) * 6


def sweep(runs=100, proc=6, budget=BUDGET, betas=BETAS, testers=TESTERS, crn=True):
    """{problem: {beta: [metric of each run, in path order]}}"""
    out = {}
    for name, tester in testers:
        metric = tester().metric
        out[name] = {}
        for beta in betas:
            res, _ = testsolve(tester, RPE, None, budget=budget, isp=runs, proc=proc, ranx0=True,
                               seed=SEED, betaeps=beta, crn=crn)
            out[name][beta] = [metric(res[i]['itersoln'][len(res[i]['itersoln']) - 1]) for i in range(runs)]
    return out


def quantile(xs, q):
    # the order statistic at position q*(n-1), interpolated; the paper's
    # figures show sample quantiles without saying which definition
    s = sorted(xs)
    pos = q * (len(s) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def table(results):
    lines = []
    for name, by_beta in results.items():
        lines.append('Problem {0}: dH at the end of the run, quantiles over {1} runs'.format(
            name, len(next(iter(by_beta.values())))))
        lines.append('          beta    q0.25    median    q0.75    q0.90')
        best = min(by_beta, key=lambda b: quantile(by_beta[b], 0.5))
        for beta, xs in by_beta.items():
            lines.append('  {0:12.1f}  {1:7.3f}  {2:8.3f}  {3:7.3f}  {4:7.3f}{5}'.format(
                beta, quantile(xs, 0.25), quantile(xs, 0.5), quantile(xs, 0.75), quantile(xs, 0.9),
                '   <- least median' if beta == best else ''))
    return '\n'.join(lines)


if __name__ == '__main__':
    runs = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    proc = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    crn = bool(int(sys.argv[3])) if len(sys.argv) > 3 else True
    start = time.time()
    results = sweep(runs, proc, crn=crn)
    print('crn', crn)
    print(table(results))
    print(json.dumps({n: {str(b): xs for b, xs in r.items()} for n, r in results.items()}))
    print('elapsed {0:.0f} s'.format(time.time() - start))
