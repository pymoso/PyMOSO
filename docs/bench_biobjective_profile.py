"""
Where R-PERLE, R-MinRLE and R-SPLINE spend a run at two objectives,
when g() costs something (docs/phase7-plan.md, step 1). Observes;
changes nothing under pymoso/.

Method. ProbExpensive's burn never reads x or the stream, so a run's
trajectory -- every point, every replication, the end seed -- is the
same at every cost tier. Each configuration is therefore profiled once
at burn 0, where the framework's own costs are visible, and its wall
time at a tier is

    framework seconds (burn 0, uninstrumented) + feasible g() calls * burn seconds

The burn is skipped for an infeasible point, hence "feasible". That
is a model, and `validate` tests it: it runs the real tier classes
through chnutils.solve(), interleaved with the burn-0 class, and
requires the same solution and end seed before comparing the time.

Three modes, never mixed in one run, because wrappers distort times:
- 'time': exclusive wall time per region (a region's time excludes
  the regions nested in it). Regions are the solver routines, the
  dominance/neighbourhood helpers, the oracle (`hit`/`hit_many` own
  bookkeeping), `streams` (turning a coordinate into a stream: the
  jump and the per-replication advances), `aggregate` and `g`.
- 'count': calls, and the quantities the algorithm's requirements are
  derived from: g() calls feasible and infeasible, blocks and the
  ones that repeat a point already simulated in the same iteration,
  stream_at calls, estimate() calls answered from the iteration's
  cache, dominance predicate calls per region, get_nondom's sizes,
  get_ncn's sizes and the predicate calls an early exit in the same
  order would need, calc_delta calls, ne's neighbours examined.
- 'plain': no wrappers at all; the wall time the model uses.

Patches reach their callers through the names those callers read
(CLAUDE.md, Testing): `rle`/`get_min` read `chnbase.get_nondom`;
`pe` reads `rperle.get_biparetos`; `get_ncn` reads `chnbase.does_*`,
`chnbase.get_setnbors` and `chnbase.get_nbors`; `remove_nlwep` reads
`chnbase.is_lwep`, which reads `moso.does_strict_dominate`; `front`
reads `moso.does_dominate`. Every run records each region's call
count, and `check_reached` fails a run in which an expected region
was never entered.

Usage (from the repository root, quiet machine, `uptime` first):
    python docs/bench_biobjective_profile.py run RESULTS.jsonl
    python docs/bench_biobjective_profile.py validate RESULTS.jsonl
    python docs/bench_biobjective_profile.py report RESULTS.jsonl > docs/biobjective-profile-tables.md
`run` and `validate` append, and skip work already in the file.
"""
import contextlib
import io
import json
import os
import statistics
import sys
import time

import pymoso.chnbase as chnbase
import pymoso.moso as moso
import pymoso.solvers.rperle as rperle_mod
from pymoso.chnutils import solve
from pymoso.executor import SerialExecutor
from pymoso.layout import get_solv_prnstreams
from pymoso.oracle import Oracle
from pymoso.paths import isp_run
from pymoso.prng import registry
from pymoso.problems import probexpensive as pe_mod
from pymoso.solvers.rminrle import RMINRLE
from pymoso.solvers.rperle import RPERLE
from pymoso.solvers.rspline import RSPLINE

SOLVERS = {'RPERLE': RPERLE, 'RMINRLE': RMINRLE, 'RSPLINE': RSPLINE}
# Problem families: the burn-0 base class, then the tiers by name.
PROBLEMS = {
    'Bi': (pe_mod.ProbExpensiveBi, {'Light': pe_mod.ProbExpensiveBiLight,
                                    'Moderate': pe_mod.ProbExpensiveBiModerate,
                                    'Heavy': pe_mod.ProbExpensiveBiHeavy}),
    'One': (pe_mod.ProbExpensive, {'Light': pe_mod.ProbExpensiveLight,
                                   'Moderate': pe_mod.ProbExpensiveModerate,
                                   'Heavy': pe_mod.ProbExpensiveHeavy}),
}
PROBLEMS['BiEdge'] = PROBLEMS['Bi']
# BiEdge starts at the second objective's minimizer, (0, 20), on the
# boundary that ProbTPA's efficient set touches; from (30, 30) the
# solvers do not reach that boundary within the budget, and so never
# simulate an infeasible point.
X0 = {'Bi': (30, 30), 'BiEdge': (0, 20), 'One': (97,)}
# (solver, problem family). R-SPLINE is single-objective: on the
# bi-objective problem it minimizes the first objective, in two
# dimensions; on 'One' it is the one-dimensional benchmark the other
# docs use.
CONFIGS = [('RPERLE', 'Bi'), ('RMINRLE', 'Bi'), ('RPERLE', 'BiEdge'), ('RMINRLE', 'BiEdge'),
           ('RSPLINE', 'Bi'), ('RSPLINE', 'One')]
