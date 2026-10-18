#!/usr/bin/env python
"""
Regenerates docs/neighbourhood-radius.md's measurements: what a larger
neighbourhood radius buys and costs (docs/phase7-plan.md, step 5b).

    python docs/bench_radius.py verify             # the barrier's known answer, checked
    python docs/bench_radius.py nbors  OUT.json    # get_nbors construction, timed
    python docs/bench_radius.py run    OUT.jsonl   # the solver runs (counted)
    python docs/bench_radius.py report OUT.jsonl NBORS.json OUT.md

The subject is the barrier problem (scratch/phase7/barrier.py): a trap
certified at radius r exactly when r <= t, for an annulus t cells thick.
Does a radius above the thickness escape it, at a cost that reaches the
matched checkpoints at all? The built-in test problems are the control.

`verify` holds the exact certificate (barrier.certified_by) to PyMOSO's
own as RLESolver.rle applies it (a non-dominated set, and get_ncn on
exact values planted with zero standard errors finding nothing), on the
barrier's E, T and other sets at radii 1-5 and on random small tables
of integer values, where ties and certified sets other than the
efficient set are common; and checks it rejects sets known not to be
certified.

`nbors` times moso.get_nbors on its own: construction, which the
pruning argument leaves as the one part of the neighbourhood's cost
that could be made cheaper. A quiet machine; the load is recorded.

`run` counts. Per run: counted simulations and g() calls (an infeasible
point's replications count only in the second), the points estimated
for certification (get_ncn and remove_nlwep), quality at matched counted
simulations (the last RA iteration at or under each checkpoint), and
for the barrier the share of the returned set inside the annulus and
whether that set is certified on the true means at the run's radius.
The time spent constructing neighbourhoods and the time spent
estimating are recorded as two separate lines (wall time, under timing
wrappers, so shares rather than absolute costs). A run that reaches
OVERSHOOT times its budget in g() calls is stopped and recorded as not
finished: a cost result (KNOWN_ISSUES.md issue 16), not missing data.
`run` appends one JSON line per run and skips runs already in the file.

tests/test_benchmark_scripts.py only checks that the script runs.
"""
import contextlib
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

from pymoso import chnbase, moso  # noqa: E402
from pymoso.layout import get_solv_prnstreams  # noqa: E402
from pymoso.paths import isp_run  # noqa: E402
from pymoso.prng import mrg32k3a  # noqa: E402
from pymoso.problems.probsimpleso import ProbSimpleSO  # noqa: E402
from pymoso.problems.probtpa import ProbTPA  # noqa: E402
from pymoso.problems.probtpb import ProbTPB  # noqa: E402
from pymoso.problems.probtpc import ProbTPC  # noqa: E402
from pymoso.solvers.rminrle import RMINRLE  # noqa: E402
from pymoso.solvers.rpe import RPE  # noqa: E402
from pymoso.solvers.rperle import RPERLE  # noqa: E402
from pymoso.solvers.rspline import RSPLINE  # noqa: E402
from pymoso.testers import simplesotester, tpatester, tpbtester, tpctester  # noqa: E402

RADII = (1, 2, 3, 4, 5)
BUDGET = 20000
CHECKPOINTS = (1000, 5000, 20000)
OVERSHOOT = 50
SEEDS = {'subject': 20, 'control': 10}
SOLVERS = {'RSPLINE': RSPLINE, 'RPERLE': RPERLE, 'RPE': RPE, 'RMINRLE': RMINRLE}
CONTROL = {
    'ProbSimpleSO': (ProbSimpleSO, simplesotester, [range(-100, 101)]),
    'ProbTPA': (ProbTPA, tpatester, [range(0, 51)] * 2),
    'ProbTPB': (ProbTPB, tpbtester, [range(0, 101)] * 2),
    'ProbTPC': (ProbTPC, tpctester, [range(-10, 11)] * 3),
}
TESTERS = {'ProbSimpleSO': simplesotester.SimpleSOTester, 'ProbTPA': tpatester.TPATester,
           'ProbTPB': tpbtester.TPBTester, 'ProbTPC': tpctester.TPCTester}
