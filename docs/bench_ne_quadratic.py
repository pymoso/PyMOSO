#!/usr/bin/env python
"""
Regenerates docs/ne-quadratic.md: NE's quadratic candidate and
best-improvement scan, against the reference (docs/phase7-plan.md,
steps 4 and 5).

    python docs/bench_ne_quadratic.py run    OUT.jsonl     # the runs
    python docs/bench_ne_quadratic.py report OUT.jsonl OUT.md

Four cells: the reference (first-improvement, no candidate), the
candidate alone, best-improvement alone, and both. Every built-in RA
solver on every built-in test problem it can solve (R-SPLINE on the
first objective), each from a start drawn by the problem's tester, on
the same seeds in every cell.

Counted, never timed: simulations, g() calls, NE and SPLINE events.
Nothing here depends on the machine. `run` appends one JSON line per
run and skips runs already in the file, so an interrupted run resumes.
Solution quality is the tester's own metric at matched counted
simulations (the last RA iteration at or under each checkpoint), and,
for R-SPLINE, the gap between the true first objective of its solution
and the problem's true minimum, found by enumerating the feasible box.
tests/test_benchmark_scripts.py only checks that the script runs.
"""
import contextlib
import io
import itertools
import json
import os
import platform
import random
import statistics
import sys
import time

from pymoso import chnbase
from pymoso.layout import get_solv_prnstreams
from pymoso.paths import isp_run
from pymoso.prng import mrg32k3a
from pymoso.problems.probsimpleso import ProbSimpleSO
from pymoso.problems.probtpa import ProbTPA
from pymoso.problems.probtpb import ProbTPB
from pymoso.problems.probtpc import ProbTPC
from pymoso.solvers.rminrle import RMINRLE
from pymoso.solvers.rpe import RPE
from pymoso.solvers.rperle import RPERLE
from pymoso.solvers.rspline import RSPLINE
from pymoso.testers import simplesotester, tpatester, tpbtester, tpctester

CELLS = {
    'reference': dict(),
    'quadratic': dict(quadratic=1),
    'best': dict(bestimprove=1),
    'best+quadratic': dict(bestimprove=1, quadratic=1),
}
PROBLEMS = {
    'ProbSimpleSO': (ProbSimpleSO, simplesotester, [range(-100, 101)]),
    'ProbTPA': (ProbTPA, tpatester, [range(0, 51)] * 2),
    'ProbTPB': (ProbTPB, tpbtester, [range(0, 101)] * 2),
    'ProbTPC': (ProbTPC, tpctester, [range(-10, 11)] * 3),
}
TESTERS = {'ProbSimpleSO': simplesotester.SimpleSOTester, 'ProbTPA': tpatester.TPATester,
           'ProbTPB': tpbtester.TPBTester, 'ProbTPC': tpctester.TPCTester}
PAIRS = [('RSPLINE', p) for p in PROBLEMS] + [
    (s, p) for s in ('RPERLE', 'RPE', 'RMINRLE') for p in ('ProbTPA', 'ProbTPB', 'ProbTPC')]
SOLVERS = {'RSPLINE': RSPLINE, 'RPERLE': RPERLE, 'RPE': RPE, 'RMINRLE': RMINRLE}
BUDGET = 5000
CHECKPOINTS = (1000, 2500, 5000)
REPS = 20


def seed_for(rep):
    return (1000 + rep,) * 6


def x0_for(problem, rep):
    tester = PROBLEMS[problem][1]
    return tester.get_ranx0(random.Random(rep))


def true_first_min(problem):
    _, tester, box = PROBLEMS[problem]
    return min(tester.true_g(x)[0] for x in itertools.product(*box))


