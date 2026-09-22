#!/usr/bin/env python
"""
Task 4: run solve() with a known-infeasible x0, for each built-in solver.
Report the actual exception and message. Confirm/refute the
KeyError-vs-ValueError analysis from docs/phase1-review.md risk #5.
"""
import sys
import traceback
sys.path.insert(0, '/home/kyle/Documents/PyMOSO')

from pymoso import chnutils
from pymoso.problems.probtpa import ProbTPA
from pymoso.problems.probsimpleso import ProbSimpleSO
from pymoso.solvers.rperle import RPERLE
from pymoso.solvers.rpe import RPE
from pymoso.solvers.rminrle import RMINRLE
from pymoso.solvers.rspline import RSPLINE

# ProbTPA is feasible on x >= 0 roughly per its constraint; use a clearly
# out-of-domain / infeasible point. Check probtpa.py for feasibility rule
# first via direct call.


def probe_feasibility(prob_cls, x0, rng_seed=(12345,)*6):
    from pymoso.prng.mrg32k3a import MRG32k3a
    MRG32k3a.set_class_cache(False)
    orc = prob_cls(MRG32k3a(rng_seed))
    isfeas, obj = orc.g(x0, MRG32k3a(rng_seed))
    print(f"  g({x0}) on {prob_cls.__name__}: isfeas={isfeas}, obj={obj}")
    return isfeas


print("=== Probing feasibility of candidate x0 values ===")
probe_feasibility(ProbTPA, (40, 40))
probe_feasibility(ProbTPA, (-100, -100))
probe_feasibility(ProbTPA, (-1, -1))
probe_feasibility(ProbSimpleSO, (40,))
probe_feasibility(ProbSimpleSO, (-1000,))
print()


def try_solve(name, prob, solver, x0, budget=1000):
    print(f"--- {name}: solve with x0={x0} ---")
    try:
        result = chnutils.solve(prob, solver, x0, budget=budget)
        print(f"  NO EXCEPTION. result={result}")
    except SystemExit as e:
        print(f"  SystemExit raised (code={e.code}) -- means sys.exit() was reached "
              f"somewhere in the friendly-error path (caught internally, printed above).")
    except Exception as e:
        print(f"  EXCEPTION: {type(e).__name__}: {e}")
        tb = traceback.format_exc()
        print("  --- traceback ---")
        print(tb)
    print()


cases = [
    ("ProbTPA/RPERLE, infeasible x0 alone (empty warm start alternative)", ProbTPA, RPERLE, (-100, -100)),
    ("ProbTPA/RPE, infeasible x0", ProbTPA, RPE, (-100, -100)),
    ("ProbTPA/RMINRLE, infeasible x0", ProbTPA, RMINRLE, (-100, -100)),
    ("ProbSimpleSO/RSPLINE, infeasible x0", ProbSimpleSO, RSPLINE, (-1000,)),
]

for name, prob, solver, x0 in cases:
    try_solve(name, prob, solver, x0)
