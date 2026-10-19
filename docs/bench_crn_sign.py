#!/usr/bin/env python
"""
Regenerates docs/crn-failure.md's measurements of the covariance's
sign: whether a threshold, a conservation or an antithetic structure
makes CRN's correlation between neighbours negative
(docs/phase7-plan.md, step 6b, part 3).

    python docs/bench_crn_sign.py verify               # Route's known answer, checked
    python docs/bench_crn_sign.py mutations            # ... and every check shown to detect
    python docs/bench_crn_sign.py covariance OUT.json  # measured against exact (counted, not timed)
    python docs/bench_crn_sign.py run RUNS.jsonl [WORKERS]   # the solvers (counted)
    python docs/bench_crn_sign.py report OUT.json OUT.md [RUNS.jsonl]

The problems are scratch/phase7/crnsign.py: Route (a routing threshold,
services shared after the branch), Split (a fixed total split between
substitutes by one shared draw; exact only), and Antithetic
(crnsync.SyncFixed reading u as 1 - u at odd points: artificial).

Every problem here is synchronized and its periods are i.i.d., so each
pair's correlation has an exact value (crnsign: route_rho, split_rho,
inventory_rho) at any number of periods. The measurement is
docs/bench_crn.py's (one hit(x, R) per point through the real Oracle
and executor, replication j paired with replication j), and
`covariance` holds every measured pair to its exact value -- under CRN
the exact correlation, without it 0 -- in Fisher z with a jackknife
standard error (the data are not normal; a normal-theory error put
SyncFixed's largest |z| at 4.1), or the normal-theory one where the
jackknife is undefined (a correlation within one replication of 1). `verify` holds Route's exact
certificate to PyMOSO's own; `mutations` shows each check failing on a
wrong measurement, a wrong closed form, a wrong exact correlation and
wrong certificates.

tests/test_benchmark_scripts.py only checks that the script runs.
"""
import contextlib
import importlib.util
import itertools
import json
import math
import pathlib
import platform
import random
import statistics
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scratch' / 'phase7'))
import barrier  # noqa: E402
import crnsign  # noqa: E402
import crnsync  # noqa: E402


def _load(name):
    spec = importlib.util.spec_from_file_location(name, str(ROOT / 'docs' / '{0}.py'.format(name)))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


bench_crn = _load('bench_crn')
bench_radius = bench_crn.bench_radius
bench_plateau = bench_crn.bench_plateau

from pymoso import moso  # noqa: E402
from pymoso.layout import get_solv_prnstreams  # noqa: E402
from pymoso.prng import mrg32k3a  # noqa: E402

SEED = bench_crn.SEED
ARMS = bench_crn.ARMS
TOL = 4.5


def _inv_exact(x, y):
    return crnsign.inventory_rho(x, y, False, False)


# name: (class, exact CRN correlation, box, inside)
MEASURED = {
    'Route': (crnsign.Route, crnsign.route_rho, crnsign.ROUTE_BOX, crnsign.route_in_box),
    'Antithetic': (crnsign.Antithetic, crnsign.inventory_rho, crnsync.BOX, crnsync.in_box),
    'SyncFixed': (crnsync.SyncFixed, _inv_exact, crnsync.BOX, crnsync.in_box),
}


# ---- the measurement against exact ----

def jack_z(a, b):
    """(atanh r, its standard error, which): the jackknife error, or the
    normal-theory 1 / sqrt(n - 3) when leaving one replication out makes
    |r| 1 (a correlation within a few discordant replications of 1).
    None when either is constant or |r| is 1."""
    n = len(a)
    sx, sy = math.fsum(a), math.fsum(b)
    sxx = math.fsum(v * v for v in a)
    syy = math.fsum(v * v for v in b)
    sxy = math.fsum(p * q for p, q in zip(a, b))

    def z(m, sx, sy, sxx, syy, sxy):
        vx, vy = sxx - sx * sx / m, syy - sy * sy / m
        if vx <= 0 or vy <= 0:
            return None
        r = (sxy - sx * sy / m) / math.sqrt(vx * vy)
        return None if abs(r) >= 1 else math.atanh(r)
    full = z(n, sx, sy, sxx, syy, sxy)
    if full is None:
        return None
    loo = [z(n - 1, sx - p, sy - q, sxx - p * p, syy - q * q, sxy - p * q) for p, q in zip(a, b)]
    if any(v is None for v in loo):
        return full, 1 / math.sqrt(n - 3), 'normal'
    m = statistics.fmean(loo)
    return full, math.sqrt((n - 1) / n * math.fsum((v - m) ** 2 for v in loo)), 'jackknife'