class Probe:
    """NE and SPLINE events, from wrappers on the methods the solvers
    call (chnbase.RASolver.ne/spline/spli); restored on exit."""

    def __init__(self):
        self.ne_calls = 0
        self.candidates = 0             # NE calls that formed and evaluated one
        self.cand_feasible = 0
        self.cand_new = 0               # neither the centre nor a neighbour
        self.cand_new_feasible = 0
        self.cand_beats_neighbours = 0  # a new point strictly below every feasible neighbour
        self.cand_taken = 0             # moved to it
        self.cand_is_centre = 0
        self.cand_is_neighbour = 0
        self.splines = []               # per SPLINE call: NE rounds, nominal, counted, g() calls
        self.stack = []
        self.g_calls = 0

    @contextlib.contextmanager
    def installed(self):
        real_ne, real_spline, real_spli = chnbase.RASolver.ne, chnbase.RASolver.spline, chnbase.RASolver.spli
        probe = self

        def ne(solver, x, fx, sex, nobj, *a, **k):
            calls = []
            real_est = solver.estimate

            def est(p, *ea, **ek):
                out = real_est(p, *ea, **ek)
                calls.append((p, out))
                return out
            solver.estimate = est
            try:
                out = real_ne(solver, x, fx, sex, nobj, *a, **k)
            finally:
                del solver.estimate
            probe.ne_calls += 1
            if probe.stack:
                probe.stack[-1]['rounds'] += 1
                probe.stack[-1]['nominal'] += out[3]
            q = len(x)
            if solver.quadratic and len(calls) == 2 * q + 1:
                probe.candidates += 1
                cand, (cfeas, cf, _) = calls[-1]
                nb = calls[:-1]
                is_centre = cand == x
                is_nb = any(cand == p for p, _ in nb)
                probe.cand_is_centre += is_centre
                probe.cand_is_neighbour += is_nb
                new = not is_centre and not is_nb
                probe.cand_new += new
                if cfeas:
                    probe.cand_feasible += 1
                    if new:
                        probe.cand_new_feasible += 1
                        best_nb = min((r[1][nobj] for _, r in nb if r[0]), default=float('inf'))
                        probe.cand_beats_neighbours += cf[nobj] < best_nb
                    probe.cand_taken += out[0] == cand and new
            return out

        def spline(solver, *a, **k):
            frame = dict(rounds=0, nominal=0, counted=solver.num_calls, g=probe.g_calls)
            probe.stack.append(frame)
            try:
                return real_spline(solver, *a, **k)
            finally:
                probe.stack.pop()
                probe.splines.append((frame['rounds'], frame['nominal'],
                                      solver.num_calls - frame['counted'], probe.g_calls - frame['g']))

        def spli(solver, *a, **k):
            out = real_spli(solver, *a, **k)
            if probe.stack:
                probe.stack[-1]['nominal'] += out[3]
            return out

        chnbase.RASolver.ne, chnbase.RASolver.spline, chnbase.RASolver.spli = ne, spline, spli
        try:
            yield self
        finally:
            chnbase.RASolver.ne, chnbase.RASolver.spline, chnbase.RASolver.spli = real_ne, real_spline, real_spli


def counted_problem(cls, probe):
    class Counted(cls):
        def g(self, x, rng):
            probe.g_calls += 1
            return super().g(x, rng)
    Counted.__name__ = cls.__name__
    return Counted


def quality(problem, solver, soln, fmin):
    tester = PROBLEMS[problem][1]
    if solver == 'RSPLINE':
        return min(tester.true_g(x)[0] for x in soln) - fmin
    return TESTERS[problem]().metric(soln)