SUBJECT = ('Barrier1', 'Barrier2')
PAIRS = ([('RSPLINE', p) for p in SUBJECT] + [(s, p) for s in ('RPERLE', 'RPE', 'RMINRLE') for p in SUBJECT]
         + [('RSPLINE', p) for p in CONTROL]
         + [(s, p) for s in ('RPERLE', 'RPE', 'RMINRLE') for p in ('ProbTPA', 'ProbTPB', 'ProbTPC')])


def _loadavg():
    """The load averages where the platform has them (not Windows)."""
    try:
        return os.getloadavg()
    except (AttributeError, OSError):
        return None


def seed_for(rep):
    return (1000 + rep,) * 6


def thickness(problem):
    return barrier.PROBLEMS[problem].THICKNESS


def problem_class(problem):
    return barrier.PROBLEMS[problem] if problem in SUBJECT else CONTROL[problem][0]


def x0_for(problem, rep):
    rng = random.Random(rep)
    if problem in SUBJECT:
        return barrier.get_ranx0(rng, thickness(problem))
    return CONTROL[problem][1].get_ranx0(rng)


def first_min(problem):
    import itertools
    if problem in SUBJECT:
        return barrier.first_objective_min(thickness(problem))
    _, tester, box = CONTROL[problem]
    return min(tester.true_g(x)[0] for x in itertools.product(*box))


def quality(solver, problem, soln, fmin):
    if problem in SUBJECT:
        t = thickness(problem)
        if solver == 'RSPLINE':
            return min(barrier.true_g(x, t)[0] for x in soln) - fmin
        return barrier.metric(soln, t)
    if solver == 'RSPLINE':
        return min(CONTROL[problem][1].true_g(x)[0] for x in soln) - fmin
    return TESTERS[problem]().metric(soln)


# ---- verify ----

class _Table(chnbase.Oracle):
    """An oracle whose g is a table of exact values, for `verify`."""
    TABLE = {}
    NUM_OBJ = 2

    def __init__(self, rng):
        self.num_obj = self.NUM_OBJ
        self.dim = 2
        super().__init__(rng)

    def g(self, x, rng):
        if x not in self.TABLE:
            return False, ()
        return True, self.TABLE[x]


def code_certified(S, r, table):
    """
    PyMOSO's own certificate on exact values, zero standard errors, as
    RLESolver.rle applies it: the set is its own non-dominated subset
    (rle passes get_ncn only get_nondom's output) and get_ncn finds no
    non-conforming neighbour. That every member is then locally weakly
    efficient follows: a neighbour strictly dominating a member is
    non-conforming by part (a). A point not in the table is infeasible.
    """
    S = set(S)
    if set(moso.get_nondom({x: table[x] for x in S})) != S:
        return False
    cls = type('Table', (_Table,), {'TABLE': table})
    orcstream, solvstream = get_solv_prnstreams(seed_for(0), mrg32k3a)
    orc = cls(orcstream)
    orc.set_crnflag(False)
    with orc.set_simpar(1):
        solver = RMINRLE(orc, sprn=solvstream, x0=next(iter(S)), radius=r)
        solver.m = 1
        solver.gbar = dict(table)
        solver.sehat = {x: (0.0, 0.0) for x in table}
        return not solver.get_ncn(S)


def _grown(table, r, start):
    """A set grown from `start` by adding undominated neighbours until
    none is left: such sets are often certified, so the comparison has
    positives, not only rejections."""
    S = {start}
    zero = (0, 0)
    for _ in range(50):
        nbors = set().union(*(moso.get_nbors(s, r) for s in S)) - S
        add = [x for x in nbors if x in table
               and not any(moso.does_weak_dominate(table[s], table[x], zero, zero) for s in S)]
        if not add:
            break
        S = set(moso.get_nondom({x: table[x] for x in S | set(add)}))
    return S