def check_pairs(name, s, pairs, crn, exact=None, mutation=None, tol=TOL):
    """
    Each pair's measured correlation per objective against its exact
    value (0 without CRN). Raises on any beyond `tol` jackknife standard
    errors in Fisher z, on an exact correlation of +-1 not reproduced to
    rounding, and on a constant objective that is not constant in both.
    Returns the rows.
    """
    exact = MEASURED[name][1] if exact is None else exact
    rows = []
    for x, y, i in pairs:
        sx, sy = s[x], s[y]
        if mutation == 'shift':
            sy = sy[1:] + sy[:1]
        stats, differ = bench_crn.pair_stats(sx, sy, 'pooled' if mutation == 'pooled' else None)
        want = exact(x, y)
        zs, se_kind = [], []
        for k, (r, lo, hi, vr) in enumerate(stats):
            w = want[k]
            if w is None:
                if r is not None:
                    raise AssertionError('{0} {1}->{2} objective {3}: exactly constant, measured rho {4}'.format(
                        name, x, y, k, r))
                zs.append(None)
                se_kind.append(None)
                continue
            w = w if crn else 0.0
            if abs(w) > 1 - 1e-12:
                if r is None or abs(r - w) > 1e-6:
                    raise AssertionError('{0} {1}->{2} objective {3}: exact {4}, measured {5}'.format(
                        name, x, y, k, w, r))
                zs.append(0.0)
                se_kind.append('exact')
                continue
            a = [t[0][k] for t in sx]
            b = [t[0][k] for t in sy]
            if mutation == 'pooled':
                a = [t[0][j] for t in sx for j in range(len(want))]
                b = [t[0][j] for t in sy for j in range(len(want))]
            jz = jack_z(a, b)
            zv = math.inf if jz is None else (jz[0] - math.atanh(w)) / jz[1]
            if abs(zv) > tol:
                raise AssertionError('{0} crn={1} {2}->{3} objective {4}: rho {5}, exact {6}, z {7:.2f}'.format(
                    name, crn, x, y, k, r, w, zv))
            zs.append(zv)
            se_kind.append(None if jz is None else jz[2])
        rows.append(dict(problem=name, arm='crn' if crn else 'default', x=list(x), y=list(y), axis=i,
                         exact=[None if w is None else (w if crn else 0.0) for w in want], z=zs, se=se_kind,
                         **bench_crn._summ(stats, differ)))
    return rows


def lattice(name, reps, points=None, crn=True, mutation=None, exact=None):
    cls, _, box, inside = MEASURED[name]
    points = box if points is None else points
    pairs = bench_crn.axis_pairs(points, inside)
    sampled = sorted({p for x, y, _ in pairs for p in (x, y)})
    s = bench_crn.samples(cls, sampled, reps, crn and mutation != 'nocrn')
    return check_pairs(name, s, pairs, crn, exact, mutation), s


def route_marginals(s, true_g=crnsign.true_route_g, tol=TOL):
    """Route's per-point means without CRN against the closed form;
    raises beyond `tol`. Returns the largest |z|."""
    worst = 0.0
    for x, reps in s.items():
        for k in range(2):
            a = [t[0][k] for t in reps]
            v = statistics.variance(a)
            mu = true_g(x)[k]
            if v == 0:
                if statistics.fmean(a) != mu:
                    raise AssertionError('{0} objective {1}: constant {2}, closed form {3}'.format(
                        x, k, a[0], mu))
                continue
            z = (statistics.fmean(a) - mu) / math.sqrt(v / len(a))
            worst = max(worst, abs(z))
    if worst > tol:
        raise AssertionError('Route against its closed form: |z| = {0:.2f}'.format(worst))
    return worst