def run_one(solver, problem, cell, rep, budget=BUDGET, checkpoints=CHECKPOINTS, fmin=None):
    probe = Probe()
    cls = counted_problem(PROBLEMS[problem][0], probe)
    orcstream, solvstream = get_solv_prnstreams(seed_for(rep), mrg32k3a)
    orc = cls(orcstream)
    orc.set_crnflag(False)
    x0 = x0_for(problem, rep)
    with probe.installed(), contextlib.redirect_stdout(io.StringIO()), orc.set_simpar(1):
        res = isp_run(SOLVERS[solver], budget, orc, solvprn=solvstream, x0=x0, **CELLS[cell])
    iters = sorted(res['itersoln'])
    at = {}
    for c in checkpoints:
        done = [k for k in iters if res['simcalls'][k] <= c and k > 0]
        at[c] = quality(problem, solver, res['itersoln'][done[-1]], fmin) if done else None
    rounds = [s[0] for s in probe.splines]
    return dict(
        solver=solver, problem=problem, cell=cell, rep=rep, seed=list(seed_for(rep)), x0=list(x0),
        budget=budget, iterations=iters[-1], simcalls=res['simcalls'][iters[-1]], g_calls=probe.g_calls,
        quality={str(c): q for c, q in at.items()},
        ne_calls=probe.ne_calls, candidates=probe.candidates, cand_feasible=probe.cand_feasible,
        cand_new=probe.cand_new, cand_new_feasible=probe.cand_new_feasible,
        cand_beats_neighbours=probe.cand_beats_neighbours, cand_taken=probe.cand_taken,
        cand_is_centre=probe.cand_is_centre, cand_is_neighbour=probe.cand_is_neighbour,
        spline_calls=len(probe.splines), spline_rounds=sum(rounds),
        spline_nominal=sum(s[1] for s in probe.splines), spline_counted=sum(s[2] for s in probe.splines),
        spline_g=sum(s[3] for s in probe.splines),
    )


def _done(path):
    done = set()
    if os.path.exists(path):
        for line in open(path):
            r = json.loads(line)
            done.add((r['solver'], r['problem'], r['cell'], r['rep']))
    return done


def run(path, pairs=PAIRS, cells=CELLS, reps=REPS, budget=BUDGET, checkpoints=CHECKPOINTS, verbose=True):
    done = _done(path)
    fmins = {}
    for solver, problem in pairs:
        if solver == 'RSPLINE' and problem not in fmins:
            fmins[problem] = true_first_min(problem)
        for rep in range(reps):
            for cell in cells:
                if (solver, problem, cell, rep) in done:
                    continue
                t0 = time.perf_counter()
                row = run_one(solver, problem, cell, rep, budget, checkpoints, fmins.get(problem))
                row.update(python=platform.python_version(), loadavg=os.getloadavg()[0],
                           when=time.strftime('%Y-%m-%dT%H:%M:%S'))
                with open(path, 'a') as f:
                    f.write(json.dumps(row) + '\n')
                if verbose:
                    print(solver, problem, cell, rep, row['simcalls'], '{0:.1f}s'.format(time.perf_counter() - t0),
                          flush=True)


def _pct(a, b):
    return '{0:.0f}%'.format(100 * a / b) if b else '-'


