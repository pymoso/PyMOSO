#!/usr/bin/env python
"""
Regenerates docs/plateau-problems.md's measurements: what the built-in
solvers do on integer plateaus, where the true pseudo-gradient is zero
(docs/phase7-plan.md, step 6).

    python docs/bench_plateau.py verify               # the known answer, checked
    python docs/bench_plateau.py mutations            # ... and the check shown to detect
    python docs/bench_plateau.py describe OUT.json    # traps per width and radius
    python docs/bench_plateau.py run      OUT.jsonl   # the solver runs (counted)
    python docs/bench_plateau.py report   OUT.jsonl DESCRIBE.json OUT.md

The problem is scratch/phase7/plateau.py: W x W cells on {0..59}^2, each
flat at the value of two quadratics at its centre; W = 1 is the matched
control without plateaus.

`verify` holds the exact certificate (barrier.certified_by) to PyMOSO's
own, as RLESolver.rle applies it (docs/bench_radius.py's
`code_certified`), on the plateau's efficient sets, single points, whole
cells, grown and random sets, at radii 1-6, where ties between points
are everywhere. `mutations` runs `verify` against wrong versions of the
exact certificate and reports which are caught. `describe` is a
property of the problem alone: certified single points (traps) and
first-objective local minima per width and radius, and ties between
points of different cells.

`run` counts. Arms: the default (no CRN) and CRN, which makes equal true
values give exactly equal estimates. Per run: quality at matched counted
simulations against the control on the same seed; and what the search
did on a plateau -- PLI calls whose pseudo-gradient was exactly zero,
SPLI and NE moves that lowered the true value against moves that lowered
only the estimate, NE moves to a point of the same cell (a true tie),
and distinct cells visited. One arm of ExampleBnBSolver (the in-tree
MOPBnB port) is included, labelled as what it is: a non-local sampler
(docs/mocompass-mopbnb-known-issues.md, item 0), not partition-and-bound.
`run` appends one JSON line per run and skips runs already in the file.

tests/test_benchmark_scripts.py only checks that the script runs.
"""
import contextlib
import importlib.util
import io
import itertools
import json
import os
import pathlib
import platform
import random
import statistics
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scratch' / 'phase7'))
import barrier  # noqa: E402
import plateau  # noqa: E402

_spec = importlib.util.spec_from_file_location('bench_radius', str(ROOT / 'docs' / 'bench_radius.py'))
bench_radius = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bench_radius)

from pymoso import chnbase, moso  # noqa: E402
from pymoso.layout import get_solv_prnstreams  # noqa: E402
from pymoso.paths import isp_run  # noqa: E402
from pymoso.prng import mrg32k3a  # noqa: E402
from pymoso.solvers.mopbnb import ExampleBnBSolver  # noqa: E402
from pymoso.solvers.rminrle import RMINRLE  # noqa: E402
from pymoso.solvers.rpe import RPE  # noqa: E402
from pymoso.solvers.rperle import RPERLE  # noqa: E402
from pymoso.solvers.rspline import RSPLINE  # noqa: E402

BUDGET = 20000
CHECKPOINTS = (1000, 5000, 20000)
REPS = 20
OVERSHOOT = 50
SOLVERS = {'RSPLINE': RSPLINE, 'RPERLE': RPERLE, 'RPE': RPE, 'RMINRLE': RMINRLE,
           'ExampleBnBSolver': ExampleBnBSolver}
ARMS = ('default', 'crn')
# (solver, width, radius, arm)
CONFIGS = ([(s, w, 1, a) for s in ('RSPLINE', 'RPERLE', 'RPE', 'RMINRLE') for w in plateau.WIDTHS for a in ARMS]
           + [(s, 10, r, a) for s in ('RSPLINE', 'RPERLE', 'RPE', 'RMINRLE') for r in (3, 6) for a in ARMS]
           + [('ExampleBnBSolver', w, None, 'default') for w in plateau.WIDTHS])