def verify(radii=RADII, thicknesses=(1, 2), extra=60, random_tables=40, seed=7, verbose=True):
    """
    The exact certificate (barrier.certified_by) against PyMOSO's own,
    on the barrier's true means and on random small tables of integer
    values, where ties between points and certified sets other than the
    efficient set are common. Raises on any disagreement, and if a set
    known not to be certified is passed.
    """
    rng = random.Random(seed)
    agree = total = positives = rejected_known = 0
    table = {}

    def compare(S, r, values):
        nonlocal agree, total, positives
        a = barrier.certified_by(S, r, values.__getitem__, values.__contains__)
        b = code_certified(S, r, values)
        total += 1
        positives += a
        agree += a == b
        if a != b:
            raise AssertionError('the two certificates disagree: r={0} S={1}: exact {2}, PyMOSO {3}'.format(
                r, sorted(S), a, b))

    for t in thicknesses:
        values = {x: barrier.true_g(x, t) for x in barrier.BOX}
        E, T = barrier.efficient_set(t), barrier.trap(t)
        for r in radii:
            table[(t, r)] = (barrier.certified(E, r, t), barrier.certified(T, r, t))
            # known not certified: a proper subset of E (its other members
            # are undominated neighbours), and E with a dominated point added
            for S in (set(list(E)[:5]), set(E) | {(0, 0)}):
                if barrier.certified(S, r, t):
                    raise AssertionError('certified a set known not to be: t={0} r={1}'.format(t, r))
                rejected_known += 1
                compare(S, r, values)
            compare(E, r, values)
            compare(T, r, values)
            pool = list(E) + list(T) + rng.sample(barrier.BOX, 30)
            for _ in range(extra):
                compare(set(rng.sample(pool, rng.randint(1, 8))), r, values)
    for _ in range(random_tables):
        box = [x for x in itertools.product(range(6), repeat=2)]
        values = {x: (rng.randint(0, 3), rng.randint(0, 3)) for x in box}
        for r in (1, 2, 3):
            for start in rng.sample(box, 6):
                compare(_grown(values, r, start), r, values)
            for _ in range(4):
                compare(set(rng.sample(box, rng.randint(1, 6))), r, values)
    if verbose:
        for (t, r), (e, tr) in sorted(table.items()):
            print('thickness {0} radius {1}: E certified {2}, T certified {3}'.format(t, r, e, tr))
        print('{0} of {1} sets: the exact certificate and PyMOSO\'s agree ({2} of them certified); {3} sets '
              'known not to be certified were rejected'.format(agree, total, positives, rejected_known))
    return table, agree, total, positives


# ---- nbors (timed) ----

def nbors(out, radii=RADII, dims=(1, 2, 3), repeats=300):
    rows = []
    load = _loadavg()
    for d in dims:
        x = (7,) * d
        for r in radii:
            n = len(moso.get_nbors(x, r))
            t0 = time.perf_counter()
            for _ in range(repeats):
                moso.get_nbors(x, r)
            us = (time.perf_counter() - t0) / repeats * 1e6
            rows.append(dict(dim=d, radius=r, points=n, us_per_call=us, us_per_point=us / n))
    result = dict(python=platform.python_version(), loadavg_before=load, loadavg_after=_loadavg(),
                  rows=rows)
    with open(out, 'w') as f:
        json.dump(result, f, indent=1)
    return result


# ---- run (counted) ----

class _Overshoot(Exception):
    pass


