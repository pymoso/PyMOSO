#!/usr/bin/env python
"""
Regenerates docs/crn-failure.md's measurements: where common random
numbers stop helping, measured directly as the correlation between
neighbouring points' replications, with no solver
(docs/phase7-plan.md, step 6b).

    python docs/bench_crn.py calibrate            # the measurement, on exact correlations
    python docs/bench_crn.py verify               # the sync problem's known answer, checked
    python docs/bench_crn.py mutations            # ... and every check shown to detect
    python docs/bench_crn.py covariance OUT.json  # the measurement (counted, not timed)
    python docs/bench_crn.py run RUNS.jsonl [WORKERS]   # the solvers on the twins (counted)
    python docs/bench_crn.py report OUT.json OUT.md [RUNS.jsonl]

The problems are scratch/phase7/crnsync.py: the inventory twins
SyncVar/SyncFixed and the cyclic twins CycRare/CycFixed (each pair with
identical marginals; the first's draw count depends on
x), the calibration oracles Calib/CalibVar (exact correlations), and
RandRange (randint over a range that grows with x).

How it measures. Each point gets one hit(x, R) through the real Oracle
and executor, in process; a wrapper on SerialExecutor.run records every
replication's objectives and raw draw count (executor.Replication), and
the recorder is checked to have seen R replications of every point
asked for. Under CRN (set_crnflag(True)), replication j of every point
starts at the same position of the iteration's stream; without it each
point has its own. For a pair (x, x + e_i), replication j at x is paired
with replication j at y: per objective the Pearson correlation (a
Fisher-z 95% interval), the variance ratio Var(g(x) - g(y)) / (Var g(x)
+ Var g(y)) -- 1 for independent sampling, below 1 where CRN helps,
above where it hurts -- and the share of replications whose draw counts
differ.

`calibrate` holds that measurement to the calibration oracles' exact
values and must fail under four wrong versions of it (`mutations`).
`verify` holds the sync problem's exact certificate to PyMOSO's own, as
docs/bench_plateau.py does; `mutations` also runs it against wrong
certificates, and runs the closed-form-means check against a wrong
closed form.

tests/test_benchmark_scripts.py only checks that the script runs.
"""
import contextlib
import importlib.util
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
import crnsync  # noqa: E402


def _load(name):
    spec = importlib.util.spec_from_file_location(name, str(ROOT / 'docs' / '{0}.py'.format(name)))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


bench_radius = _load('bench_radius')
bench_plateau = _load('bench_plateau')

from pymoso import executor, moso  # noqa: E402
from pymoso.layout import get_solv_prnstreams  # noqa: E402
from pymoso.prng import mrg32k3a  # noqa: E402
from pymoso.problems import bsprob, probsimpleso, probtpa, probtpb, probtpc  # noqa: E402
from pymoso.testers import bstester, simplesotester, tpatester, tpbtester, tpctester  # noqa: E402

SEED = (12345,) * 6
ARMS = ('crn', 'default')
SWEEP_T = (1, 5, 30, 100, 300)
BUILTINS = (('ProbSimpleSO', probsimpleso.ProbSimpleSO, simplesotester.get_ranx0),
            ('ProbTPA', probtpa.ProbTPA, tpatester.get_ranx0),
            ('ProbTPB', probtpb.ProbTPB, tpbtester.get_ranx0),
            ('ProbTPC', probtpc.ProbTPC, tpctester.get_ranx0),
            ('BSProb', bsprob.BSProb, bstester.get_ranx0))
VERIFY_RADII = (1, 2, 3)


# ---- sampling ----

@contextlib.contextmanager
def _recording(log, on_block=None):
    """Record (x, outcomes) for every block the in-process executor runs;
    `on_block(executor, block, outcomes)` runs while it is still open."""
    real = executor.SerialExecutor.run

    def run(self, blocks):
        out = real(self, blocks)
        for b, o in zip(blocks, out):
            log.append((b.x, o))
            if on_block is not None:
                on_block(self, b, o)
        return out
    executor.SerialExecutor.run = run
    try:
        yield
    finally:
        executor.SerialExecutor.run = real


def samples(cls, points, reps, crn, on_block=None, seed=SEED):
    """
    {x: [(objectives, raw draws), ...]} for each feasible x in `points`,
    one hit(x, reps) each, replication order kept. Infeasible points are
    left out.
    """
    orcstream, _ = get_solv_prnstreams(seed, mrg32k3a)
    orc = cls(orcstream)
    orc.set_crnflag(crn)
    log = []
    feasible = {}
    with orc.set_simpar(1), _recording(log, on_block):
        for x in points:
            isfeas, _, _ = orc.hit(x, reps)
            feasible[x] = isfeas
    got = {}
    for x, outcomes in log:
        got.setdefault(x, []).extend(outcomes)
    # the substitution was reached, and saw exactly what was asked for
    for x in points:
        if feasible[x] and len(got.get(x, ())) != reps:
            raise AssertionError('recorded {0} replications of {1}, asked for {2}'.format(
                len(got.get(x, ())), x, reps))
    return {x: [(o.objectives, o.raw_consumed) for o in got[x]] for x in points if feasible[x]}


