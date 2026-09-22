#!/usr/bin/env python
"""
The single-seed old-vs-new comparison (task5_metric_compare.py) is not
statistically meaningful on its own: these are stochastic algorithms, and
a single run's metric value has enormous seed-to-seed variance. A
"better" or "worse" single number just reflects which seed you happened
to draw, not a property of the fix.

The scientific question is whether the *distribution* of solution quality
changed. The mechanism (docs/phase2a-verification.md item 1) predicts it
should not: the fix corrects *how far* the jump-ahead lands, not whether
the values drawn are valid, well-mixed MRG32k3a output. Every RA
iteration after the first was landing at a wrong-but-still-uniform
position, not a degenerate one. So old and new code should produce
statistically indistinguishable metric distributions across many
independent seeds, even though any single matched seed gives a different
(and incomparable) run.

Run this once under the pre-fix code (git stash) and once under the
post-fix code, over N independent seeds each, budget higher than the
golden tests' 1000 so the metric isn't dominated by "barely started".
"""
import json
import sys
sys.path.insert(0, '/home/kyle/Documents/PyMOSO')

from pymoso.chnutils import solve
from pymoso.problems.probtpa import ProbTPA
from pymoso.problems.probsimpleso import ProbSimpleSO
from pymoso.solvers.rperle import RPERLE
from pymoso.solvers.rspline import RSPLINE
from pymoso.testers.tpatester import TPATester
from pymoso.testers.simplesotester import SimpleSOTester
from pymoso.prng.mrg32k3a import get_next_prnstream

N_SEEDS = 40
BUDGET = 5000

def make_seeds(n, base=(12345, 12345, 12345, 12345, 12345, 12345)):
    seeds = []
    s = base
    for _ in range(n):
        prn = get_next_prnstream(s, False)
        s = prn.get_seed()
        seeds.append(s)
    return seeds

seeds = make_seeds(N_SEEDS)

results = {'rperle_tpa': [], 'rspline_simpleso': []}
tpa_tester = TPATester()
so_tester = SimpleSOTester()

for i, seed in enumerate(seeds):
    res, _ = solve(ProbTPA, RPERLE, (40, 40), budget=BUDGET, seed=seed)
    results['rperle_tpa'].append(tpa_tester.metric(set(res)))

    res2, _ = solve(ProbSimpleSO, RSPLINE, (40,), budget=BUDGET, seed=seed)
    results['rspline_simpleso'].append(so_tester.metric(set(res2)))

out_path = sys.argv[1] if len(sys.argv) > 1 else '/tmp/metric_dist.json'
with open(out_path, 'w') as f:
    json.dump(results, f, indent=2)

for k, vals in results.items():
    mean = sum(vals) / len(vals)
    svals = sorted(vals)
    median = svals[len(svals)//2]
    print(f"{k}: n={len(vals)} mean={mean:.4f} median={median:.4f} min={min(vals):.4f} max={max(vals):.4f}")
print(f"wrote {out_path}")
