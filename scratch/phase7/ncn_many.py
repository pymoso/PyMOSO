"""get_ncn's early-exit ratio at M >= 3 (Phase 7, step 1, outstanding).

RMINRLE on the many-objective baseline's lattice DTLZ2 (L = 4, arm A,
sigma 0.05, x0 as there, Philox), instrumented with
docs/bench_biobjective_profile.py's probes: 'count' gives predicate and
calc_delta calls done in get_ncn against what an early exit giving the
same ncn needs (the shadow asserts the same answer on every call);
'time' gives get_ncn's exclusive share of the run.

    python ncn_many.py OUT.jsonl BUDGET M[,M...] REPS
"""
import contextlib
import importlib.util
import io
import json
import os
import pathlib
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import dtlz2_lattice as dl  # noqa: E402

spec = importlib.util.spec_from_file_location(
    'bench', str(HERE.parent.parent / 'docs' / 'bench_biobjective_profile.py'))
bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bench)

from pymoso.chnutils import solve  # noqa: E402
from pymoso.layout import get_solv_prnstreams  # noqa: E402
from pymoso.paths import isp_run  # noqa: E402
from pymoso.prng import registry  # noqa: E402
from pymoso.solvers.rminrle import RMINRLE  # noqa: E402

L, SIGMA, GEN = 4, 0.05, 'philox4x32'
X0 = (L // 2,) * (dl.N_DIM - 1) + (0,)


def run_one(M, seed, budget, mode):
    cls = dl.make_problem(M, SIGMA, L)
    orcstream, solvstream = get_solv_prnstreams(seed, registry.get_generator(GEN))
    orc = cls(orcstream)
    orc.set_crnflag(False)
    with bench.instrumented(mode, cls) as probe, contextlib.redirect_stdout(io.StringIO()):
        t0 = time.perf_counter()
        with orc.set_simpar(1):
            res = isp_run(RMINRLE, budget, orc, solvprn=solvstream, x0=X0)
        wall = time.perf_counter() - t0
    last = max(res['itersoln'])
    row = dict(M=M, seed=list(seed), budget=budget, mode=mode, wall=wall,
               simcalls=res['simcalls'][last], iterations=last,
               soln=sorted(res['itersoln'][last]), endseed=list(res['endseed']),
               sizes=[len(res['itersoln'][nu]) for nu in sorted(res['itersoln'])],
               load=os.getloadavg())
    if mode == 'time':
        row['excl'] = probe.excl
    if mode == 'count':
        c = probe.c
        get = lambda *k: c.get(k, 0)
        ncn = probe.lists.get('get_ncn', [])
        row.update(
            shadow_checked=get('ncn_shadow_checked'), ncn_calls=len(ncn),
            a_done=get('pred', 'get_ncn', 'chnbase.does_strict_dominate'),
            a_need=sum(d['need_a'] for d in ncn),
            b_done=get('pred', 'get_ncn', 'chnbase.does_weak_dominate')
            + get('pred', 'get_ncn', 'chnbase.does_dominate'),
            b_need=sum(d['need_b'] for d in ncn),
            cd_done=get('calc_delta', 'get_ncn'),
            cd_need=sum((d['S'] + d['cands']) * M for d in ncn),
            mean_S=sum(d['S'] for d in ncn) / max(1, len(ncn)),
            max_S=max((d['S'] for d in ncn), default=0))
    return row


def main(out, budget, Ms, reps):
    done = set()
    if os.path.exists(out):
        for line in open(out):
            r = json.loads(line)
            done.add((r['M'], tuple(r['seed']), r['budget'], r['mode']))
    for rep in range(reps):
        seed = (rep + 1, 12345)
        for M in Ms:
            ref = None
            for mode in ('plain', 'time', 'count'):
                if (M, seed, budget, mode) in done:
                    continue
                row = run_one(M, seed, budget, mode)
                key = (row['soln'], row['endseed'])
                ref = ref or key
                assert key == ref, 'instrumentation changed the run'
                with open(out, 'a') as f:
                    f.write(json.dumps(row) + '\n')
                print(M, seed, mode, round(row['wall'], 1), flush=True)


if __name__ == '__main__':
    main(sys.argv[1], int(sys.argv[2]), [int(m) for m in sys.argv[3].split(',')],
         int(sys.argv[4]))
