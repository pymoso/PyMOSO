"""Step 1b, before any design: what does remembering oracle-infeasible
points within an RA iteration change?

Shadow only: RASolver.estimate/estimate_many are patched in this process
to return a point's first infeasible outcome again, without simulating,
for the rest of that iteration (gbar's lifetime). Nothing in pymoso/
changes. Each configuration runs twice, without and with the shadow,
and the solution, end seed, simcalls and g() calls are compared.

    python infeas_cache.py OUT.jsonl
"""
import contextlib
import io
import json
import sys
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import dtlz2_lattice as dl  # noqa: E402

import pymoso.chnbase as chnbase  # noqa: E402
from pymoso.layout import get_solv_prnstreams  # noqa: E402
from pymoso.paths import isp_run  # noqa: E402
from pymoso.prng import registry  # noqa: E402
from pymoso.problems import probexpensive as pe_mod  # noqa: E402
from pymoso.problems.probtpa import ProbTPA  # noqa: E402
from pymoso.problems.probtpb import ProbTPB  # noqa: E402
from pymoso.solvers.rminrle import RMINRLE  # noqa: E402
from pymoso.solvers.rperle import RPERLE  # noqa: E402
from pymoso.solvers.rspline import RSPLINE  # noqa: E402

_EST = chnbase.RASolver.estimate
STATE = {'on': False, 'skipped': 0, 'hits': 0}


def estimate(self, x, con=float('inf'), nobj=0):
    if STATE['on'] and x not in self.gbar:
        memo = self.__dict__.setdefault('_infeas_memo', {})
        key = (self.nu, x)
        if key in memo:
            STATE['skipped'] += 1
            return memo[key]
        out = _EST(self, x, con, nobj)
        if not out[0] and x not in self.gbar:      # oracle-infeasible, not con
            memo[key] = out
        return out
    return _EST(self, x, con, nobj)


_EM = chnbase.RASolver.estimate_many


def estimate_many(self, points):
    """Batched like the real one; a point already found infeasible this
    iteration, or earlier in this same list, is answered from the record."""
    if not STATE['on']:
        return _EM(self, points)
    points = list(points)
    memo = self.__dict__.setdefault('_infeas_memo', {})
    todo = []
    for x in points:
        if x not in self.gbar and (self.nu, x) not in memo and x not in todo:
            todo.append(x)
    fresh = dict(zip(todo, _EM(self, todo)))
    for x, out in fresh.items():
        if not out[0]:
            memo[(self.nu, x)] = out
    results = []
    for x in points:
        if x in self.gbar:
            results.append((True, self.gbar[x], self.sehat[x]))
        else:
            if x not in fresh or fresh.get(x) is None:
                STATE['skipped'] += 1
            results.append(memo[(self.nu, x)])
            fresh[x] = None
    return results


P_INFEAS = float(__import__('os').environ.get('P_INFEAS', '0.03'))


class RandomEdgeBi(pe_mod.ProbExpensiveBi):
    """ProbExpensiveBi, except that near x[0] = 0 a replication is
    infeasible with probability P_INFEAS: feasibility is random there."""
    def g(self, x, rng):
        if 0 <= x[0] <= 5 and rng.random() < P_INFEAS:
            return False, (None, None)
        return super().g(x, rng)


class Counting:
    def __init__(self, cls):
        self.n = 0
        real = cls.g

        def g(obj, x, rng):
            self.n += 1
            return real(obj, x, rng)
        self.cls = type(cls.__name__, (cls,), {'g': g})


SEEDS = {'mrg32k3a': [(12345,) * 6, (42,) * 6, (271828,) * 6],
         'philox4x32': [(12345, 12345), (42, 42), (271828, 271828)]}

CONFIGS = [
    # name, problem class, solver, x0, budget
    ('RPERLE BiEdge', pe_mod.ProbExpensiveBi, RPERLE, (0, 20), 10000),
    ('RMINRLE BiEdge', pe_mod.ProbExpensiveBi, RMINRLE, (0, 20), 10000),
    ('RSPLINE BiEdge', pe_mod.ProbExpensiveBi, RSPLINE, (0, 20), 10000),
    ('RPERLE TPA', ProbTPA, RPERLE, (0, 20), 10000),
    ('RPERLE TPB', ProbTPB, RPERLE, (0, 0), 10000),
    ('RMINRLE DTLZ2 M3', dl.make_problem(3, 0.05, 4), RMINRLE, (2,) * 7 + (0,), 20000),
    ('RMINRLE DTLZ2 M4', dl.make_problem(4, 0.05, 4), RMINRLE, (2,) * 7 + (0,), 20000),
    ('RPERLE RandomEdge', RandomEdgeBi, RPERLE, (8, 20), 10000),
    ('RMINRLE RandomEdge', RandomEdgeBi, RMINRLE, (8, 20), 10000),
]


def run(cls, solver, x0, budget, gen, seed, on):
    STATE.update(on=on, skipped=0)
    counter = Counting(cls)
    orcstream, solvstream = get_solv_prnstreams(seed, registry.get_generator(gen))
    orc = counter.cls(orcstream)
    orc.set_crnflag(False)
    with contextlib.redirect_stdout(io.StringIO()), orc.set_simpar(1):
        res = isp_run(solver, budget, orc, solvprn=solvstream, x0=x0)
    last = max(res['itersoln'])
    return dict(soln=sorted(res['itersoln'][last]), endseed=list(res['endseed']),
                simcalls=res['simcalls'][last], iterations=last, g=counter.n,
                skipped=STATE['skipped'],
                path=[sorted(res['itersoln'][nu]) for nu in sorted(res['itersoln'])])


def main(out):
    chnbase.RASolver.estimate = estimate
    chnbase.RASolver.estimate_many = estimate_many
    only = sys.argv[2] if len(sys.argv) > 2 else ''
    for name, cls, solver, x0, budget in CONFIGS:
        if only not in name:
            continue
        for gen in ('mrg32k3a', 'philox4x32'):
            for seed in SEEDS[gen]:
                a = run(cls, solver, x0, budget, gen, seed, False)
                b = run(cls, solver, x0, budget, gen, seed, True)
                row = dict(config=name, generator=gen, seed=list(seed),
                           same_soln=a['soln'] == b['soln'], same_path=a['path'] == b['path'],
                           same_endseed=a['endseed'] == b['endseed'],
                           simcalls=(a['simcalls'], b['simcalls']),
                           iterations=(a['iterations'], b['iterations']),
                           g=(a['g'], b['g']), skipped=b['skipped'])
                with open(out, 'a') as f:
                    f.write(json.dumps(row) + '\n')
                print(name, gen, seed[0], 'soln', row['same_soln'], 'path', row['same_path'],
                      'endseed', row['same_endseed'], 'g', row['g'], 'skipped', row['skipped'],
                      flush=True)


if __name__ == '__main__':
    main(sys.argv[1])