VERIFY_RADII = (1, 2, 3, 6)


def _loadavg():
    """The load averages where the platform has them (not Windows)."""
    try:
        return os.getloadavg()
    except (AttributeError, OSError):
        return None


def seed_for(rep):
    return (1000 + rep,) * 6


def x0_for(rep):
    return plateau.get_ranx0(random.Random(rep))


# ---- verify and mutations ----

def _cell_points(c, w):
    return {x for x in plateau.BOX if plateau.cell(x, w) == c}


def verify(widths=plateau.WIDTHS, radii=VERIFY_RADII, extra=20, seed=11, verbose=True):
    """The exact certificate against PyMOSO's own on the plateaus. Raises
    on any disagreement, and if a set known not to be certified passes."""
    rng = random.Random(seed)
    agree = total = positives = rejected_known = 0

    def compare(S, r, vals):
        nonlocal agree, total, positives
        a = barrier.certified_by(S, r, vals.__getitem__, vals.__contains__)
        b = bench_radius.code_certified(S, r, vals)
        total += 1
        positives += a
        agree += a == b
        if a != b:
            raise AssertionError('the two certificates disagree: r={0} S={1}: exact {2}, PyMOSO {3}'.format(
                r, sorted(S)[:6], a, b))

    for w in widths:
        vals = plateau.values(w)
        E = plateau.efficient_set(w)
        cells = sorted({plateau.cell(x, w) for x in plateau.BOX})
        for r in radii:
            # known not certified: E less one of its cells (its points are
            # efficient, so undominated by the rest, and adjacent to the
            # next cell -- E less one point would not do: on a plateau the
            # point's tied neighbours in E weakly dominate it), and E with a
            # dominated point
            first = min(plateau.cell(x, w) for x in E)
            less_a_cell = {x for x in E if plateau.cell(x, w) != first}
            for S in (less_a_cell, set(E) | {(0, 0)} if (0, 0) not in E else set(E) | {(59, 59)}):
                if barrier.certified_by(S, r, vals.__getitem__, vals.__contains__):
                    raise AssertionError('certified a set known not to be: w={0} r={1}'.format(w, r))
                rejected_known += 1
                compare(S, r, vals)
            compare(E, r, vals)
            for x in rng.sample(plateau.BOX, extra):
                compare({x}, r, vals)
            if w > 1:
                for c in rng.sample(cells, min(len(cells), 6)):
                    compare(_cell_points(c, w), r, vals)
            for start in rng.sample(plateau.BOX, 4):
                compare(bench_radius._grown(vals, r, start), r, vals)
            for _ in range(4):
                compare(set(rng.sample(plateau.BOX, rng.randint(1, 6))), r, vals)
    if verbose:
        print('{0} of {1} sets: the exact certificate and PyMOSO\'s agree ({2} of them certified); {3} sets '
              'known not to be certified were rejected'.format(agree, total, positives, rejected_known))
    return agree, total, positives


def _mutants():
    from pymoso.moso import does_strict_dominate, does_weak_dominate, get_nbors, get_nondom
    real = barrier.certified_by

    def nbors_of(S, r):
        return set().union(*(get_nbors(s, r) for s in S)) - S

    def strict(S, r, f, feas):
        S = set(S)
        if not S or len(get_nondom({s: f(s) for s in S})) != len(S):
            return False
        z = (0,) * len(f(next(iter(S))))
        return all(any(does_strict_dominate(f(s), f(x), z, z) for s in S) for x in nbors_of(S, r) if feas(x))

    def ties_dominate(S, r, f, feas):
        # equal vectors treated as dominating each other: a set of tied
        # points is then never mutually non-dominated
        S = set(S)
        z = (0,) * len(f(next(iter(S)))) if S else ()
        if not S or any(a != b and does_weak_dominate(f(a), f(b), z, z) for a in S for b in S):
            return False
        return real(S, r, f, feas)

    def no_nondom(S, r, f, feas):
        S = set(S)
        if not S:
            return False
        z = (0,) * len(f(next(iter(S))))
        return all(any(does_weak_dominate(f(s), f(x), z, z) for s in S) for x in nbors_of(S, r) if feas(x))

    def radius_one(S, r, f, feas):
        return real(S, 1, f, feas)

    def outside_counts(S, r, f, feas):
        return real(S, r, f, lambda x: True) if all(feas(x) for x in nbors_of(set(S), r)) else False

    return [('strict instead of weak domination', strict), ('ties count as domination', ties_dominate),
            ('no non-dominated test', no_nondom), ('the radius ignored', radius_one),
            ('neighbours outside the box counted', outside_counts)]