# ---- verify: Route's known answer ----

def verify(radii=(1, 2, 3), extra=20, random_tables=20, seed=13, verbose=True):
    """Route's exact certificate against PyMOSO's own on its true means,
    as docs/bench_crn.py's verify; raises on a disagreement and if a
    set known not to be certified passes."""
    rng = random.Random(seed)
    vals = crnsign.route_values()
    E = crnsign.route_efficient_set()
    agree = total = positives = rejected = 0

    def compare(S, r, table=vals):
        nonlocal agree, total, positives
        a = barrier.certified_by(S, r, table.__getitem__, table.__contains__)
        b = bench_radius.code_certified(S, r, table)
        total += 1
        positives += a
        agree += a == b
        if a != b:
            raise AssertionError('the two certificates disagree: r={0} S={1}: exact {2}, PyMOSO {3}'.format(
                r, sorted(S)[:6], a, b))

    near = [x for x in crnsign.ROUTE_BOX if x not in E and any(
        abs(x[0] - e[0]) + abs(x[1] - e[1]) == 1 for e in E)]
    for r in radii:
        # known not certified: E with a dominated point next to it, and
        # E less a point (each efficient point is non-dominated, and in
        # the neighbourhood of its efficient neighbours)
        known = [set(E) | {near[0]}] + [set(E) - {x} for x in sorted(E)[:3]]
        for S in known:
            if barrier.certified_by(S, r, vals.__getitem__, vals.__contains__):
                raise AssertionError('certified a set known not to be: r={0}'.format(r))
            rejected += 1
            compare(S, r)
        compare(E, r)
        for x in rng.sample(crnsign.ROUTE_BOX, extra):
            compare({x}, r)
        for x in rng.sample(sorted(E), 6):
            compare(set(E) - {x}, r)
        for start in rng.sample(crnsign.ROUTE_BOX, 4):
            compare(bench_radius._grown(vals, r, start), r)
        for _ in range(4):
            compare(set(rng.sample(crnsign.ROUTE_BOX, rng.randint(1, 6))), r)
    # tie-rich tables: Route has one tie, so ties are exercised here
    for _ in range(random_tables):
        box = [x for x in itertools.product(range(6), repeat=2)]
        table = {x: (rng.randint(0, 3), rng.randint(0, 3)) for x in box}
        for r in radii:
            for start in rng.sample(box, 6):
                compare(bench_radius._grown(table, r, start), r, table)
            for _ in range(4):
                compare(set(rng.sample(box, rng.randint(1, 6))), r, table)
    if verbose:
        print('{0} of {1} sets: the exact certificate and PyMOSO\'s agree ({2} of them certified); {3} sets '
              'known not to be certified were rejected'.format(agree, total, positives, rejected))
    return agree, total, positives


# ---- mutations ----

MUTATION_POINTS = {'Route': crnsign.ROUTE_BOX[::9], 'Antithetic': crnsync.BOX[::23]}


def mutations(verbose=True, reps=400, random_tables=20, points=None):
    """`points`: {name: points}, MUTATION_POINTS by default."""
    points = MUTATION_POINTS if points is None else points
    out = []

    def report(name, caught):
        out.append((name, caught))
        if verbose:
            print('{0:55s} {1}'.format(name, 'caught' if caught else 'NOT CAUGHT'))

    def raises(f):
        try:
            f()
        except AssertionError:
            return True
        return False

    for name, pts in points.items():
        lattice(name, reps, pts)          # the real measurement passes on these points
        lattice(name, reps, pts, crn=False)
        for label, m in (('replication j paired with j+1', 'shift'), ('default coordinates in the CRN arm', 'nocrn'),
                         ('correlation pooled across objectives', 'pooled')):
            report('measurement on {0}: {1}'.format(name, label), raises(lambda: lattice(name, reps, pts, mutation=m)))
    report('exact: Antithetic\'s cost and its flip independent',
           raises(lambda: lattice('Antithetic', reps, points['Antithetic'],
                                  exact=lambda x, y: crnsign.inventory_rho(x, y, wrong_epp=True))))
    report('exact: Antithetic computed without the flip',
           raises(lambda: lattice('Antithetic', reps, points['Antithetic'], exact=_inv_exact)))
    pts = points['Route']
    route_marginals(bench_crn.samples(crnsign.Route, pts, reps, False))
    report('closed form: Route against the R <= x1 model',
           raises(lambda: route_marginals(bench_crn.samples(crnsign.RouteBelow, pts, reps, False))))
    real = barrier.certified_by
    for name, m in bench_plateau._mutants():
        barrier.certified_by = m
        try:
            caught = raises(lambda: verify(verbose=False, random_tables=random_tables))
        except KeyError:
            caught = True
        finally:
            barrier.certified_by = real
        report('certificate: ' + name, caught)
    return out