GENERATORS = ('mrg32k3a', 'philox4x32')
SEEDS = {
    'mrg32k3a': [(12345,) * 6, (42,) * 6, (271828,) * 6],
    'philox4x32': [(12345, 12345), (42, 42), (271828, 271828)],
}
BUDGET = 10_000

ALGO_REGIONS = ('pe', 'get_min', 'rle', 'get_ncn', 'remove_nlwep', 'seek_lwep',
                'spsolve', 'spline', 'ne', 'spli', 'pli', 'upsample')
HELPER_REGIONS = ('get_nondom', 'get_biparetos', 'is_lwep', 'nbors')
SIM_REGIONS = ('estimate', 'oracle', 'streams', 'aggregate', 'g')
OTHER_REGIONS = ('endseed',)
REGIONS = ALGO_REGIONS + HELPER_REGIONS + SIM_REGIONS + OTHER_REGIONS


class Probe:
    def __init__(self, mode):
        self.mode = mode
        self.stack = []                       # [name, start, child seconds]
        self.excl = {r: 0.0 for r in REGIONS}
        self.calls = {r: 0 for r in REGIONS}
        self.c = {}                           # free-form counters
        self.lists = {}                       # free-form per-call records

    def bump(self, key, by=1):
        self.c[key] = self.c.get(key, 0) + by

    def record(self, key, value):
        self.lists.setdefault(key, []).append(value)

    def owner(self):
        """The innermost algorithm region: who asked for the work."""
        for frame in reversed(self.stack):
            if frame[0] in ALGO_REGIONS:
                return frame[0]
        return 'other'

    def top(self):
        return self.stack[-1][0] if self.stack else 'other'

    @contextlib.contextmanager
    def region(self, name):
        self.calls[name] += 1
        if self.mode != 'time':
            self.stack.append([name, 0.0, 0.0])
            try:
                yield
            finally:
                self.stack.pop()
            return
        frame = [name, time.perf_counter(), 0.0]
        self.stack.append(frame)
        try:
            yield
        finally:
            self.stack.pop()
            elapsed = time.perf_counter() - frame[1]
            self.excl[name] += elapsed - frame[2]
            if self.stack:
                self.stack[-1][2] += elapsed


PROBE = None
# The shadow computations below must not be counted as the solver's.
_ORIG_SDOM = moso.does_strict_dominate
_ORIG_WDOM = moso.does_weak_dominate
_ORIG_DOM = moso.does_dominate


class Patches:
    def __init__(self):
        self._undo = []

    def set(self, owner, name, value):
        self._undo.append((owner, name, getattr(owner, name)))
        setattr(owner, name, value)

    def undo(self):
        for owner, name, value in reversed(self._undo):
            setattr(owner, name, value)
        self._undo = []


def _regioned(region, fn, before=None, after=None):
    def wrapped(*args, **kwargs):
        state = None
        if before is not None:
            state = before(*args, **kwargs)
        with PROBE.region(region):
            out = fn(*args, **kwargs)
        if after is not None:
            after(state, out, *args, **kwargs)
        return out
    wrapped.__wrapped__ = fn
    return wrapped


def _counted(label, fn):
    def wrapped(*args, **kwargs):
        PROBE.bump(('pred', PROBE.top(), label))
        return fn(*args, **kwargs)
    return wrapped


# --- count-mode observers ---------------------------------------------

def _estimate_before(self, x, *a, **k):
    PROBE.bump(('estimate', PROBE.owner(), 'cached' if x in self.gbar else 'asked'))


def _estimate_many_before(self, points, *a, **k):
    points = list(points)
    cached = sum(1 for x in points if x in self.gbar)
    PROBE.bump(('estimate_many', PROBE.owner(), 'points'), len(points))
    PROBE.bump(('estimate_many', PROBE.owner(), 'cached'), cached)
    PROBE.bump(('estimate_many', PROBE.owner(), 'distinct_uncached'),
               len({x for x in points if x not in self.gbar}))


def _plan_hit_after(state, block, self, x, m, *a, **k):
    if block is None:
        return
    key = (self._iteration, x)
    seen = PROBE.lists.setdefault('_seen', {})
    owner = PROBE.owner()
    PROBE.bump(('blocks', owner))
    PROBE.bump(('block_reps', owner), m)
    if key in seen:
        PROBE.bump(('repeat_blocks', owner))
        PROBE.bump(('repeat_reps', owner), m)
    seen[key] = seen.get(key, 0) + 1


def _get_nondom_before(edict):
    return PROBE.c.get(('pred', 'get_nondom', 'moso.does_dominate'), 0)


def _get_nondom_after(before, out, edict):
    after = PROBE.c.get(('pred', 'get_nondom', 'moso.does_dominate'), 0)
    PROBE.record('get_nondom', (len(edict), after - before, len(out), _bounded_front_calls(edict)))