def mutations(verbose=True, **kw):
    real = barrier.certified_by
    out = []
    for name, m in _mutants():
        barrier.certified_by = m
        try:
            verify(verbose=False, **kw)
            caught = False
        except (AssertionError, KeyError):
            caught = True
        finally:
            barrier.certified_by = real
        out.append((name, caught))
        if verbose:
            print('{0:40s} {1}'.format(name, 'caught' if caught else 'NOT CAUGHT'))
    return out


# ---- describe ----

def describe(out, widths=plateau.WIDTHS, radii=(1, 2, 3, 6, 10)):
    rows = []
    for w in widths:
        E = plateau.efficient_set(w)
        rows.append(dict(width=w, efficient=len(E), cells=len({plateau.cell(x, w) for x in E}),
                         ties_both=plateau.cross_cell_ties(w), ties_first=plateau.cross_cell_ties(w, 0),
                         traps={str(r): plateau.trap_count(w, r) for r in radii},
                         minima={str(r): plateau.trap_count(w, r, 0) for r in radii}))
    result = dict(box=len(plateau.BOX), rows=rows)
    with open(out, 'w') as f:
        json.dump(result, f, indent=1)
    return result


# ---- run ----

class Probe:
    """What the search did, from wrappers on the methods the solvers call
    (chnbase.RASolver.pli/spli/ne); restored on exit."""

    def __init__(self, w):
        self.w = w
        self.pli = 0
        self.pli_zero = 0
        self.moves = {('spli', 'true'): 0, ('spli', 'noise'): 0, ('ne', 'true'): 0, ('ne', 'noise'): 0,
                      ('ne', 'tie'): 0}
        self.cells = set()

    def _classify(self, kind, x, y, nobj):
        if y == x:
            return
        self.cells.add(plateau.cell(y, self.w))
        fx, fy = plateau.true_g(x, self.w)[nobj], plateau.true_g(y, self.w)[nobj]
        if kind == 'ne' and plateau.cell(x, self.w) == plateau.cell(y, self.w):
            self.moves[('ne', 'tie')] += 1
        self.moves[(kind, 'true' if fy < fx else 'noise')] += 1

    @contextlib.contextmanager
    def installed(self):
        probe = self
        real_pli, real_spli, real_ne = chnbase.RASolver.pli, chnbase.RASolver.spli, chnbase.RASolver.ne

        def pli(self, *a, **k):
            out = real_pli(self, *a, **k)
            probe.pli += 1
            if out[0] is not None and all(v == 0 for v in out[0]):
                probe.pli_zero += 1
            return out

        def spli(self, x0, fx0, sex0, e, nobj, *a, **k):
            out = real_spli(self, x0, fx0, sex0, e, nobj, *a, **k)
            probe._classify('spli', x0, out[0], nobj)
            return out

        def ne(self, x, fx, sex, nobj, *a, **k):
            out = real_ne(self, x, fx, sex, nobj, *a, **k)
            probe._classify('ne', x, out[0], nobj)
            return out

        chnbase.RASolver.pli, chnbase.RASolver.spli, chnbase.RASolver.ne = pli, spli, ne
        try:
            yield self
        finally:
            chnbase.RASolver.pli, chnbase.RASolver.spli, chnbase.RASolver.ne = real_pli, real_spli, real_ne