# ---- covariance ----

def covariance(out, reps=1000, points=None, verbose=True):
    """`points`: {name: points} to sample instead of each whole box."""
    t0 = time.perf_counter()
    points = points or {}
    result = dict(python=platform.python_version(), when=time.strftime('%Y-%m-%dT%H:%M:%S'), seed=list(SEED),
                  reps=reps, lattice=[], marginals={})
    store = {}
    for name in MEASURED:
        for arm in ARMS:
            rows, s = lattice(name, reps, points.get(name), crn=arm == 'crn')
            result['lattice'].extend(rows)
            store[(name, arm)] = s
        if verbose:
            print(name, 'done', round(time.perf_counter() - t0), flush=True)
    result['marginals']['Route'] = route_marginals(store[('Route', 'default')])
    anti, fixed = store[('Antithetic', 'default')], store[('SyncFixed', 'default')]
    result['marginals']['Antithetic'] = bench_crn.marginals(anti, fixed)
    # at even points Antithetic is SyncFixed bit for bit
    for arm in ARMS:
        a, f = store[('Antithetic', arm)], store[('SyncFixed', arm)]
        if any(a[x] != f[x] for x in a if not crnsign.flipped(x)):
            raise AssertionError('Antithetic differs from SyncFixed at an even point')
    result.update(exact_only())
    if verbose:
        print('done', round(time.perf_counter() - t0), flush=True)
    with open(out, 'w') as f:
        json.dump(result, f)
    return result


def exact_only():
    """The exact correlations that are not measured: Split's, and the
    swap pairs (x + e1, x + e2) of Route and Antithetic (whose swap
    pairs share a parity). No sampling, so they do not depend on a run."""
    def swaps(f, n):
        return [dict(x=[a + 1, b], y=[a, b + 1], rho=list(f((a + 1, b), (a, b + 1))))
                for a in range(n) for b in range(n)]
    return dict(split=[dict(kind=k, x=list(x), y=list(y), rho=list(r)) for k, x, y, r in crnsign.split_exact()],
                route_exact_swap=swaps(crnsign.route_rho, crnsign.NR),
                anti_exact_swap=swaps(crnsign.inventory_rho, crnsync.N))


# ---- run: the solvers ----

BUDGET = bench_crn.BUDGET
CHECKPOINTS = bench_crn.CHECKPOINTS
REPS = bench_crn.REPS
RUN_PROBLEMS = {'Route': (crnsign.Route, crnsign.ROUTE_BOX, crnsign.route_efficient_set),
                'Antithetic': (crnsign.Antithetic, crnsync.BOX, crnsync.efficient_set),
                'SyncFixed': (crnsync.SyncFixed, crnsync.BOX, crnsync.efficient_set)}
CONFIGS = [(s, p, a) for s in bench_crn.MO_SOLVERS for p in RUN_PROBLEMS for a in ARMS]


def quality(problem, soln):
    cls, _, eff = RUN_PROBLEMS[problem]
    f = cls.TRUE_G
    return moso.dh([f(x) for x in soln], [f(x) for x in eff()])