def axis_pairs(points, inside):
    return [(x, tuple(v + (j == i) for j, v in enumerate(x)), i)
            for x in points for i in range(len(x))
            if inside(tuple(v + (j == i) for j, v in enumerate(x)))]


# ---- statistics ----

def _corr(a, b):
    if statistics.pvariance(a) == 0 or statistics.pvariance(b) == 0:
        return None
    return statistics.correlation(a, b)


def _interval(r, n):
    if r is None:
        return None, None
    if abs(r) >= 1:
        return r, r
    z, h = math.atanh(r), 1.96 / math.sqrt(n - 3)
    return math.tanh(z - h), math.tanh(z + h)


def pair_stats(sx, sy, mutation=None):
    """
    Per objective: (rho, lo, hi, variance ratio); and the share of
    replications whose draw counts differ. `mutation` makes it wrong on
    purpose, for `mutations`.
    """
    if mutation == 'shift':
        sy = sy[1:] + sy[:1]
    n = len(sx)
    nobj = len(sx[0][0])
    out = []
    for k in range(nobj):
        a = [s[0][k] for s in sx]
        b = [s[0][k] for s in sy]
        if mutation == 'pooled':
            a = [s[0][j] for s in sx for j in range(nobj)]
            b = [s[0][j] for s in sy for j in range(nobj)]
        r = _corr(a, b)
        lo, hi = _interval(r, n)
        va, vb = statistics.variance(a), statistics.variance(b)
        vd = statistics.variance([p - q for p, q in zip(a, b)])
        if va + vb == 0:
            vr = None
        elif mutation == 'inverted':
            vr = (va + vb) / vd if vd else math.inf
        else:
            vr = vd / (va + vb)
        out.append((r, lo, hi, vr))
    differ = sum(p[1] != q[1] for p, q in zip(sx, sy)) / n
    return out, differ


# ---- calibrate ----

def calibrate(reps=1000, verbose=True, mutation=None, tol=4.5):
    """
    The measurement on the calibration oracles, against their exact
    correlations (crnsync.calib_rho) and variance ratios (1 - rho).
    Raises on any pair outside `tol` standard errors (Fisher z), or off
    an exact value of 1 by more than rounding.
    """
    checked = 0
    for cls in (crnsync.Calib, crnsync.CalibVar):
        for crn in (True, False):
            run_crn = crn and mutation != 'nocrn'
            s = samples(cls, crnsync.CALIB_BOX, reps, run_crn)
            exact = crnsync.calib_rho(cls, crn)
            for x, y, i in axis_pairs(crnsync.CALIB_BOX, lambda p: p in s):
                stats, _ = pair_stats(s[x], s[y], mutation)
                for k, (r, lo, hi, vr) in enumerate(stats):
                    want = exact[k]
                    if want == 1.0:
                        ok = r is not None and r > 1 - 1e-9 and vr < 1e-9
                    else:
                        se = 1 / math.sqrt(reps - 3)
                        ok = (r is not None and abs(math.atanh(r) - math.atanh(want)) <= tol * se
                              and abs(vr - (1 - want)) <= tol * 2 * se)
                    if not ok:
                        raise AssertionError('{0} crn={1} {2}->{3} objective {4}: rho {5}, ratio {6}; exact {7}'.format(
                            cls.__name__, crn, x, y, k, r, vr, want))
                    checked += 1
    if verbose:
        print('{0} pair-objectives match their exact correlation and variance ratio'.format(checked))
    return checked


HARNESS_MUTANTS = (('replication j paired with j+1', 'shift'),
                   ('default coordinates in the CRN arm', 'nocrn'),
                   ('correlation pooled across objectives', 'pooled'),
                   ('variance ratio inverted', 'inverted'))


# ---- verify: the sync problem's known answer ----

def _mirror_pair(E):
    for a in sorted(E):
        b = (a[1], a[0])
        if a != b and b in E:
            return {a, b}
    raise AssertionError('no mirror pair in E')