def quality(solver, w, soln, fmin):
    if solver == 'RSPLINE':
        return min(plateau.true_g(x, w)[0] for x in soln) - fmin
    return plateau.metric(soln, w)


class _Overshoot(Exception):
    pass


@contextlib.contextmanager
def _guard(limit, seen):
    """Stop a run whose next hit() would take it past `limit`
    replications in all: ExampleBnBSolver's replication count is set from
    the smallest gap between estimates and is not bounded by the budget,
    so one call can ask for millions. The largest request is recorded."""
    from pymoso.oracle import Oracle
    real_hit, real_many = Oracle.hit, Oracle.hit_many

    def hit(self, x, m, *a, **k):
        seen['largest'] = max(seen['largest'], m)
        if seen['replications'] + m > limit:
            raise _Overshoot()
        seen['replications'] += m
        return real_hit(self, x, m, *a, **k)

    def hit_many(self, requests, *a, **k):
        total = sum(r[1] for r in requests)
        seen['largest'] = max([seen['largest']] + [r[1] for r in requests])
        if seen['replications'] + total > limit:
            raise _Overshoot()
        seen['replications'] += total
        return real_many(self, requests, *a, **k)
    Oracle.hit, Oracle.hit_many = hit, hit_many
    try:
        yield
    finally:
        Oracle.hit, Oracle.hit_many = real_hit, real_many


def _caused_by_overshoot(e):
    while e is not None:
        if isinstance(e, _Overshoot):
            return True
        e = e.__cause__ or e.__context__
    return False


def run_one(solver, w, radius, arm, rep, budget=BUDGET, checkpoints=CHECKPOINTS, fmin=None):
    probe = Probe(w)
    cls = plateau.PROBLEMS['Plateau{0}'.format(w)]
    orcstream, solvstream = get_solv_prnstreams(seed_for(rep), mrg32k3a)
    orc = cls(orcstream)
    orc.set_crnflag(arm == 'crn')
    x0 = x0_for(rep)
    kwargs = dict(lb=0, ub=plateau.N) if solver == 'ExampleBnBSolver' else dict(radius=radius)
    seen = dict(largest=0, replications=0)
    base = dict(solver=solver, width=w, radius=radius, arm=arm, rep=rep, seed=list(seed_for(rep)), x0=list(x0),
                budget=budget)
    with probe.installed(), _guard(OVERSHOOT * budget, seen), contextlib.redirect_stdout(io.StringIO()), \
            orc.set_simpar(1):
        try:
            res = isp_run(SOLVERS[solver], budget, orc, solvprn=solvstream, x0=x0, **kwargs)
        except Exception as e:      # the guard, raised from hit() and re-wrapped on the way out
            if not _caused_by_overshoot(e):
                raise
            res = None
    base.update(finished=res is not None, largest_request=seen['largest'], replications=seen['replications'])
    if res is None:
        base.update(iterations=None, simcalls=None, quality={str(c): None for c in checkpoints}, final_size=None,
                    final_cells=None, pli=probe.pli, pli_zero=probe.pli_zero, cells_visited=len(probe.cells),
                    moves={'{0}_{1}'.format(*k): v for k, v in probe.moves.items()})
        return base
    iters = sorted(res['itersoln'])
    last = iters[-1]
    at = {}
    for c in checkpoints:
        done = [k for k in iters if res['simcalls'][k] <= c and k > 0 and res['itersoln'][k]]
        at[str(c)] = quality(solver, w, res['itersoln'][done[-1]], fmin) if done else None
    soln = res['itersoln'][last]
    return dict(base, iterations=last, simcalls=res['simcalls'][last], quality=at,
                final_size=len(soln), final_cells=len({plateau.cell(x, w) for x in soln}),
                pli=probe.pli, pli_zero=probe.pli_zero, cells_visited=len(probe.cells),
                moves={'{0}_{1}'.format(*k): v for k, v in probe.moves.items()})