def run_one(solver, problem, arm, rep, budget=BUDGET, checkpoints=CHECKPOINTS):
    """bench_crn.run_one, on these problems; the same seeds, and the same
    x0 on the inventory box, so SyncFixed's rows reproduce
    scratch/phase7/crn_runs.jsonl's."""
    import io
    from pymoso.paths import isp_run
    cls, box, _ = RUN_PROBLEMS[problem]
    orcstream, solvstream = get_solv_prnstreams(bench_crn.run_seed(rep), mrg32k3a)
    orc = cls(orcstream)
    orc.set_crnflag(arm == 'crn')
    x0 = random.Random(rep).choice(box)
    seen = dict(largest=0, replications=0)
    row = dict(solver=solver, problem=problem, arm=arm, rep=rep, seed=list(bench_crn.run_seed(rep)),
               x0=list(x0), budget=budget)
    with bench_plateau._guard(bench_crn.OVERSHOOT * budget, seen), contextlib.redirect_stdout(io.StringIO()), \
            orc.set_simpar(1):
        try:
            res = isp_run(bench_crn._solvers()[solver], budget, orc, solvprn=solvstream, x0=x0)
        except Exception as e:
            if not bench_plateau._caused_by_overshoot(e):
                raise
            res = None
    row.update(finished=res is not None, replications=seen['replications'])
    if res is None:
        row.update(iterations=None, simcalls=None, quality={str(c): None for c in checkpoints}, final_size=None)
        return row
    iters = sorted(res['itersoln'])
    at = {}
    for c in checkpoints:
        done = [k for k in iters if res['simcalls'][k] <= c and k > 0 and res['itersoln'][k]]
        at[str(c)] = quality(problem, res['itersoln'][done[-1]]) if done else None
    last = iters[-1]
    row.update(iterations=last, simcalls=res['simcalls'][last], quality=at, final_size=len(res['itersoln'][last]))
    return row


def _run_task(args):
    solver, problem, arm, rep, budget, checkpoints = args
    row = run_one(solver, problem, arm, rep, budget, checkpoints)
    row.update(python=platform.python_version(), when=time.strftime('%Y-%m-%dT%H:%M:%S'))
    return row


def run(path, configs=CONFIGS, reps=REPS, budget=BUDGET, checkpoints=CHECKPOINTS, workers=1, verbose=True):
    """As bench_crn.run: appends one JSON line per run, skipping runs
    already in `path`; only the parent writes."""
    import multiprocessing
    import os
    done = set()
    if os.path.exists(path):
        done = {bench_crn._key(json.loads(line)) for line in open(path)}
    tasks = [(s, p, a, rep, budget, checkpoints) for s, p, a in configs for rep in range(reps)
             if (s, p, a, rep) not in done]
    with contextlib.ExitStack() as stack:
        if workers > 1:
            pool = stack.enter_context(multiprocessing.get_context('spawn').Pool(workers))
            results = pool.imap_unordered(_run_task, tasks)
        else:
            results = map(_run_task, tasks)
        for row in results:
            with open(path, 'a') as f:
                f.write(json.dumps(row) + '\n')
            if verbose:
                print(row['solver'], row['problem'], row['arm'], row['rep'], row['simcalls'], flush=True)


def _versus(a, b, k):
    """(a better, same, worse) than b on the same seed at checkpoint k."""
    pairs = [(a[i]['quality'][k], b[i]['quality'][k]) for i in a
             if i in b and a[i]['quality'][k] is not None and b[i]['quality'][k] is not None]
    w = sum(x < y for x, y in pairs)
    e = sum(x == y for x, y in pairs)
    return w, e, len(pairs) - w - e