def verify(radii=VERIFY_RADII, extra=20, random_tables=20, seed=13, verbose=True):
    """
    The exact certificate against PyMOSO's own on the sync problem's
    true means. Raises on any disagreement, and if a set known not to be
    certified passes.

    On this problem no set compared here is certified at one radius and
    not another (counted: `radius_dependent`), so a certificate that
    ignores the radius would give the same answers on it. Random 6 x 6
    tables of small integers (docs/bench_radius.py) are added so that
    the radius handling is still exercised.
    """
    import itertools
    rng = random.Random(seed)
    vals = crnsync.values()
    E = crnsync.efficient_set()
    agree = total = positives = rejected_known = radius_dependent = 0

    def compare(S, r, table=vals):
        nonlocal agree, total, positives, radius_dependent
        a = barrier.certified_by(S, r, table.__getitem__, table.__contains__)
        b = bench_radius.code_certified(S, r, table)
        if table is vals:
            radius_dependent += a != barrier.certified_by(S, 1, table.__getitem__, table.__contains__)
        total += 1
        positives += a
        agree += a == b
        if a != b:
            raise AssertionError('the two certificates disagree: r={0} S={1}: exact {2}, PyMOSO {3}'.format(
                r, sorted(S)[:6], a, b))

    dominated = next(x for x in crnsync.BOX if x not in E)
    for r in radii:
        # known not certified: E less a mirror pair (each is tied only
        # with the other, so E less one of them would still be covered,
        # the plateau harness's mistake), and E with a dominated point
        for S in (set(E) - _mirror_pair(E), set(E) | {dominated}):
            if barrier.certified_by(S, r, vals.__getitem__, vals.__contains__):
                raise AssertionError('certified a set known not to be: r={0}'.format(r))
            rejected_known += 1
            compare(S, r)
        compare(E, r)
        for x in rng.sample(crnsync.BOX, extra):
            compare({x}, r)
        for x in rng.sample(sorted(E), 6):
            compare(set(E) - {x}, r)
            compare(set(E) - {x, (x[1], x[0])}, r)
        for start in rng.sample(crnsync.BOX, 4):
            compare(bench_radius._grown(vals, r, start), r)
        for _ in range(4):
            compare(set(rng.sample(crnsync.BOX, rng.randint(1, 6))), r)
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
              'known not to be certified were rejected; {4} sync-problem sets certified differently at '
              'radius 1'.format(agree, total, positives, rejected_known, radius_dependent))
    return agree, total, positives, radius_dependent


def marginals(s_var, s_fixed, true_g=crnsync.true_g, tol=4.5):
    """
    Without CRN: each twin's per-point means against the closed form, and
    the twins' means and variances against each other, as z-scores.
    Raises if any is beyond `tol`. Returns the largest |z| of each kind.
    """
    worst = dict(var_vs_exact=0.0, fixed_vs_exact=0.0, twins_means=0.0, twins_variances=0.0)
    for x in s_var:
        for k in range(2):
            a = [s[0][k] for s in s_var[x]]
            b = [s[0][k] for s in s_fixed[x]]
            n = len(a)
            mu = true_g(x)[k]
            va, vb = statistics.variance(a), statistics.variance(b)
            if va == 0 and vb == 0:
                if not (statistics.fmean(a) == statistics.fmean(b) == mu):
                    raise AssertionError('{0} objective {1}: constant, but not at the closed form'.format(x, k))
                continue
            za = (statistics.fmean(a) - mu) / math.sqrt(va / n) if va else 0.0
            zb = (statistics.fmean(b) - mu) / math.sqrt(vb / n) if vb else 0.0
            zt = (statistics.fmean(a) - statistics.fmean(b)) / math.sqrt((va + vb) / n)
            # variances: log ratio, approximately normal with variance
            # (kurtosis-dependent; 2/(n-1) each for normal data, so use
            # the samples' own fourth moments)
            def lvar(v, xs):
                m = statistics.fmean(xs)
                m4 = statistics.fmean([(t - m) ** 4 for t in xs])
                return (m4 / (v * v) - (n - 3) / (n - 1)) / n
            zv = math.log(va / vb) / math.sqrt(lvar(va, a) + lvar(vb, b))
            for key, z in (('var_vs_exact', za), ('fixed_vs_exact', zb), ('twins_means', zt),
                           ('twins_variances', zv)):
                worst[key] = max(worst[key], abs(z))
    for key, z in worst.items():
        if z > tol:
            raise AssertionError('{0}: |z| = {1:.2f} > {2}'.format(key, z, tol))
    return worst


def _wrong_true_g(x):
    """The closed form with the stockout condition off by one (d >= x)."""
    def item(xi):
        hold = sum(crnsync.Fraction(crnsync.H * (xi - d), crnsync.M) for d in range(crnsync.M) if d < xi)
        short = sum(crnsync.Fraction(crnsync.B * (d - xi) + crnsync.MU, crnsync.M)
                    for d in range(crnsync.M) if d >= xi)
        return hold, short
    a, b = item(x[0]), item(x[1])
    return float(a[0] + b[0]), float(a[1] + b[1])