def _key(r):
    return (r['solver'], r['width'], r['radius'], r['arm'], r['rep'])


def run(path, configs=CONFIGS, reps=REPS, budget=BUDGET, checkpoints=CHECKPOINTS, verbose=True):
    done = set()
    if os.path.exists(path):
        done = {_key(json.loads(line)) for line in open(path)}
    fmins = {w: plateau.first_objective_min(w) for w in plateau.WIDTHS}
    for solver, w, radius, arm in configs:
        for rep in range(reps):
            if (solver, w, radius, arm, rep) in done:
                continue
            t0 = time.perf_counter()
            row = run_one(solver, w, radius, arm, rep, budget, checkpoints, fmins[w])
            row.update(python=platform.python_version(), loadavg=(_loadavg() or [None])[0],
                       when=time.strftime('%Y-%m-%dT%H:%M:%S'))
            with open(path, 'a') as f:
                f.write(json.dumps(row) + '\n')
            if verbose:
                print(solver, w, radius, arm, rep, row['simcalls'], '{0:.1f}s'.format(time.perf_counter() - t0),
                      flush=True)


# ---- report ----

def report(path, describe_path, out):
    rows = [json.loads(line) for line in open(path)]
    desc = json.load(open(describe_path))
    med = statistics.median
    by = {}
    for r in rows:
        by.setdefault((r['solver'], r['radius'], r['arm']), {}).setdefault(r['width'], {})[r['rep']] = r
    cps = sorted({int(c) for r in rows for c in r['quality']})
    L = ['<!-- generated by docs/bench_plateau.py report; do not edit -->', '',
         'Runs: {0}, Python {1}, budget {2}.'.format(len(rows), sorted({r['python'] for r in rows}),
                                                    sorted({r['budget'] for r in rows})), '']
    L.extend(['### The problem: traps per width and radius', '',
              'A property of the problem alone, by enumeration on the true means ({0} points). Certified single '
              'points: sets of one point that PyMOSO\'s certificate would accept at that radius (the efficient '
              'set\'s own points included). First-objective local minima: points no neighbour within the radius '
              'is strictly better than, the traps of a single-objective search. Ties: pairs of points in '
              'different cells with equal true values.'.format(desc['box']), ''])
    radii = sorted(desc['rows'][0]['traps'], key=int)
    L.append('| width | efficient points | efficient cells | ties (both / first) | '
             + ' | '.join('certified singles r={0}'.format(r) for r in radii) + ' | '
             + ' | '.join('first-objective minima r={0}'.format(r) for r in radii) + ' |')
    L.append('|---|---|---|---|' + '---|' * (2 * len(radii)))
    for d in desc['rows']:
        L.append('| {0} | {1} | {2} | {3} / {4} | '.format(d['width'], d['efficient'], d['cells'], d['ties_both'],
                                                         d['ties_first'])
                 + ' | '.join('{0:,}'.format(d['traps'][r]) for r in radii) + ' | '
                 + ' | '.join('{0:,}'.format(d['minima'][r]) for r in radii) + ' |')
    L.append('')
    L.extend(['### Quality at matched counted simulations', '',
              'The tester-style metric (Hausdorff distance between the true images of the returned set and of the '
              'efficient set), or for R-SPLINE the gap to the true minimum of the first objective: lower is '
              'better. Median, then seeds better / same / worse than width 1 (the control, no plateaus) on the '
              'same seed, solver, radius and arm. "-": no iteration finished by that checkpoint.', ''])
    L.append('| solver | radius | arm | width | finished | ' + ' | '.join('at {0:,}'.format(c) for c in cps) + ' |')
    L.append('|---|---|---|---|---|' + '---|' * len(cps))
    ctrl_key = {}
    for (s, rad, arm), d in by.items():
        ctrl = by.get((s, 1 if rad is not None else None, arm), {}).get(1, {})
        for w in sorted(d):
            rs = d[w]
            cells = []
            for c in cps:
                k = str(c)
                vals = [rs[i]['quality'][k] for i in rs if rs[i]['quality'][k] is not None]
                if not vals:
                    cells.append('-')
                    continue
                if w == 1:
                    cells.append('{0:.3g}'.format(med(vals)))
                    continue
                pairs = [(rs[i]['quality'][k], ctrl[i]['quality'][k]) for i in rs
                         if i in ctrl and rs[i]['quality'][k] is not None and ctrl[i]['quality'][k] is not None]
                b = sum(x < y for x, y in pairs)
                e = sum(x == y for x, y in pairs)
                cells.append('{0:.3g} ({1}/{2}/{3})'.format(med(vals), b, e, len(pairs) - b - e))
            L.append('| {0} | {1} | {2} | {3} | {4}/{5} | '.format(
                s, '-' if rad is None else rad, arm, w, sum(r['finished'] for r in rs.values()), len(rs))
                + ' | '.join(cells) + ' |')
    L.append('')
    bnb = [r for r in rows if r['solver'] == 'ExampleBnBSolver']
    if bnb:
        L.extend(['### ExampleBnBSolver: the replications it asks for', '',
                  'A run is stopped when its next hit() would take it past {0}x its budget in replications. '
                  'The largest single request (replications per point) and the replications run before the '
                  'stop, medians over seeds.'.format(OVERSHOOT), ''])
        L.append('| width | finished | largest request | replications run | budget |')
        L.append('|---|---|---|---|---|')
        for w in sorted({r['width'] for r in bnb}):
            rs = [r for r in bnb if r['width'] == w]
            L.append('| {0} | {1}/{2} | {3:,.0f} | {4:,.0f} | {5:,} |'.format(
                w, sum(r['finished'] for r in rs), len(rs), med(r['largest_request'] for r in rs),
                med(r['replications'] for r in rs), rs[0]['budget']))
        L.append('')
    L.extend(['### What the search does on a plateau', '',
              'Per run, medians over seeds (sums of moves over all seeds in brackets). PLI calls, and the share whose '
              'pseudo-gradient was exactly zero. Moves by SPLI and by NE that lowered the true value of the '
              'objective being searched ("true") against moves that lowered only its estimate ("noise"); NE moves '
              'to a point of the same cell, a true tie. Distinct cells the search moved into, and cells in the '
              'final returned set. Not for ExampleBnBSolver, which has no PLI, SPLI or NE.', ''])
    L.append('| solver | radius | arm | width | PLI calls | gradient exactly 0 | SPLI true / noise | NE true / noise | '
             'NE within a cell | cells visited | final cells |')
    L.append('|---|---|---|---|---|---|---|---|---|---|---|')
    for (s, rad, arm), d in by.items():
        if s == 'ExampleBnBSolver':
            continue
        for w in sorted(d):
            rs = list(d[w].values())
            tot = {k: sum(r['moves'][k] for r in rs) for k in rs[0]['moves']}
            L.append('| {0} | {1} | {2} | {3} | {4:.0f} | {5:.0%} | {6} / {7} | {8} / {9} | {10} | {11:.0f} | {12:.0f} |'.format(
                s, rad, arm, w, med(r['pli'] for r in rs),
                sum(r['pli_zero'] for r in rs) / max(1, sum(r['pli'] for r in rs)),
                tot['spli_true'], tot['spli_noise'], tot['ne_true'], tot['ne_noise'], tot['ne_tie'],
                med(r['cells_visited'] for r in rs), med(r['final_cells'] for r in rs)))
    with open(out, 'w') as f:
        f.write('\n'.join(L) + '\n')


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else ''
    if cmd == 'verify':
        verify()
    elif cmd == 'mutations':
        mutations()
    elif cmd == 'describe':
        describe(sys.argv[2])
    elif cmd == 'run':
        run(sys.argv[2])
    elif cmd == 'report':
        report(sys.argv[2], sys.argv[3], sys.argv[4])
    else:
        raise SystemExit(__doc__)