def _bounded_front_calls(edict):
    """does_dominate calls get_nondom would make with front's merge
    loop bounded at the first half's length (docs/phase7-plan.md,
    step 2): the same sort, the same recursion, the same order."""
    calls = [0]

    def front(points, objs):
        if len(points) <= 1:
            return list(points), list(objs)
        half = int(len(points) / 2)
        tp, to = front(points[:half], objs[:half])
        bp, bo = front(points[half:], objs[half:])
        bound = len(tp)
        for pt, gv in zip(bp, bo):
            z = [0] * len(gv)
            nondom = True
            j = 0
            while j < bound and nondom:
                calls[0] += 1
                if _ORIG_DOM(to[j], gv, z, z):
                    nondom = False
                j += 1
            if nondom:
                tp.append(pt)
                to.append(gv)
        return tp, to

    pts = list(edict.keys())
    vals = list(edict.values())
    order = moso.argsort(vals)
    front([pts[i] for i in order], [vals[i] for i in order])
    return calls[0]


def _get_ncn_before(self, mcS):
    return set(mcS)


def _get_ncn_after(mcS, ncn, self, _mcS):
    """The quantities get_ncn's requirement is derived from, computed
    afterwards with the unwrapped predicates on the same estimates."""
    r = self.nbor_rad
    d = self.num_obj
    z = tuple(0 for _ in range(d))
    nb = moso.get_nbors
    sdom, wdom, dom = _ORIG_SDOM, _ORIG_WDOM, _ORIG_DOM
    delta = lambda se: se / pow(self.m, self.betadel)
    pairs = [(s, x) for s in mcS for x in nb(s, r) - mcS]
    feas_pairs = [(s, x) for s, x in pairs if x in self.gbar]
    # (a) with an early exit: skip a pair whose x is already known to be in ncn.
    ncn_a = set()
    need_a = 0
    for s, x in feas_pairs:
        if x in ncn_a:
            continue
        need_a += 1
        if sdom(self.gbar[x], self.gbar[s], z, z):
            ncn_a.add(x)
    delN = moso.get_setnbors(mcS, r)
    cands = [x for x in delN - ncn_a if x in self.gbar]
    # (b) with an early exit: stop at the first s that rules x out, and
    # evaluate (iii) only while it can still matter.
    need_b = 0
    shadow = set(ncn_a)
    dels = {s: tuple(delta(self.sehat[s][i]) for i in range(d)) for s in mcS}
    for x in cands:
        fx = self.gbar[x]
        delx = tuple(delta(self.sehat[x][i]) for i in range(d))
        doesweakdom = False
        wouldnotchange = True
        ruled_out = False
        for s in mcS:
            fs = self.gbar[s]
            need_b += 1
            if wdom(fs, fx, z, z):
                ruled_out = True
                break
            need_b += 1
            if dom(fx, fs, z, z):
                need_b += 1
                if wdom(fs, fx, dels[s], delx):
                    ruled_out = True
                    break
            if not doesweakdom:
                need_b += 1
                doesweakdom = wdom(fx, fs, z, z)
            if not doesweakdom and wouldnotchange:
                need_b += 1
                if wdom(fs, fx, dels[s], delx):
                    wouldnotchange = False
                else:
                    need_b += 1
                    if wdom(fx, fs, delx, dels[s]):
                        wouldnotchange = False
        if not ruled_out and (doesweakdom or wouldnotchange):
            shadow.add(x)
    if shadow != ncn:
        raise AssertionError('get_ncn shadow decided differently: the early-exit count is not for the same answer')
    PROBE.bump(('ncn_shadow_checked',))
    PROBE.record('get_ncn', dict(S=len(mcS), pairs=len(pairs), feas_pairs=len(feas_pairs),
                                 need_a=need_a, delN=len(delN), cands=len(cands),
                                 need_b=need_b, ncn=len(ncn)))