def mutations(verbose=True, reps=400):
    out = []

    def report(name, caught):
        out.append((name, caught))
        if verbose:
            print('{0:45s} {1}'.format(name, 'caught' if caught else 'NOT CAUGHT'))

    for name, m in HARNESS_MUTANTS:
        try:
            calibrate(reps=reps, verbose=False, mutation=m)
            caught = False
        except AssertionError:
            caught = True
        report('measurement: ' + name, caught)
    real = barrier.certified_by
    for name, m in bench_plateau._mutants():
        barrier.certified_by = m
        try:
            verify(verbose=False)
            caught = False
        except (AssertionError, KeyError):
            caught = True
        finally:
            barrier.certified_by = real
        report('certificate: ' + name, caught)
    pts = crnsync.BOX[::7]
    sv = samples(crnsync.SyncVar, pts, reps, False)
    sf = samples(crnsync.SyncFixed, pts, reps, False)
    marginals(sv, sf)  # the real closed form passes on the same samples
    try:
        marginals(sv, sf, true_g=_wrong_true_g)
        caught = False
    except AssertionError:
        caught = True
    report('closed form: stockout at d >= x', caught)
    cv = samples(crnsync.CycRare, pts, reps, False)
    cf = samples(crnsync.CycFixed, pts, reps, False)
    marginals(cv, cf, true_g=crnsync.true_g_cyc)
    try:
        marginals(cv, cf, true_g=crnsync.true_g)
        caught = False
    except AssertionError:
        caught = True
    report('closed form: cyclic twins without Q', caught)
    return out


# ---- covariance ----

def _summ(stats, differ):
    return dict(rho=[s[0] for s in stats], lo=[s[1] for s in stats], hi=[s[2] for s in stats],
                vr=[s[3] for s in stats], differ=differ)


def _lattice(reps, points=None):
    """Both twins, both arms, every axis pair from `points` (default the
    whole box); and the twins' marginals without CRN."""
    points = crnsync.BOX if points is None else points
    pairs = axis_pairs(points, crnsync.in_box)
    sampled = sorted({p for x, y, _ in pairs for p in (x, y)})
    rows = []
    worst = {}
    for var, fixed in crnsync.TWINS:
        store = {}
        for cls in (fixed, var):
            for arm in ARMS:
                s = samples(cls, sampled, reps, arm == 'crn')
                store[(cls, arm)] = s
                for x, y, i in pairs:
                    rows.append(dict(problem=cls.__name__, arm=arm, x=list(x), axis=i,
                                     **_summ(*pair_stats(s[x], s[y]))))
        worst[var.__name__] = marginals(store[(var, 'default')], store[(fixed, 'default')], true_g=var.TRUE_G)
    return rows, worst


# the synchronized twin of each pair first
ORDER = [c for pair in crnsync.TWINS for c in reversed(pair)]
SWEEP_POINTS = [(a, b) for a in (2, 9, 16) for b in (2, 9, 16)]


def _sweep(reps, sweep_t=SWEEP_T):
    """The T sweep on a few pairs, CRN only: correlation against the
    share of periods still in step at the first point where the draw
    counts part (replayed from the same streams, and checked against the
    recorded outputs)."""
    rows = []
    for periods in sweep_t:
        for base in ORDER:
            cls = crnsync.with_periods(base, periods)
            pairs = [(x, y, i) for x, y, i in axis_pairs(SWEEP_POINTS, crnsync.in_box)]
            points = sorted({p for x, y, _ in pairs for p in (x, y)})
            traces = {}

            def on_block(ex, block, outcomes):
                tr = []
                for stream, o in zip(ex.streams(block), outcomes):
                    t = []
                    replay = base.run(block.x, stream, periods, t)
                    if replay != tuple(o.objectives):
                        raise AssertionError('replay differs from the recorded replication')
                    tr.append(t)
                traces[block.x] = tr
            s = samples(cls, points, reps, True, on_block)
            for x, y, i in pairs:
                in_step, in_role = [], []
                for tx, ty in zip(traces[x], traces[y]):
                    k = next((j for j in range(periods) if tx[j] != ty[j]), periods)
                    in_step.append(k / periods)
                    in_role.append(len(_starts(tx) & _starts(ty)) / periods)
                rows.append(dict(problem=base.__name__, periods=periods, x=list(x), axis=i,
                                 in_step=statistics.fmean(in_step), in_role=statistics.fmean(in_role),
                                 **_summ(*pair_stats(s[x], s[y]))))
    return rows