class Probe:
    def __init__(self, limit):
        self.limit = limit
        self.g_calls = 0
        self.nbors_s = 0.0
        self.estimate_s = 0.0
        self.cert_points = 0
        self.in_cert = 0
        self.est_depth = 0

    @contextlib.contextmanager
    def installed(self):
        probe = self
        saved = [(chnbase, 'get_nbors'), (moso, 'get_nbors'),
                 (chnbase.RASolver, 'estimate'), (chnbase.RASolver, 'estimate_many'),
                 (chnbase.RASolver, 'remove_nlwep'), (chnbase.RLESolver, 'get_ncn')]
        saved = [(o, n, getattr(o, n)) for o, n in saved]
        real_nb_c, real_nb_m = chnbase.get_nbors, moso.get_nbors

        def timed_nbors(real):
            def f(*a, **k):
                t0 = time.perf_counter()
                try:
                    return real(*a, **k)
                finally:
                    probe.nbors_s += time.perf_counter() - t0
            return f

        def timed_est(real, many):
            def f(self, *a, **k):
                if probe.in_cert:
                    probe.cert_points += len(a[0]) if many else 1
                probe.est_depth += 1
                t0 = time.perf_counter()
                try:
                    return real(self, *a, **k)
                finally:
                    probe.est_depth -= 1
                    if not probe.est_depth:
                        probe.estimate_s += time.perf_counter() - t0
            return f

        def cert(real):
            def f(self, *a, **k):
                probe.in_cert += 1
                try:
                    return real(self, *a, **k)
                finally:
                    probe.in_cert -= 1
            return f

        chnbase.get_nbors = timed_nbors(real_nb_c)
        moso.get_nbors = timed_nbors(real_nb_m)
        chnbase.RASolver.estimate = timed_est(saved[2][2], False)
        chnbase.RASolver.estimate_many = timed_est(saved[3][2], True)
        chnbase.RASolver.remove_nlwep = cert(saved[4][2])
        chnbase.RLESolver.get_ncn = cert(saved[5][2])
        try:
            yield self
        finally:
            for o, n, v in saved:
                setattr(o, n, v)


def counted_problem(cls, probe):
    class Counted(cls):
        def g(self, x, rng):
            probe.g_calls += 1
            if probe.g_calls > probe.limit:
                raise _Overshoot()
            return super().g(x, rng)
    Counted.__name__ = cls.__name__
    return Counted


def _caused_by_overshoot(e):
    while e is not None:
        if isinstance(e, _Overshoot):
            return True
        e = e.__cause__ or e.__context__
    return False


def run_one(solver, problem, radius, rep, budget=BUDGET, checkpoints=CHECKPOINTS, fmin=None):
    probe = Probe(OVERSHOOT * budget)
    cls = counted_problem(problem_class(problem), probe)
    orcstream, solvstream = get_solv_prnstreams(seed_for(rep), mrg32k3a)
    orc = cls(orcstream)
    orc.set_crnflag(False)
    x0 = x0_for(problem, rep)
    finished = True
    res = None
    t0 = time.perf_counter()
    with probe.installed(), contextlib.redirect_stdout(io.StringIO()), orc.set_simpar(1):
        try:
            res = isp_run(SOLVERS[solver], budget, orc, solvprn=solvstream, x0=x0, radius=radius)
        except Exception as e:      # the guard, raised from g() and re-wrapped on the way out
            if not _caused_by_overshoot(e):
                raise
            finished = False
    wall = time.perf_counter() - t0
    row = dict(solver=solver, problem=problem, radius=radius, rep=rep, seed=list(seed_for(rep)), x0=list(x0),
               budget=budget, finished=finished, g_calls=probe.g_calls, cert_points=probe.cert_points,
               nbors_s=probe.nbors_s, estimate_s=probe.estimate_s, wall=wall)
    if res is None:
        row.update(iterations=None, simcalls=None, quality={str(c): None for c in checkpoints},
                   final_size=None)
        return row
    iters = sorted(res['itersoln'])
    last = iters[-1]
    row.update(iterations=last, simcalls=res['simcalls'][last], final_size=len(res['itersoln'][last]))
    at = {}
    for c in checkpoints:
        done = [k for k in iters if res['simcalls'][k] <= c and k > 0]
        at[str(c)] = quality(solver, problem, res['itersoln'][done[-1]], fmin) if done else None
    row['quality'] = at
    if problem in SUBJECT:
        t = thickness(problem)
        soln = res['itersoln'][last]
        row['inside'] = sum(barrier.linf(x) < barrier.RHO for x in soln) / len(soln)
        if solver == 'RSPLINE':
            x = next(iter(soln))
            row['certified'] = all(barrier.true_g(n, t)[0] >= barrier.true_g(x, t)[0]
                                   for n in moso.get_nbors(x, radius) if barrier.in_box(n))
        else:
            row['certified'] = barrier.certified(soln, radius, t)
    return row


