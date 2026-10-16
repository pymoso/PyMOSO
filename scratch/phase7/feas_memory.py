"""What a whole-run record of feasibility verdicts would hold (KNOWN_ISSUES
issue 18's check, before it is built).

For each run: distinct points ever estimated feasible and ever
infeasible, the largest single iteration's gbar for scale, and the
bytes the two sets would occupy, tuples included, measured with
tracemalloc by rebuilding them from fresh tuples after the run.
Points whose verdict ever flipped are counted too (0 for these
problems, which decide feasibility from x).

    python scratch/phase7/feas_memory.py OUT.jsonl
"""
import contextlib
import io
import json
import pathlib
import sys
import tracemalloc

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import dtlz2_lattice as dl  # noqa: E402

import pymoso.chnbase as chnbase  # noqa: E402
from pymoso.layout import get_solv_prnstreams  # noqa: E402
from pymoso.paths import isp_run  # noqa: E402
from pymoso.prng import registry  # noqa: E402
from pymoso.problems import probexpensive as pe_mod  # noqa: E402
from pymoso.solvers.rminrle import RMINRLE  # noqa: E402
from pymoso.solvers.rperle import RPERLE  # noqa: E402

CONFIGS = [('RMINRLE DTLZ2 M{0} budget {1}'.format(M, b), dl.make_problem(M, 0.05, 4), RMINRLE,
            (2,) * 7 + (0,), b, 'philox4x32', (1, 12345))
           for M, b in [(2, 30000), (3, 30000), (4, 30000), (5, 30000), (6, 30000),
                        (3, 100000), (6, 100000)]]
CONFIGS += [('RPERLE Bi (0, 20) budget 10000', pe_mod.ProbExpensiveBi, RPERLE, (0, 20), 10000,
             'mrg32k3a', (12345,) * 6),
            ('RMINRLE Bi (0, 20) budget 10000', pe_mod.ProbExpensiveBi, RMINRLE, (0, 20), 10000,
             'mrg32k3a', (12345,) * 6)]


def run(name, cls, solver, x0, budget, gen, seed):
    feas, infeas = set(), set()
    peak = [0]
    real_est, real_many = chnbase.RASolver.estimate, chnbase.RASolver.estimate_many

    def note(self, x, isfeas):
        (feas if isfeas else infeas).add(x)
        peak[0] = max(peak[0], len(self.gbar))

    def estimate(self, x, *a, **k):
        out = real_est(self, x, *a, **k)
        note(self, x, x in self.gbar)          # oracle feasibility, not the constraint
        return out

    def estimate_many(self, points):
        points = list(points)
        out = real_many(self, points)
        for x, (isfeas, _, _) in zip(points, out):
            note(self, x, isfeas)
        return out
    chnbase.RASolver.estimate, chnbase.RASolver.estimate_many = estimate, estimate_many
    try:
        orcstream, solvstream = get_solv_prnstreams(seed, registry.get_generator(gen))
        orc = cls(orcstream)
        orc.set_crnflag(False)
        with contextlib.redirect_stdout(io.StringIO()), orc.set_simpar(1):
            res = isp_run(solver, budget, orc, solvprn=solvstream, x0=x0)
    finally:
        chnbase.RASolver.estimate, chnbase.RASolver.estimate_many = real_est, real_many
    fl, il = [tuple(x) for x in feas], [tuple(x) for x in infeas]

    def measured(points):
        tracemalloc.start()
        before = tracemalloc.get_traced_memory()[0]
        held = {tuple(int(v) for v in x) for x in points}
        size = tracemalloc.get_traced_memory()[0] - before
        tracemalloc.stop()
        del held
        return size
    last = max(res['itersoln'])
    return dict(config=name, simcalls=res['simcalls'][last], iterations=last,
                feasible=len(feas), infeasible=len(infeas), flipped=len(feas & infeas),
                peak_gbar=peak[0], bytes_feasible=measured(fl), bytes_infeasible=measured(il))


if __name__ == '__main__':
    with open(sys.argv[1], 'w') as f:
        for cfg in CONFIGS:
            row = run(*cfg)
            f.write(json.dumps(row) + '\n')
            print(json.dumps(row), flush=True)