def _starts(trace):
    """The raw positions at which a replication's periods start."""
    return {0} | set(trace[:-1])


SHIFTS = (0, 1, 2, 3, 4, 8, 100, 1000, 2000)


def _shift(reps, x=(9, 9), periods=300, shifts=SHIFTS):
    """
    One point against itself, misaligned: replication j at x from its CRN
    stream, against x again from that stream advanced by k raw draws --
    a misalignment from the first draw, with no x-dependence at all.
    Whether the correlation survives says whether misaligned draws are
    effectively independent (they would be at every k > 0) or still the
    same pool of uniforms used in the same roles.
    """
    rows = []
    for base in ORDER:
        cls = crnsync.with_periods(base, periods)
        got = {}

        def on_block(ex, block, outcomes):
            for k in shifts:
                got[k] = [(base.run(block.x, st.advance(k), periods), 0)
                          for st in ex.streams(block)]
        s = samples(cls, [x], reps, True, on_block)
        if [o[0] for o in got[0]] != [tuple(o[0]) for o in s[x]]:
            raise AssertionError('the unshifted replay differs from the recorded replications')
        for k in shifts:
            stats, _ = pair_stats(got[0], got[k])
            rows.append(dict(problem=base.__name__, periods=periods, x=list(x), shift=k,
                             rho=[t[0] for t in stats]))
    return rows


def _randrange(reps):
    rows = []
    pts = [(v,) for v in range(60)]
    for arm in ARMS:
        s = samples(crnsync.RandRange, pts, reps, arm == 'crn')
        for x, y, i in axis_pairs(pts, lambda p: p[0] <= 59):
            rows.append(dict(arm=arm, x=list(x), range=4 + x[0], **_summ(*pair_stats(s[x], s[y]))))
    return rows


def _builtins(reps, npoints, seed=21):
    rows = []
    for name, cls, ranx0 in BUILTINS:
        rng = random.Random(seed)
        pts = []
        while len(pts) < npoints:
            x = tuple(ranx0(rng))
            if x not in pts:
                pts.append(x)
        pairs = [(x, tuple(v + (j == i) for j, v in enumerate(x)), i) for x in pts for i in range(len(x))]
        allpts = list(dict.fromkeys([p for x, y, _ in pairs for p in (x, y)]))
        for arm in ARMS:
            s = samples(cls, allpts, reps, arm == 'crn')
            for x, y, i in pairs:
                if x in s and y in s:
                    rows.append(dict(problem=name, arm=arm, x=list(x), axis=i, **_summ(*pair_stats(s[x], s[y]))))
    return rows


def covariance(out, reps=1000, sweep_reps=1000, randrange_reps=2000, builtin_reps=500, builtin_points=10,
               lattice_points=None, sweep_t=SWEEP_T, shift_reps=1000, shift_periods=300, verbose=True):
    t0 = time.perf_counter()
    result = dict(python=platform.python_version(), when=time.strftime('%Y-%m-%dT%H:%M:%S'), seed=list(SEED),
                  reps=reps, sweep_reps=sweep_reps, randrange_reps=randrange_reps, builtin_reps=builtin_reps,
                  shift_reps=shift_reps)
    result['lattice'], result['marginals'] = _lattice(reps, lattice_points)
    result['lattice_points'] = len(crnsync.BOX if lattice_points is None else lattice_points)
    result['sweep_t'] = list(sweep_t)
    result['builtin_points'] = builtin_points
    if verbose:
        print('lattice done', round(time.perf_counter() - t0), flush=True)
    result['sweep'] = _sweep(sweep_reps, sweep_t)
    if verbose:
        print('sweep done', round(time.perf_counter() - t0), flush=True)
    result['shift'] = _shift(shift_reps, periods=shift_periods)
    result['randrange'] = _randrange(randrange_reps)
    result['builtins'] = _builtins(builtin_reps, builtin_points)
    if verbose:
        print('done', round(time.perf_counter() - t0), flush=True)
    with open(out, 'w') as f:
        json.dump(result, f)
    return result


# ---- run: the solvers on the twins (counted) ----

BUDGET = 20000
CHECKPOINTS = (500, 1000, 2000, 5000, 20000)
REPS = 20
OVERSHOOT = 50
MO_SOLVERS = ('RPERLE', 'RPE', 'RMINRLE')
# (solver, problem, arm): R-SPLINE on the single-objective twins
CONFIGS = ([(s, p.__name__, a) for s in MO_SOLVERS for pair in crnsync.TWINS for p in pair for a in ARMS]
           + [('RSPLINE', p, a) for p in ('SyncVarSO', 'SyncFixedSO', 'CycRareSO', 'CycFixedSO') for a in ARMS])