def _ne_after(state, out, self, x, *a, **k):
    PROBE.record('ne', (len(x), out[3] // self.m if self.m else 0, out[0] != x))


@contextlib.contextmanager
def instrumented(mode, problem_base):
    global PROBE
    PROBE = Probe(mode)
    p = Patches()
    if mode == 'plain':
        try:
            yield PROBE
        finally:
            p.undo()
        return
    counting = mode == 'count'
    for cls, name, region in [
        (RPERLE, 'pe', 'pe'), (chnbase.RASolver, 'get_min', 'get_min'),
        (chnbase.RLESolver, 'rle', 'rle'), (chnbase.RLESolver, 'get_ncn', 'get_ncn'),
        (chnbase.RASolver, 'remove_nlwep', 'remove_nlwep'),
        (chnbase.RLESolver, 'seek_lwep', 'seek_lwep'), (RSPLINE, 'spsolve', 'spsolve'),
        (chnbase.RASolver, 'spline', 'spline'), (chnbase.RASolver, 'ne', 'ne'),
        (chnbase.RASolver, 'spli', 'spli'), (chnbase.RASolver, 'pli', 'pli'),
        (chnbase.RASolver, 'upsample', 'upsample'),
        (chnbase.RASolver, 'estimate', 'estimate'),
        (chnbase.RASolver, 'estimate_many', 'estimate'),
        (Oracle, 'hit', 'oracle'), (Oracle, 'hit_many', 'oracle'),
        (Oracle, '_aggregate', 'aggregate'), (SerialExecutor, 'streams', 'streams'),
        (problem_base, 'g', 'g'), (Oracle, 'get_endseed', 'endseed'),
    ]:
        before = after = None
        if counting:
            before = {'estimate': _estimate_before,
                      'estimate_many': _estimate_many_before,
                      'get_ncn': _get_ncn_before}.get(name)
            after = {'get_ncn': _get_ncn_after, 'ne': _ne_after}.get(name)
        p.set(cls, name, _regioned(region, getattr(cls, name), before, after))
    for owner, name, region in [
        (chnbase, 'get_nondom', 'get_nondom'), (rperle_mod, 'get_biparetos', 'get_biparetos'),
        (chnbase, 'is_lwep', 'is_lwep'), (chnbase, 'get_setnbors', 'nbors'),
        (chnbase, 'get_nbors', 'nbors'),
    ]:
        before = after = None
        if counting and name == 'get_nondom':
            before, after = _get_nondom_before, _get_nondom_after
        p.set(owner, name, _regioned(region, getattr(owner, name), before, after))
    if counting:
        p.set(Oracle, '_plan_hit', _regioned('oracle', Oracle._plan_hit, None, _plan_hit_after))
        real_g = problem_base.g.__wrapped__

        def g(self, x, rng):
            isfeas, objs = real_g(self, x, rng)
            PROBE.bump(('g', PROBE.owner(), 'feasible' if isfeas else 'infeasible'))
            return isfeas, objs
        p.set(problem_base, 'g', _regioned('g', g))
        p.set(chnbase.RLESolver, 'calc_delta',
              _regioned_count('calc_delta', chnbase.RLESolver.calc_delta))
        for name in ('does_dominate', 'does_weak_dominate', 'does_strict_dominate'):
            p.set(chnbase, name, _counted('chnbase.' + name, getattr(chnbase, name)))
        for name in ('does_dominate', 'does_strict_dominate'):
            p.set(moso, name, _counted('moso.' + name, getattr(moso, name)))
        for gen in GENERATORS:
            backend = registry.get_generator(gen)
            p.set(backend, 'stream_at', _counted('stream_at', backend.stream_at))
    try:
        yield PROBE
    finally:
        p.undo()


def _regioned_count(label, fn):
    def wrapped(*args, **kwargs):
        PROBE.bump((label, PROBE.owner()))
        return fn(*args, **kwargs)
    return wrapped


def run_one(solver, family, generator, seed, mode, budget=BUDGET, problem=None):
    """One instrumented run, set up as chnutils.solve() sets one up."""
    base, _ = PROBLEMS[family]
    problem = problem or base
    backend = registry.get_generator(generator)
    orcstream, solvstream = get_solv_prnstreams(seed, backend)
    orc = problem(orcstream)
    orc.set_crnflag(False)
    with instrumented(mode, base) as probe, contextlib.redirect_stdout(io.StringIO()):
        t0 = time.perf_counter()
        c0 = time.process_time()
        with orc.set_simpar(1):
            res = isp_run(SOLVERS[solver], budget, orc, solvprn=solvstream, x0=X0[family])
        wall = time.perf_counter() - t0
        cpu = time.process_time() - c0
    last = max(res['itersoln'])
    out = dict(solver=solver, family=family, generator=generator, seed=list(seed), mode=mode,
               budget=budget, wall=wall, cpu=cpu, iterations=last,
               simcalls=res['simcalls'][last], soln=sorted(res['itersoln'][last]),
               endseed=list(res['endseed']),
               sizes=[len(res['itersoln'][nu]) for nu in sorted(res['itersoln'])],
               python=sys.version.split()[0])
    if mode == 'time':
        out['excl'] = probe.excl
        out['calls'] = probe.calls
    elif mode == 'count':
        out['calls'] = probe.calls
        out['counts'] = [[list(k), v] for k, v in probe.c.items()]
        out['lists'] = {k: v for k, v in probe.lists.items() if not k.startswith('_')}
    return out


EXPECTED = {
    'RPERLE': ('pe', 'get_min', 'rle', 'get_ncn', 'remove_nlwep', 'spline', 'ne', 'spli', 'pli',
               'upsample', 'get_nondom', 'get_biparetos', 'is_lwep', 'nbors') + SIM_REGIONS,
    'RMINRLE': ('get_min', 'rle', 'get_ncn', 'remove_nlwep', 'spline', 'ne', 'spli', 'pli',
                'upsample', 'get_nondom', 'is_lwep', 'nbors') + SIM_REGIONS,
    'RSPLINE': ('spsolve', 'spline', 'ne', 'spli', 'pli', 'upsample') + SIM_REGIONS,
}


def check_reached(row):
    missing = [r for r in EXPECTED[row['solver']] if not row['calls'].get(r)]
    if missing:
        raise AssertionError('{0}: regions never entered: {1}'.format(_key(row), missing))


def _key(row):
    return '{solver}/{family}/{generator}/{seed}/{mode}'.format(**row)


def burn_seconds(units, repeats=30):
    """Median seconds for one replication's burn at `units`."""
    times = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        pe_mod._burn(units)
        times.append(time.perf_counter() - t0)
    return statistics.median(times)


def _load(path):
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def _append(path, row):
    with open(path, 'a') as f:
        f.write(json.dumps(row) + '\n')


def run(path, configs=CONFIGS, generators=GENERATORS, seeds=None, budget=BUDGET,
        modes=('plain', 'time', 'count', 'plain'), verbose=True):
    """Each configuration in every mode; 'plain' twice, first and last,
    so the two uninstrumented times bracket the instrumented ones."""
    done = {(_key(r), i) for i, r in _indexed(_load(path))}
    for solver, family in configs:
        for gen in generators:
            for seed in (seeds or SEEDS)[gen]:
                reference = None
                for i, mode in enumerate(modes):
                    row0 = dict(solver=solver, family=family, generator=gen, seed=list(seed), mode=mode)
                    if (_key(row0), modes[:i].count(mode)) in done:
                        continue
                    row = run_one(solver, family, gen, tuple(seed), mode, budget)
                    row['load'] = os.getloadavg()
                    if mode != 'plain':
                        check_reached(row)
                    if reference is None:
                        reference = (row['soln'], row['endseed'])
                    elif (row['soln'], row['endseed']) != reference:
                        raise AssertionError('{0}: instrumentation changed the run'.format(_key(row)))
                    _append(path, row)
                    if verbose:
                        print('{0}: {1:.2f}s, {2} sims, load {3:.2f}'.format(
                            _key(row), row['wall'], row['simcalls'], row['load'][0]), flush=True)


def _indexed(rows):
    seen = {}
    for r in rows:
        k = _key(r)
        yield seen.get(k, 0), r
        seen[k] = seen.get(k, 0) + 1


def validate(path, tiers=('Light', 'Moderate'), configs=CONFIGS, generator='mrg32k3a',
             seed=None, budget=BUDGET, verbose=True):
    """Each tier through chnutils.solve(), interleaved with burn 0:
    base, tier, base, tier. The tier must return burn 0's solution and
    end seed; its time is compared with the model's prediction."""
    seed = tuple(seed or SEEDS[generator][0])
    done = {(r['solver'], r['family'], r['tier'], r['rep']) for r in _load(path) if r.get('mode') == 'validate'}
    for solver, family in configs:
        base, classes = PROBLEMS[family]
        for tier in tiers:
            for rep in (0, 1):
                if (solver, family, tier, rep) in done:
                    continue
                times = {}
                answers = {}
                for label, cls in (('base', base), ('tier', classes[tier])):
                    with contextlib.redirect_stdout(io.StringIO()):
                        t0 = time.perf_counter()
                        soln, endseed = solve(cls, SOLVERS[solver], X0[family], budget=budget,
                                              generator=generator, seed=seed)
                        times[label] = time.perf_counter() - t0
                    answers[label] = (sorted(soln), list(endseed))
                if answers['base'] != answers['tier']:
                    raise AssertionError('{0} {1}: the tier changed the run'.format(solver, tier))
                row = dict(mode='validate', solver=solver, family=family, tier=tier, rep=rep,
                           generator=generator, seed=list(seed), budget=budget,
                           base_wall=times['base'], tier_wall=times['tier'],
                           burn=burn_seconds(classes[tier].burn_units),
                           load=os.getloadavg(), python=sys.version.split()[0])
                _append(path, row)
                if verbose:
                    print('{0}/{1} {2} rep {3}: base {4:.1f}s tier {5:.1f}s'.format(
                        solver, family, tier, rep, times['base'], times['tier']), flush=True)


# --- report -----------------------------------------------------------

def _counts(row):
    return {tuple(k): v for k, v in row['counts']}


def _sum(counts, head, *rest):
    return sum(v for k, v in counts.items() if k[0] == head and all(
        a is None or a == b for a, b in zip(rest, k[1:])))


def _cfg(row):
    return (row['solver'], row['family'], row['generator'])


def _fmt(x, digits=1):
    return '{0:,.{1}f}'.format(x, digits)


GROUPS = [
    ('g() at burn 0', ('g',)),
    ('coordinate -> stream (jump)', ('streams',)),
    ('oracle bookkeeping', ('oracle', 'aggregate')),
    ('estimate cache', ('estimate',)),
    ('get_ncn (own)', ('get_ncn',)),
    ('remove_nlwep + is_lwep', ('remove_nlwep', 'is_lwep')),
    ('get_nondom', ('get_nondom',)),
    ('get_biparetos + pe', ('get_biparetos', 'pe')),
    ('SPLINE (spline, ne, spli, pli)', ('spline', 'ne', 'spli', 'pli')),
    ('everything else', ('get_min', 'rle', 'seek_lwep', 'spsolve', 'upsample', 'nbors')),
]


def report(path, tiers=('Light', 'Moderate', 'Heavy'), out=sys.stdout):
    rows = _load(path)
    p = lambda *a: print(*a, file=out)
    configs = []
    for r in rows:
        if r['mode'] != 'validate' and _cfg(r) not in configs:
            configs.append(_cfg(r))
    burns = {}
    for r in rows:
        if r['mode'] == 'validate':
            burns.setdefault(r['tier'], []).append(r['burn'])
    burn = {t: statistics.median(v) for t, v in burns.items()}
    p('<!-- Generated by docs/bench_biobjective_profile.py report. Do not edit. -->')
    p('')
    p('# Bi-objective profile: tables')
    p('')
    p('Budget {0:,} per run; every row is the mean over seeds unless it says otherwise. '
      'Python {1}. Load averages (1-minute) over the runs: {2:.2f}-{3:.2f}.'.format(
          rows[0]['budget'], rows[0]['python'],
          min(r['load'][0] for r in rows), max(r['load'][0] for r in rows)))
    p('')
    p('## Run shape (count mode)')
    p('')
    p('| solver | problem | generator | seeds | iterations | simcalls | g() feasible | g() infeasible '
      '| blocks (hits) | blocks repeating a point | stream_at calls | final m | mean |S| |')
    p('|---|---|---|---|---|---|---|---|---|---|---|---|---|')
    for cfg in configs:
        cr = [r for r in rows if _cfg(r) == cfg and r['mode'] == 'count']
        mean = lambda f: statistics.mean(f(r) for r in cr)
        p('| {0} | {1} | {2} | {3} | {4} | {5} | {6} | {7} | {8} | {9} | {10} | {11} | {12} |'.format(
            *cfg, len(cr), _fmt(mean(lambda r: r['iterations'])), _fmt(mean(lambda r: r['simcalls']), 0),
            _fmt(mean(lambda r: _sum(_counts(r), 'g', None, 'feasible')), 0),
            _fmt(mean(lambda r: _sum(_counts(r), 'g', None, 'infeasible')), 0),
            _fmt(mean(lambda r: _sum(_counts(r), 'blocks')), 0),
            _fmt(mean(lambda r: _sum(_counts(r), 'repeat_blocks')), 0),
            _fmt(mean(lambda r: _sum(_counts(r), 'pred', None, 'stream_at')), 0),
            _fmt(mean(lambda r: _m_final(r)), 0),
            _fmt(mean(lambda r: statistics.mean(r['sizes'][1:])), 1)))
    p('')
    p('## Where the framework time goes at burn 0 (time mode, exclusive seconds, % of the instrumented run)')
    p('')
    p('| solver | problem | generator | plain wall (s) | instrumented wall (s) | '
      + ' | '.join(g for g, _ in GROUPS) + ' | end seed | unattributed |')
    p('|' + '---|' * (7 + len(GROUPS)))
    for cfg in configs:
        tr = [r for r in rows if _cfg(r) == cfg and r['mode'] == 'time']
        pr = [r for r in rows if _cfg(r) == cfg and r['mode'] == 'plain']
        cells = []
        for _, regs in GROUPS:
            secs = statistics.mean(sum(r['excl'][g] for g in regs) for r in tr)
            share = statistics.mean(sum(r['excl'][g] for g in regs) / r['wall'] for r in tr)
            cells.append('{0} ({1}%)'.format(_fmt(secs, 2), _fmt(100 * share)))
        for regs in (('endseed',), None):
            if regs is None:
                secs = statistics.mean(r['wall'] - sum(r['excl'].values()) for r in tr)
                share = statistics.mean((r['wall'] - sum(r['excl'].values())) / r['wall'] for r in tr)
            else:
                secs = statistics.mean(sum(r['excl'][g] for g in regs) for r in tr)
                share = statistics.mean(sum(r['excl'][g] for g in regs) / r['wall'] for r in tr)
            cells.append('{0} ({1}%)'.format(_fmt(secs, 2), _fmt(100 * share)))
        p('| {0} | {1} | {2} | {3} | {4} | '.format(
            *cfg, _fmt(statistics.mean(r['wall'] for r in pr), 2),
            _fmt(statistics.mean(r['wall'] for r in tr), 2)) + ' | '.join(cells) + ' |')
    p('')
    if burn:
        p('## Modelled share of wall time at each tier (MODEL: plain burn-0 wall + feasible g() x median burn)')
        p('')
        p('Burn per replication, measured (median): ' + ', '.join(
            '{0} {1} ms'.format(t, _fmt(1000 * burn[t], 2)) for t in tiers if t in burn) + '.')
        p('')
        p('| solver | problem | generator | tier | modelled wall (s) | simulation (burn + g) | '
          'jump | get_ncn + remove_nlwep + is_lwep | get_nondom | everything else |')
        p('|---|---|---|---|---|---|---|---|---|---|')
        for cfg in configs:
            tr = [r for r in rows if _cfg(r) == cfg and r['mode'] == 'time']
            pr = [r for r in rows if _cfg(r) == cfg and r['mode'] == 'plain']
            cr = [r for r in rows if _cfg(r) == cfg and r['mode'] == 'count']
            plain = statistics.mean(r['wall'] for r in pr)
            inst = statistics.mean(r['wall'] for r in tr)
            share = lambda regs: statistics.mean(sum(r['excl'][g] for g in regs) / r['wall'] for r in tr)
            feas = statistics.mean(_sum(_counts(r), 'g', None, 'feasible') for r in cr)
            for t in tiers:
                if t not in burn:
                    continue
                b = feas * burn[t]
                total = plain + b
                # Exclusive shares from the instrumented run, scaled to the plain wall.
                sim = plain * share(('g',)) + b
                jump = plain * share(('streams',))
                ncn = plain * share(('get_ncn', 'remove_nlwep', 'is_lwep'))
                nd = plain * share(('get_nondom',))
                rest = total - sim - jump - ncn - nd
                p('| {0} | {1} | {2} | {3} | {4} | {5}% | {6}% | {7}% | {8}% | {9}% |'.format(
                    *cfg, t, _fmt(total), _fmt(100 * sim / total), _fmt(100 * jump / total),
                    _fmt(100 * ncn / total, 2), _fmt(100 * nd / total, 2), _fmt(100 * rest / total)))
        p('')
        p('### The jump against simulation (MODEL, from the burn-0 runs)')
        p('')
        p('Per-replication g() cost at which the jump is a given share of the run, '
          'ignoring the rest of the framework: c = J(1-f)/(f F), J the jump seconds, F the feasible g() calls.')
        p('')
        p('| solver | problem | generator | jump (s) | blocks | jump per block (ms) | feasible g() per block | g() cost for jump = 50% | for 10% | for 1% |')
        p('|---|---|---|---|---|---|---|---|---|---|')
        for cfg in configs:
            tr = [r for r in rows if _cfg(r) == cfg and r['mode'] == 'time']
            pr = [r for r in rows if _cfg(r) == cfg and r['mode'] == 'plain']
            cr = [r for r in rows if _cfg(r) == cfg and r['mode'] == 'count']
            plain = statistics.mean(r['wall'] for r in pr)
            J = plain * statistics.mean(r['excl']['streams'] / r['wall'] for r in tr)
            F = statistics.mean(_sum(_counts(r), 'g', None, 'feasible') for r in cr)
            B = statistics.mean(_sum(_counts(r), 'blocks') for r in cr)
            c = lambda f: J * (1 - f) / (f * F)
            p('| {0} | {1} | {2} | {3} | {4} | {5} | {6} | {7} ms | {8} ms | {9} ms |'.format(
                *cfg, _fmt(J, 2), _fmt(B, 0), _fmt(1000 * J / B, 3), _fmt(F / B, 1),
                _fmt(1000 * c(0.5), 3), _fmt(1000 * c(0.1), 2), _fmt(1000 * c(0.01), 1)))
        p('')
        vr = [r for r in rows if r['mode'] == 'validate']
        if vr:
            p('## Model check: real tier runs through chnutils.solve() (MEASURED), each with the same solution and end seed as burn 0')
            p('')
            p('| solver | problem | tier | rep | burn-0 wall (s) | tier wall (s) | predicted (s) | error |')
            p('|---|---|---|---|---|---|---|---|')
            for r in vr:
                cr = [c for c in rows if c['mode'] == 'count' and c['solver'] == r['solver']
                      and c['family'] == r['family'] and c['generator'] == r['generator']
                      and c['seed'] == r['seed'] and c['budget'] == r['budget']]
                if not cr:
                    continue
                feas = _sum(_counts(cr[0]), 'g', None, 'feasible')
                pred = r['base_wall'] + feas * r['burn']
                p('| {0} | {1} | {2} | {3} | {4} | {5} | {6} | {7}% |'.format(
                    r['solver'], r['family'], r['tier'], r['rep'], _fmt(r['base_wall'], 2),
                    _fmt(r['tier_wall'], 2), _fmt(pred, 2),
                    _fmt(100 * (r['tier_wall'] - pred) / pred, 1)))
            p('')
    redundancy(rows, configs, p)


def _m_final(row):
    nu = row['iterations']
    return __import__('math').ceil(2 * pow(1.1, nu))


def redundancy(rows, configs, p):
    p('## Required against done (count mode, totals per run, mean over seeds)')
    p('')
    p('| solver | problem | generator | g() in blocks repeating a point | % of all g() | '
      'estimate() calls answered from cache | get_nondom does_dominate: done / loop bounded | '
      'get_ncn (a) strict: done / early exit | get_ncn (b) predicates: done / early exit | '
      'calc_delta: done / per point | is_lwep strict |')
    p('|---|---|---|---|---|---|---|---|---|---|---|')
    for cfg in configs:
        cr = [r for r in rows if _cfg(r) == cfg and r['mode'] == 'count']
        if not cr:
            continue
        def mean(f):
            return statistics.mean(f(r) for r in cr)
        rep = mean(lambda r: _sum(_counts(r), 'repeat_reps'))
        allg = mean(lambda r: _sum(_counts(r), 'g'))
        est_c = mean(lambda r: _sum(_counts(r), 'estimate', None, 'cached'))
        est_a = mean(lambda r: _sum(_counts(r), 'estimate', None, 'asked'))
        nd_done = mean(lambda r: sum(c for n, c, k, b in r['lists'].get('get_nondom', [])))
        nd_need = mean(lambda r: sum(b for n, c, k, b in r['lists'].get('get_nondom', [])))
        ncn = lambda r: r['lists'].get('get_ncn', [])
        a_done = mean(lambda r: _sum(_counts(r), 'pred', 'get_ncn', 'chnbase.does_strict_dominate'))
        a_need = mean(lambda r: sum(d['need_a'] for d in ncn(r)))
        b_done = mean(lambda r: _sum(_counts(r), 'pred', 'get_ncn', 'chnbase.does_weak_dominate')
                      + _sum(_counts(r), 'pred', 'get_ncn', 'chnbase.does_dominate'))
        b_need = mean(lambda r: sum(d['need_b'] for d in ncn(r)))
        cd_done = mean(lambda r: _sum(_counts(r), 'calc_delta'))
        cd_need = mean(lambda r: sum((d['S'] + d['cands']) * 2 for d in ncn(r)))
        lw = mean(lambda r: _sum(_counts(r), 'pred', 'is_lwep', 'moso.does_strict_dominate'))
        p('| {0} | {1} | {2} | {3} | {4}% | {5} of {6} | {7} / {8} | {9} / {10} | {11} / {12} | {13} / {14} | {15} |'.format(
            *cfg, _fmt(rep, 0), _fmt(100 * rep / allg if allg else 0), _fmt(est_c, 0), _fmt(est_c + est_a, 0),
            _fmt(nd_done, 0), _fmt(nd_need, 0), _fmt(a_done, 0), _fmt(a_need, 0),
            _fmt(b_done, 0), _fmt(b_need, 0), _fmt(cd_done, 0), _fmt(cd_need, 0), _fmt(lw, 0)))
    p('')
    p('### Repeated blocks by the routine that asked (g() calls, mean over seeds)')
    p('')
    p('| solver | problem | generator | ' + ' | '.join(ALGO_REGIONS + ('other',)) + ' |')
    p('|' + '---|' * (3 + len(ALGO_REGIONS) + 1))
    for cfg in configs:
        cr = [r for r in rows if _cfg(r) == cfg and r['mode'] == 'count']
        if not cr:
            continue
        cells = [_fmt(statistics.mean(_sum(_counts(r), 'repeat_reps', reg) for r in cr), 0)
                 for reg in ALGO_REGIONS + ('other',)]
        p('| {0} | {1} | {2} | '.format(*cfg) + ' | '.join(cells) + ' |')
    p('')
    p('### g() calls by the routine that asked (mean over seeds)')
    p('')
    p('| solver | problem | generator | ' + ' | '.join(ALGO_REGIONS + ('other',)) + ' |')
    p('|' + '---|' * (3 + len(ALGO_REGIONS) + 1))
    for cfg in configs:
        cr = [r for r in rows if _cfg(r) == cfg and r['mode'] == 'count']
        if not cr:
            continue
        allg = statistics.mean(_sum(_counts(r), 'g') for r in cr)
        cells = ['{0}%'.format(_fmt(100 * statistics.mean(_sum(_counts(r), 'g', reg) for r in cr) / allg))
                 for reg in ALGO_REGIONS + ('other',)]
        p('| {0} | {1} | {2} | '.format(*cfg) + ' | '.join(cells) + ' |')
    p('')
    p('### ne: neighbours examined per call (radius 1: at most 2d)')
    p('')
    p('| solver | problem | generator | ne calls | mean neighbours examined | improved |')
    p('|---|---|---|---|---|---|')
    for cfg in configs:
        cr = [r for r in rows if _cfg(r) == cfg and r['mode'] == 'count']
        ne = [t for r in cr for t in r['lists'].get('ne', [])]
        if ne:
            p('| {0} | {1} | {2} | {3} | {4} | {5}% |'.format(
                *cfg, _fmt(len(ne) / len(cr), 0), _fmt(statistics.mean(t[1] for t in ne), 2),
                _fmt(100 * sum(t[2] for t in ne) / len(ne))))


def main(argv):
    cmd, path = argv[1], argv[2]
    if cmd == 'run':
        run(path)
    elif cmd == 'validate':
        validate(path)
    elif cmd == 'report':
        report(path)
    else:
        raise SystemExit('usage: bench_biobjective_profile.py run|validate|report RESULTS.jsonl')


if __name__ == '__main__':
    main(sys.argv)