def _done(path):
    done = set()
    if os.path.exists(path):
        for line in open(path):
            r = json.loads(line)
            done.add((r['solver'], r['problem'], r['radius'], r['rep']))
    return done


def run(path, pairs=PAIRS, radii=RADII, seeds=SEEDS, budget=BUDGET, checkpoints=CHECKPOINTS, verbose=True):
    done = _done(path)
    fmins = {}
    for solver, problem in pairs:
        if solver == 'RSPLINE' and problem not in fmins:
            fmins[problem] = first_min(problem)
        reps = seeds['subject' if problem in SUBJECT else 'control']
        for rep in range(reps):
            for radius in radii:
                if (solver, problem, radius, rep) in done:
                    continue
                row = run_one(solver, problem, radius, rep, budget, checkpoints, fmins.get(problem))
                row.update(python=platform.python_version(), loadavg=(_loadavg() or [None])[0],
                           when=time.strftime('%Y-%m-%dT%H:%M:%S'))
                with open(path, 'a') as f:
                    f.write(json.dumps(row) + '\n')
                if verbose:
                    print(solver, problem, radius, rep, 'finished' if row['finished'] else 'STOPPED',
                          row['g_calls'], '{0:.1f}s'.format(row['wall']), flush=True)


# ---- report ----

def _fmt(v, spec='{0:.3g}'):
    return '-' if v is None else spec.format(v)