def report_runs(path):
    rows = [json.loads(line) for line in open(path)]
    med = statistics.median
    by = {}
    for r in rows:
        by.setdefault((r['solver'], r['problem'], r['arm']), {})[r['rep']] = r
    cps = sorted({int(c) for r in rows for c in r['quality']})
    L = ['### The solvers: quality at matched counted simulations', '',
         'Runs: {0}, Python {1}, budget {2}, {3} seeds per configuration; the seeds of docs/bench_crn.py\'s runs. '
         'Quality: the Hausdorff distance between the true images of the returned set and of the efficient '
         'set; lower is better. Median, then seeds where CRN is better / same / worse than the default arm on '
         'the same seed. "-": no iteration finished by that checkpoint.'.format(
             len(rows), sorted({r['python'] for r in rows}), sorted({r['budget'] for r in rows}),
             max(len(v) for v in by.values())), '']
    L.append('| solver | problem | finished (crn / default) | '
             + ' | '.join('at {0:,}: default | at {0:,}: crn (better/same/worse)'.format(c) for c in cps) + ' |')
    L.append('|---|---|---|' + '---|---|' * len(cps))
    for solver, problem in sorted({(k[0], k[1]) for k in by}):
        crn, dft = by.get((solver, problem, 'crn'), {}), by.get((solver, problem, 'default'), {})
        cells = []
        for c in cps:
            k = str(c)
            dv = [r['quality'][k] for r in dft.values() if r['quality'][k] is not None]
            cv = [r['quality'][k] for r in crn.values() if r['quality'][k] is not None]
            cells.append('{0:.3g}'.format(med(dv)) if dv else '-')
            cells.append('{0} ({1}/{2}/{3})'.format('{0:.3g}'.format(med(cv)) if cv else '-', *_versus(crn, dft, k)))
        L.append('| {0} | {1} | {2}/{3} / {4}/{5} | '.format(
            solver, problem, sum(r['finished'] for r in crn.values()), len(crn),
            sum(r['finished'] for r in dft.values()), len(dft)) + ' | '.join(cells) + ' |')
    last = str(cps[-1])
    L.extend(['', 'Antithetic against its twin SyncFixed (identical marginals): Antithetic better / same / worse '
              'on the same seed at {0:,}, per arm. The default arm is the control.'.format(cps[-1]), ''])
    L.append('| solver | default arm | crn arm |')
    L.append('|---|---|---|')
    for solver in sorted({k[0] for k in by}):
        cells = ['{0}/{1}/{2}'.format(*_versus(by.get((solver, 'Antithetic', arm), {}),
                                               by.get((solver, 'SyncFixed', arm), {}), last))
                 for arm in ('default', 'crn')]
        L.append('| {0} | {1} | {2} |'.format(solver, *cells))
    L.append('')
    L.append('Median simulations per RA iteration (simcalls at the end over iterations), crn / default:')
    L.append('')
    L.append('| solver | problem | crn | default |')
    L.append('|---|---|---|---|')
    for solver, problem in sorted({(k[0], k[1]) for k in by}):
        vals = []
        for arm in ARMS:
            rs = [r for r in by.get((solver, problem, arm), {}).values() if r['finished'] and r['iterations']]
            vals.append('{0:.0f}'.format(med(r['simcalls'] / r['iterations'] for r in rs)) if rs else '-')
        L.append('| {0} | {1} | {2} | {3} |'.format(solver, problem, *vals))
    return L


# ---- report ----

def _exact_row(label, rhos, k):
    v = [r[k] for r in rhos if r[k] is not None]
    return '| {0} | {1} | {2:.2f} | {3:.2f} | {4:.2f} | {5} |'.format(
        label, len(v), min(v), statistics.median(v), max(v), sum(t < 0 for t in v))