def _solvers():
    from pymoso.solvers.rminrle import RMINRLE
    from pymoso.solvers.rpe import RPE
    from pymoso.solvers.rperle import RPERLE
    from pymoso.solvers.rspline import RSPLINE
    return {'RSPLINE': RSPLINE, 'RPERLE': RPERLE, 'RPE': RPE, 'RMINRLE': RMINRLE}


def run_seed(rep):
    return (2000 + rep,) * 6


def run_x0(rep):
    return crnsync.get_ranx0(random.Random(rep))


def quality(problem, soln):
    """Hausdorff distance between the true images of `soln` and of the
    efficient set (the same set for both twin pairs); for a
    single-objective twin, the gap to the true minimum cost."""
    cls = crnsync.PROBLEMS[problem]
    f = cls.TRUE_G
    if cls.NUM_OBJ == 1:
        return min(sum(f(x)) for x in soln) - min(sum(f(x)) for x in crnsync.BOX)
    return moso.dh([f(x) for x in soln], [f(x) for x in crnsync.efficient_set()])


def run_one(solver, problem, arm, rep, budget=BUDGET, checkpoints=CHECKPOINTS):
    import io
    from pymoso.paths import isp_run
    cls = crnsync.PROBLEMS[problem]
    orcstream, solvstream = get_solv_prnstreams(run_seed(rep), mrg32k3a)
    orc = cls(orcstream)
    orc.set_crnflag(arm == 'crn')
    x0 = run_x0(rep)
    seen = dict(largest=0, replications=0)
    row = dict(solver=solver, problem=problem, arm=arm, rep=rep, seed=list(run_seed(rep)), x0=list(x0),
               budget=budget)
    with bench_plateau._guard(OVERSHOOT * budget, seen), contextlib.redirect_stdout(io.StringIO()), \
            orc.set_simpar(1):
        try:
            res = isp_run(_solvers()[solver], budget, orc, solvprn=solvstream, x0=x0)
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


def _key(r):
    return (r['solver'], r['problem'], r['arm'], r['rep'])


def run(path, configs=CONFIGS, reps=REPS, budget=BUDGET, checkpoints=CHECKPOINTS, workers=1, verbose=True):
    """Appends one JSON line per run to `path`, skipping runs already in
    it. With `workers` above 1, runs go to that many processes; only the
    parent writes. Counted, not timed, so parallel runs are fine."""
    import multiprocessing
    import os
    done = set()
    if os.path.exists(path):
        done = {_key(json.loads(line)) for line in open(path)}
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


def report_runs(path):
    """The solver runs' tables, as markdown lines."""
    rows = [json.loads(line) for line in open(path)]
    med = statistics.median
    by = {}
    for r in rows:
        by.setdefault((r['solver'], r['problem'], r['arm']), {})[r['rep']] = r
    cps = sorted({int(c) for r in rows for c in r['quality']})
    L = ['### The solvers on the twins: quality at matched counted simulations', '',
         'Runs: {0}, Python {1}, budget {2}, {3} seeds per configuration. Quality: for R-PERLE, R-PE and '
         'R-MinRLE the Hausdorff distance between the true images of the returned set and of the efficient set; '
         'for R-SPLINE (on the single-objective twins) the gap to the true minimum cost. Lower is better. '
         'Median, then seeds where CRN is better / same / worse than the default arm on the same seed. '
         '"-": no iteration finished by that checkpoint.'.format(
             len(rows), sorted({r['python'] for r in rows}), sorted({r['budget'] for r in rows}),
             max(len(v) for v in by.values())), '']
    L.append('| solver | problem | finished (crn / default) | '
             + ' | '.join('at {0:,}: default | at {0:,}: crn (better/same/worse)'.format(c) for c in cps) + ' |')
    L.append('|---|---|---|' + '---|---|' * len(cps))
    for solver, problem in sorted({(k[0], k[1]) for k in by}, key=lambda k: (k[0], k[1])):
        crn, dft = by.get((solver, problem, 'crn'), {}), by.get((solver, problem, 'default'), {})
        cells = []
        for c in cps:
            k = str(c)
            dv = [r['quality'][k] for r in dft.values() if r['quality'][k] is not None]
            cv = [r['quality'][k] for r in crn.values() if r['quality'][k] is not None]
            pairs = [(crn[i]['quality'][k], dft[i]['quality'][k]) for i in crn
                     if i in dft and crn[i]['quality'][k] is not None and dft[i]['quality'][k] is not None]
            b = sum(x < y for x, y in pairs)
            e = sum(x == y for x, y in pairs)
            cells.append('{0}'.format('{0:.3g}'.format(med(dv)) if dv else '-'))
            cells.append('{0} ({1}/{2}/{3})'.format('{0:.3g}'.format(med(cv)) if cv else '-', b, e,
                                                   len(pairs) - b - e))
        L.append('| {0} | {1} | {2}/{3} / {4}/{5} | '.format(
            solver, problem, sum(r['finished'] for r in crn.values()), len(crn),
            sum(r['finished'] for r in dft.values()), len(dft)) + ' | '.join(cells) + ' |')
    L.extend(['', 'The control: each pair\'s two default arms have identical marginals, so they should match '
              'in distribution. Desynchronizing twin better / same / worse than the synchronized twin, default '
              'arm, same seed, at the last checkpoint; and the same for the CRN arm.', ''])
    L.append('| solver | pair | default arm | crn arm |')
    L.append('|---|---|---|---|')
    last = str(cps[-1])
    for solver in sorted({k[0] for k in by}):
        for var, fixed in crnsync.TWINS:
            vn, fn = var.__name__, fixed.__name__
            if solver == 'RSPLINE':
                vn, fn = vn + 'SO', fn + 'SO'
            cells = []
            for arm in ('default', 'crn'):     # the header's order
                a, b = by.get((solver, vn, arm), {}), by.get((solver, fn, arm), {})
                pairs = [(a[i]['quality'][last], b[i]['quality'][last]) for i in a
                         if i in b and a[i]['quality'][last] is not None and b[i]['quality'][last] is not None]
                w = sum(x < y for x, y in pairs)
                e = sum(x == y for x, y in pairs)
                cells.append('{0}/{1}/{2}'.format(w, e, len(pairs) - w - e))
            L.append('| {0} | {1} / {2} | {3} | {4} |'.format(solver, vn, fn, *cells))
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

