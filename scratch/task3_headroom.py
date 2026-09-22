#!/usr/bin/env python
"""
Task 3a: instrument RA iteration counts (self.nu at completion) for the
built-in problem/solver combinations across a range of budgets, at default
solver settings (mconst=2, bconst=8), to find how large a budget is needed
to reach 200 RA iterations.
"""
import sys
sys.path.insert(0, '/home/kyle/Documents/PyMOSO')

from pymoso.chnutils import get_solv_prnstreams
from pymoso.problems.probtpa import ProbTPA
from pymoso.problems.probsimpleso import ProbSimpleSO
from pymoso.solvers.rperle import RPERLE
from pymoso.solvers.rpe import RPE
from pymoso.solvers.rminrle import RMINRLE
from pymoso.solvers.rspline import RSPLINE

seed = (12345, 12345, 12345, 12345, 12345, 12345)


def run_once(problem_cls, solver_cls, x0, budget, crn=False):
    orcstream, solvstream = get_solv_prnstreams(seed, crn)
    orc = problem_cls(orcstream)
    orc.set_crnflag(crn)
    orc.simpar = 1
    solver = solver_cls(orc, sprn=solvstream, x0=x0)
    res = solver.solve(budget)
    nu_final = len(res['itersoln']) - 1
    return nu_final


cases = [
    ("ProbTPA/RPERLE", ProbTPA, RPERLE, (40, 40)),
    ("ProbTPA/RPE", ProbTPA, RPE, (40, 40)),
    ("ProbTPA/RMINRLE", ProbTPA, RMINRLE, (40, 40)),
    ("ProbSimpleSO/RSPLINE", ProbSimpleSO, RSPLINE, (40,)),
]

budgets = [1000, 5000, 10000, 20000, 50000, 100000, 200000, 400000]

for name, prob, solv, x0 in cases:
    print(f"=== {name} (default budget in CLI = 50000) ===")
    prev_nu = None
    for b in budgets:
        nu = run_once(prob, solv, x0, b)
        flag = "  <-- reaches/exceeds max_RI=200" if nu >= 200 else ""
        print(f"  budget={b:>7}: final RA iterations (nu) = {nu:>4}{flag}")
        if nu >= 200 and prev_nu is not None and prev_nu < 200:
            print(f"    ^ crosses the 200-iteration threshold between budget={prev_budget} and budget={b}")
        prev_nu = nu
        prev_budget = b
    print()