def report(path, out, runs=None):
    d = json.load(open(path))
    q = bench_crn._q
    names = {'Route': ('overflow', 'idle + transfer'), 'Antithetic': ('holding', 'shortage'),
             'SyncFixed': ('holding', 'shortage')}
    L = ['<!-- generated by docs/bench_crn_sign.py report; do not edit -->', '',
         'Python {0}, seed {1}. Counted, not timed.'.format(d['python'], d['seed'][0]), '',
         '### Exact correlations under CRN', '',
         'One period\'s correlation between the two points, which is a replication\'s at any number of periods. '
         'Pairs with a constant objective are left out. Axis pairs are (x, x + e_i); swap pairs (x + e1, x + e2), '
         'which a solver also compares.', '',
         '| problem, pairs, objective | pairs | min | median | max | negative |', '|---|---|---|---|---|---|']
    lat = d['lattice']
    for name, axis, label in (('Route', 0, 'threshold axis'), ('Route', 1, 'capacity axis')):
        rh = [r['exact'] for r in lat if r['problem'] == name and r['arm'] == 'crn' and r['axis'] == axis]
        for k in range(2):
            L.append(_exact_row('Route, {0}, {1}'.format(label, names[name][k]), rh, k))
    for k in range(2):
        L.append(_exact_row('Route, swap, {0}'.format(names['Route'][k]), [r['rho'] for r in d['route_exact_swap']], k))
    for kind in ('axis', 'swap'):
        rh = [r['rho'] for r in d['split'] if r['kind'] == kind]
        for k in range(2):
            L.append(_exact_row('Split, {0}, {1}'.format(kind, ('holding', 'shortage')[k]), rh, k))
    for name in ('Antithetic', 'SyncFixed'):
        rh = [r['exact'] for r in lat if r['problem'] == name and r['arm'] == 'crn']
        for k in range(2):
            L.append(_exact_row('{0}, axis, {1}'.format(name, names[name][k]), rh, k))
    for k in range(2):
        L.append(_exact_row('Antithetic, swap, {0}'.format(names['Antithetic'][k]),
                            [r['rho'] for r in d['anti_exact_swap']], k))
    L.extend(['', '### Measured, against exact', '',
              '{0} replications per point; every axis pair in each box. Correlation and variance ratio '
              'Var(g(x) - g(y)) / (Var g(x) + Var g(y)): median (quartiles) over pairs; 1 is independent sampling, '
              'above 1 CRN is worse than independent. Largest |z|: the measured correlation against the exact one '
              '(0 without CRN), Fisher z over a jackknife standard error; every pair was required to be within '
              '{1}. Normal-theory error: pairs where leaving one replication out gives a correlation of exactly 1, '
              'so the jackknife is undefined and 1 / sqrt(n - 3) is used instead.'.format(d['reps'], TOL), ''])
    L.append('| problem | arm | objective | correlation | variance ratio | largest |z| | normal-theory error | '
             'CI above 0 | CI below 0 |')
    L.append('|---|---|---|---|---|---|---|---|---|')
    for name in MEASURED:
        for arm in ARMS:
            rs = [r for r in lat if r['problem'] == name and r['arm'] == arm]
            for k in range(2):
                valid = [r for r in rs if r['rho'][k] is not None]
                zs = [abs(r['z'][k]) for r in rs if r['z'][k] is not None]
                L.append('| {0} | {1} | {2} | {3} | {4} | {5:.2f} | {6} | {7}/{8} | {9}/{8} |'.format(
                    name, arm, names[name][k], q(r['rho'][k] for r in rs), q((r['vr'][k] for r in rs), 3),
                    max(zs), sum(r['se'][k] == 'normal' for r in rs), sum(r['lo'][k] > 0 for r in valid),
                    len(valid), sum(r['hi'][k] < 0 for r in valid)))
    m = d['marginals']
    L.extend(['', 'Marginals without CRN: Route\'s means against its closed form, largest |z| {0:.2f}. Antithetic '
              'against SyncFixed\'s closed form {1:.2f}, SyncFixed {2:.2f}; the twins\' means {3:.2f} and variances '
              '{4:.2f} against each other. At even points the two are identical, replication for replication, in '
              'both arms (checked).'.format(m['Route'], m['Antithetic']['var_vs_exact'],
                                            m['Antithetic']['fixed_vs_exact'], m['Antithetic']['twins_means'],
                                            m['Antithetic']['twins_variances'])])
    if runs is not None:
        L.extend([''] + report_runs(runs))
    with open(out, 'w') as f:
        f.write('\n'.join(L) + '\n')


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else ''
    if cmd == 'verify':
        verify()
    elif cmd == 'mutations':
        mutations()
    elif cmd == 'covariance':
        covariance(sys.argv[2])
    elif cmd == 'run':
        run(sys.argv[2], workers=int(sys.argv[3]) if len(sys.argv) > 3 else 1)
    elif cmd == 'report':
        report(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else None)
    else:
        raise SystemExit(__doc__)