def report(path, out):
    rows = [json.loads(line) for line in open(path)]
    by = {}
    for r in rows:
        by.setdefault((r['solver'], r['problem']), {}).setdefault(r['cell'], {})[r['rep']] = r
    cells = list(CELLS)
    lines = ['<!-- generated by docs/bench_ne_quadratic.py report; do not edit -->', '']
    lines.append('Runs: {0}. Python {1}. Budget {2}, {3} seeds per configuration.'.format(
        len(rows), sorted({r['python'] for r in rows}), sorted({r['budget'] for r in rows}),
        max(len(v) for d in by.values() for v in d.values())))
    lines.append('')
    lines.append('### The candidate, per NE call that formed one')
    lines.append('')
    lines.append('A candidate is "new" when it is neither the centre nor one of the neighbours just evaluated; '
                 '"beats every neighbour" and "taken" are fractions of the feasible new ones.')
    lines.append('')
    lines.append('| solver | problem | cell | NE calls | candidates | the centre | a neighbour | new | new and feasible | beats every neighbour | taken |')
    lines.append('|---|---|---|---|---|---|---|---|---|---|---|')
    for (s, p), d in by.items():
        for c in ('quadratic', 'best+quadratic'):
            rs = list(d.get(c, {}).values())
            if not rs:
                continue
            tot = {k: sum(r[k] for r in rs) for k in ('ne_calls', 'candidates', 'cand_new', 'cand_new_feasible',
                                                     'cand_beats_neighbours', 'cand_taken', 'cand_is_centre',
                                                     'cand_is_neighbour')}
            lines.append('| {0} | {1} | {2} | {3:,} | {4:,} | {5} | {6} | {7} | {8} | {9} | {10} |'.format(
                s, p, c, tot['ne_calls'], tot['candidates'],
                _pct(tot['cand_is_centre'], tot['candidates']), _pct(tot['cand_is_neighbour'], tot['candidates']),
                _pct(tot['cand_new'], tot['candidates']), _pct(tot['cand_new_feasible'], tot['cand_new']),
                _pct(tot['cand_beats_neighbours'], tot['cand_new_feasible']),
                _pct(tot['cand_taken'], tot['cand_new_feasible'])))
    lines.append('')
    lines.append('### SPLINE, and the run, per cell (medians over seeds)')
    lines.append('')
    lines.append('NE rounds per SPLINE call; simulations (counted, feasible only) and g() calls (every replication, '
                 'feasible or not) per SPLINE call; SPLINE\'s nominal charge over its counted simulations; '
                 'RA iterations and simulations for the whole run.')
    lines.append('')
    lines.append('| solver | problem | cell | NE rounds / SPLINE | sims / SPLINE | g() / SPLINE | nominal / counted | iterations | run sims |')
    lines.append('|---|---|---|---|---|---|---|---|---|')
    med = statistics.median
    for (s, p), d in by.items():
        for c in cells:
            rs = list(d.get(c, {}).values())
            if not rs:
                continue
            lines.append('| {0} | {1} | {2} | {3:.2f} | {4:.0f} | {5:.0f} | {6:.2f} | {7:.0f} | {8:,.0f} |'.format(
                s, p, c,
                med(r['spline_rounds'] / r['spline_calls'] for r in rs),
                med(r['spline_counted'] / r['spline_calls'] for r in rs),
                med(r['spline_g'] / r['spline_calls'] for r in rs),
                med(r['spline_nominal'] / r['spline_counted'] for r in rs if r['spline_counted']),
                med(r['iterations'] for r in rs), med(r['simcalls'] for r in rs)))
    lines.append('')
    lines.append('### Quality at matched counted simulations, against the reference, seed by seed')
    lines.append('')
    lines.append('The tester\'s metric (Hausdorff distance to the true efficient frontier), or for R-SPLINE the gap '
                 'to the true minimum of the first objective: lower is better. Median, and how many seeds the cell '
                 'did better / the same / worse than the reference on the same seed. A seed with no iteration '
                 'finished by the checkpoint is left out.')
    lines.append('')
    cps = sorted({int(c) for r in rows for c in r['quality']})
    lines.append('| solver | problem | cell | ' + ' | '.join('at {0:,}'.format(c) for c in cps) + ' |')
    lines.append('|---|---|---|' + '---|' * len(cps))
    for (s, p), d in by.items():
        ref = d.get('reference', {})
        for c in cells:
            rs = d.get(c, {})
            if not rs:
                continue
            cellv = []
            for cp in cps:
                k = str(cp)
                pairs = [(rs[i]['quality'][k], ref[i]['quality'][k]) for i in rs
                         if i in ref and rs[i]['quality'].get(k) is not None and ref[i]['quality'].get(k) is not None]
                if not pairs:
                    cellv.append('-')
                    continue
                m = med(a for a, _ in pairs)
                if c == 'reference':
                    cellv.append('{0:.3g}'.format(m))
                else:
                    better = sum(a < b for a, b in pairs)
                    same = sum(a == b for a, b in pairs)
                    cellv.append('{0:.3g} ({1}/{2}/{3})'.format(m, better, same, len(pairs) - better - same))
            lines.append('| {0} | {1} | {2} | '.format(s, p, c) + ' | '.join(cellv) + ' |')
    with open(out, 'w') as f:
        f.write('\n'.join(lines) + '\n')


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'run':
        run(sys.argv[2])
    elif cmd == 'report':
        report(sys.argv[2], sys.argv[3])
    else:
        raise SystemExit(__doc__)
