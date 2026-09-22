#!/usr/bin/env python
"""
Run the golden-test cases that have known-truth testers, using the exact
same problem/solver/x0/seed/budget/crn as tests/test_golden.py, and report
the returned solution SET plus the tester's own metric against the true
solution. Run this once with the pre-fix mrg32k3a.py (git stash) and once
with the post-fix version, diff the two JSON outputs.
"""
import json
import sys
sys.path.insert(0, '/home/kyle/Documents/PyMOSO')

from pymoso.chnutils import solve, testsolve
from pymoso.problems.probtpa import ProbTPA
from pymoso.problems.probsimpleso import ProbSimpleSO
from pymoso.solvers.rperle import RPERLE
from pymoso.solvers.rpe import RPE
from pymoso.solvers.rminrle import RMINRLE
from pymoso.solvers.rspline import RSPLINE
from pymoso.testers.tpatester import TPATester
from pymoso.testers.simplesotester import SimpleSOTester

DEFAULT_SEED = (12345, 12345, 12345, 12345, 12345, 12345)
SEED2 = (1, 2, 3, 4, 5, 6)

results = {}

def run_solve(name, prob, solver, x0, budget=1000, seed=DEFAULT_SEED, crn=False, tester=None):
    res, end_seed = solve(prob, solver, x0, budget=budget, seed=seed, crn=crn)
    res_sorted = sorted(str(p) for p in res)
    entry = {
        'end_seed': list(end_seed),
        'solution_set': res_sorted,
        'solution_set_size': len(res),
    }
    if tester is not None:
        entry['metric'] = tester().metric(set(res))
    results[name] = entry
    print(f"{name}: n={len(res)} metric={entry.get('metric')}")

run_solve('rperle_tpa', ProbTPA, RPERLE, (40, 40), tester=TPATester)
run_solve('rminrle_tpa', ProbTPA, RMINRLE, (40, 40), tester=TPATester)
run_solve('rpe_tpa', ProbTPA, RPE, (40, 40), tester=TPATester)
run_solve('rperle_tpa_crn', ProbTPA, RPERLE, (40, 40), crn=True, tester=TPATester)
run_solve('rperle_tpa_seed2', ProbTPA, RPERLE, (40, 40), seed=SEED2, tester=TPATester)
run_solve('rspline_simpleso', ProbSimpleSO, RSPLINE, (40,), tester=SimpleSOTester)

# testsolve_tpa: isp=4, budget=1000, default seed, no crn
tres, tend_seed = testsolve(TPATester, RPERLE, (0,), budget=1000, seed=DEFAULT_SEED,
                             isp=4, proc=1, ranx0=True, crn=False)
tt = TPATester()
per_isp = []
for i in range(4):
    lastnu = len(tres[i]['itersoln']) - 1
    solset = tres[i]['itersoln'][lastnu]
    per_isp.append({
        'isp': i,
        'n': len(solset),
        'metric': tt.metric(set(solset)),
        'solution_set': sorted(str(p) for p in solset),
    })
    print(f"testsolve_tpa isp{i}: n={len(solset)} metric={tt.metric(set(solset))}")
results['testsolve_tpa'] = {'end_seed': list(tend_seed), 'per_isp': per_isp}

out_path = sys.argv[1] if len(sys.argv) > 1 else '/tmp/metric_compare.json'
with open(out_path, 'w') as f:
    json.dump(results, f, indent=2)
print(f"wrote {out_path}")