def report(path, nbors_path, out):
    rows = [json.loads(line) for line in open(path)]
    nb = json.load(open(nbors_path))
    med = statistics.median
    by = {}
    for r in rows:
        by.setdefault((r['solver'], r['problem']), {}).setdefault(r['radius'], {})[r['rep']] = r
    cps = sorted({int(c) for r in rows for c in r['quality']})
    L = ['<!-- generated by docs/bench_radius.py report; do not edit -->', '',
         'Runs: {0}, Python {1}, budget {2}, a run stopped at {3}x its budget in g() calls.'.format(
             len(rows), sorted({r['python'] for r in rows}), sorted({r['budget'] for r in rows}), OVERSHOOT), '']

    def quality_table(problems, title):
        L.extend(['### ' + title, '',
                  'Quality at matched counted simulations: the median, then how many seeds did better / the same / '
                  'worse than radius 1 on the same seed. "-": no seed finished an RA iteration by that checkpoint '
                  '(a stopped run counts only up to where it stopped). Barrier rows add the median share of the '
                  'returned set inside the annulus and the share of runs whose returned set is certified on the '
                  'true means at their own radius.', ''])
        hdr = '| solver | problem | radius | finished | ' + ' | '.join('at {0:,}'.format(c) for c in cps)
        if problems == SUBJECT:
            hdr += ' | inside | certified'
        L.append(hdr + ' |')
        L.append('|---|---|---|---|' + '---|' * len(cps) + ('---|---|' if problems == SUBJECT else ''))
        for (s, p), d in by.items():
            if p not in problems:
                continue
            ref = d.get(1, {})
            for radius in sorted(d):
                rs = d[radius]
                cells = []
                for c in cps:
                    k = str(c)
                    vals = [rs[i]['quality'][k] for i in rs if rs[i]['quality'][k] is not None]
                    if not vals:
                        cells.append('-')
                        continue
                    if radius == 1:
                        cells.append('{0:.3g}'.format(med(vals)))
                        continue
                    pairs = [(rs[i]['quality'][k], ref[i]['quality'][k]) for i in rs
                             if i in ref and rs[i]['quality'][k] is not None and ref[i]['quality'][k] is not None]
                    better = sum(a < b for a, b in pairs)
                    same = sum(a == b for a, b in pairs)
                    cells.append('{0:.3g} ({1}/{2}/{3})'.format(med(vals), better, same, len(pairs) - better - same))
                line = '| {0} | {1} | {2} | {3}/{4} | '.format(s, p, radius, sum(r['finished'] for r in rs.values()),
                                                              len(rs)) + ' | '.join(cells)
                if problems == SUBJECT:
                    fin = [r for r in rs.values() if r.get('inside') is not None]
                    line += ' | {0} | {1}'.format(
                        _fmt(med(r['inside'] for r in fin), '{0:.0%}') if fin else '-',
                        '{0:.0%}'.format(sum(r['certified'] for r in fin) / len(fin)) if fin else '-')
                L.append(line + ' |')
        L.append('')

    quality_table(SUBJECT, 'Does a radius above 1 escape the barrier?')

    L.extend(['### How the cost scales with radius', '',
              'Construction: moso.get_nbors timed on its own (`nbors`), microseconds. Then, per run (medians over '
              'seeds, finished runs and stopped ones alike): points estimated for certification, g() calls, the '
              'returned set\'s size, simulations per returned point (counted simulations over the final set\'s '
              'size, finished runs only), and wall time split into constructing neighbourhoods and estimating '
              '(under timing wrappers: shares, not absolute costs).', ''])
    if nb['loadavg_before'] and nb['loadavg_after']:
        L.append('Python {0}, load {1:.2f} before and {2:.2f} after.'.format(
            nb['python'], nb['loadavg_before'][0], nb['loadavg_after'][0]))
    else:
        L.append('Python {0}, load not recorded (no os.getloadavg on this platform).'.format(nb['python']))
    L.append('')
    L.append('| dim | radius | points | µs per call | µs per point |')
    L.append('|---|---|---|---|---|')
    for r in nb['rows']:
        L.append('| {0} | {1} | {2} | {3:,.1f} | {4:.2f} |'.format(r['dim'], r['radius'], r['points'],
                                                                 r['us_per_call'], r['us_per_point']))
    L.append('')
    L.append('| solver | problem | radius | finished | cert. points | g() calls | final size | sims per point | '
             'construct s | estimate s | construct share |')
    L.append('|---|---|---|---|---|---|---|---|---|---|---|')
    for (s, p), d in by.items():
        for radius in sorted(d):
            rs = list(d[radius].values())
            fin = [r for r in rs if r['finished'] and r['final_size']]
            L.append('| {0} | {1} | {2} | {3}/{4} | {5:,.0f} | {6:,.0f} | {7} | {8} | {9:.3f} | {10:.2f} | {11:.1%} |'.format(
                s, p, radius, len(fin), len(rs), med(r['cert_points'] for r in rs), med(r['g_calls'] for r in rs),
                _fmt(med(r['final_size'] for r in fin) if fin else None, '{0:.0f}'),
                _fmt(med(r['simcalls'] / r['final_size'] for r in fin) if fin else None, '{0:,.0f}'),
                med(r['nbors_s'] for r in rs), med(r['estimate_s'] for r in rs),
                med(r['nbors_s'] / r['wall'] for r in rs if r['wall'])))
    L.append('')
    quality_table(tuple(CONTROL), 'The control: the built-in test problems')
    with open(out, 'w') as f:
        f.write('\n'.join(L) + '\n')


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else ''
    if cmd == 'verify':
        verify()
    elif cmd == 'nbors':
        nbors(sys.argv[2])
    elif cmd == 'run':
        run(sys.argv[2])
    elif cmd == 'report':
        report(sys.argv[2], sys.argv[3], sys.argv[4])
    else:
        raise SystemExit(__doc__)