def _q(vals, places=2):
    vals = sorted(v for v in vals if v is not None)
    if not vals:
        return '-'
    f = '{0:.%df}' % places
    if len(vals) < 4:
        return f.format(statistics.median(vals))
    q = statistics.quantiles(vals, n=4)
    return '{0} ({1}-{2})'.format(f.format(statistics.median(vals)), f.format(q[0]), f.format(q[2]))


def report(path, out, runs=None):
    d = json.load(open(path))
    names = ('holding', 'shortage')
    L = ['<!-- generated by docs/bench_crn.py report; do not edit -->', '',
         'Python {0}, seed {1}. Counted, not timed.'.format(d['python'], d['seed'][0]), '']
    L.extend(['### The twins over the whole box', '',
              '{0} replications per point; every axis pair (x, x + e_i) in the box. Correlation and variance '
              'ratio Var(g(x) - g(y)) / (Var g(x) + Var g(y)) per objective: median (quartiles) over pairs. '
              'A ratio of 1 is independent sampling; below 1 CRN helps, above 1 it hurts. "CI excludes 0": '
              'pairs whose 95% interval for the correlation lies above zero. Draws differ: the share of '
              'replications whose total draw counts differ, mean over pairs.'.format(d['reps']), ''])
    L.append('| problem | arm | objective | correlation | variance ratio | CI above 0 | CI below 0 | draws differ |')
    L.append('|---|---|---|---|---|---|---|---|')
    for prob in [c.__name__ for c in ORDER]:
        for arm in ARMS:
            rs = [r for r in d['lattice'] if r['problem'] == prob and r['arm'] == arm]
            for k, nm in enumerate(names):
                valid = [r for r in rs if r['rho'][k] is not None]
                L.append('| {0} | {1} | {2} | {3} | {4} | {5}/{6} | {7}/{6} | {8:.1%} |'.format(
                    prob, arm, nm, _q(r['rho'][k] for r in rs), _q((r['vr'][k] for r in rs), 3),
                    sum(r['lo'][k] > 0 for r in valid), len(valid), sum(r['hi'][k] < 0 for r in valid),
                    statistics.fmean(r['differ'] for r in rs)))
    L.extend(['', 'Marginals without CRN, each pair\'s identical-distribution argument checked: largest |z| over '
              '{0} points x 2 objectives of each twin\'s mean against the closed form, of the twins\' means '
              'against each other, and of their variances.'.format(d['lattice_points']), ''])
    L.append('| pair | desynchronizing twin vs closed form | synchronized twin vs closed form | means | variances |')
    L.append('|---|---|---|---|---|')
    for var, fixed in crnsync.TWINS:
        m = d['marginals'][var.__name__]
        L.append('| {0} / {1} | {2:.2f} | {3:.2f} | {4:.2f} | {5:.2f} |'.format(
            var.__name__, fixed.__name__, m['var_vs_exact'], m['fixed_vs_exact'], m['twins_means'],
            m['twins_variances']))
    L.append('')
    L.extend(['### Periods in a replication (T), CRN', '',
              '{0} replications per point; pairs from x in {{2, 9, 16}}^2 along both axes. "Same count": the '
              'mean share of a replication\'s periods completed before the two points\' cumulative draw counts '
              'first part. "In role": the mean share of periods that start on the same raw draw at both points '
              '(each reads that uniform as item 1\'s demand), at whatever period index. The synchronized twins: '
              'both always 100%.'.format(d['sweep_reps']), ''])
    L.append('| T | problem | same count | in role | holding correlation | shortage correlation | holding ratio | '
             'shortage ratio |')
    L.append('|---|---|---|---|---|---|---|---|')
    for periods in d['sweep_t']:
        for prob in [c.__name__ for c in ORDER]:
            rs = [r for r in d['sweep'] if r['periods'] == periods and r['problem'] == prob]
            L.append('| {0} | {1} | {2:.0%} | {3:.0%} | {4} | {5} | {6} | {7} |'.format(
                periods, prob, statistics.fmean(r['in_step'] for r in rs), statistics.fmean(r['in_role'] for r in rs),
                _q(r['rho'][0] for r in rs), _q(r['rho'][1] for r in rs), _q((r['vr'][0] for r in rs), 3),
                _q((r['vr'][1] for r in rs), 3)))
    L.extend(['', '### Misaligned on purpose: a point against itself, k raw draws later', '',
              'x = {0}, T = {1}, CRN streams, {2} replications. Replication j at x against x simulated from the '
              'same stream advanced by k raw draws: misaligned from the first draw, with no x-dependence. '
              'Correlation per objective.'.format(tuple(d['shift'][0]['x']), d['shift'][0]['periods'],
                                                  d['shift_reps']), ''])
    names_in = [c.__name__ for c in ORDER]
    L.append('| k | ' + ' | '.join('{0} {1}'.format(n, o) for n in names_in for o in ('holding', 'shortage')) + ' |')
    L.append('|---|' + '---|' * (2 * len(names_in)))
    sh = {(r['problem'], r['shift']): r['rho'] for r in d['shift']}
    for k in sorted({r['shift'] for r in d['shift']}):
        L.append('| {0} | '.format(k) + ' | '.join('{0:.3f}'.format(v) for n in names_in for v in sh[(n, k)]) + ' |')
    L.extend(['', '### randint over a range that grows with x', '',
              'RandRange, g = randint(0, 4 + x) + Z, {0} replications per point; pair (x, x + 1). Under CRN, '
              'per pair.'.format(d['randrange_reps']), ''])
    L.append('| x | range | correlation (CRN) | variance ratio (CRN) | draws differ (CRN) | correlation (default) |')
    L.append('|---|---|---|---|---|---|')
    crn = {tuple(r['x']): r for r in d['randrange'] if r['arm'] == 'crn'}
    dft = {tuple(r['x']): r for r in d['randrange'] if r['arm'] == 'default'}
    for x in sorted(crn):
        r, s = crn[x], dft[x]
        L.append('| {0} | 0..{1} vs 0..{2} | {3:.3f} | {4:.3f} | {5:.1%} | {6:.3f} |'.format(
            x[0], r['range'], r['range'] + 1, r['rho'][0], r['vr'][0], r['differ'], s['rho'][0]))
    L.extend(['', '### The built-in problems', '',
              '{0} replications per point, {1} points per problem from its tester\'s get_ranx0, every axis pair '
              '(x, x + e_i) with both feasible. Median (quartiles) over pairs.'.format(d['builtin_reps'],
                                                                                       d['builtin_points']), ''])
    L.append('| problem | arm | pairs | objective 1 correlation | objective 2 correlation | objective 1 ratio | '
             'objective 2 ratio | draws differ |')
    L.append('|---|---|---|---|---|---|---|---|')
    for name, _, _ in BUILTINS:
        for arm in ARMS:
            rs = [r for r in d['builtins'] if r['problem'] == name and r['arm'] == arm]
            nobj = len(rs[0]['rho'])
            cell = lambda key, k: _q(r[key][k] for r in rs) if k < nobj else '-'  # noqa: E731
            L.append('| {0} | {1} | {2} | {3} | {4} | {5} | {6} | {7:.1%} |'.format(
                name, arm, len(rs), cell('rho', 0), cell('rho', 1), cell('vr', 0), cell('vr', 1),
                statistics.fmean(r['differ'] for r in rs)))
    if runs is not None:
        L.extend([''] + report_runs(runs))
    with open(out, 'w') as f:
        f.write('\n'.join(L) + '\n')


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else ''
    if cmd == 'calibrate':
        calibrate()
    elif cmd == 'verify':
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
