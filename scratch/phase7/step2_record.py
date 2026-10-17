"""Step 2's identity check: the counted runs, with every get_ncn call's
input and output recorded, so that a result-preserving change to get_ncn
can be shown to reproduce the same sequence of answers -- not only the
same final solution and end seed.

    python scratch/phase7/step2_record.py OUT.jsonl
    python scratch/phase7/step2_record.py --compare BEFORE.jsonl AFTER.jsonl
    STEP2_ONLY='M3' python scratch/phase7/step2_record.py OUT.jsonl   # a subset
    python scratch/phase7/step2_record.py --compare-subset BEFORE.jsonl SUBSET.jsonl

The runs: RMINRLE on lattice DTLZ2 at M = 2-6 (ncn_many.py's
configuration, budget 30,000, three seeds), and RPERLE and RMINRLE on
ProbExpensiveBi from (30, 30) and from (0, 20) at burn 0 (the
bi-objective profile's, budget 10,000, both generators, three seeds).
Per run: the solution, the end seed, simcalls, a digest of the whole
sequence of (mcS, ncn) pairs and their number, and the calls get_ncn
made to calc_delta and to the three dominance predicates (counted on
the names get_ncn reads, chnbase.*, and seen non-zero).

Added for step 2c: every get_nondom call the solver bases make (through
chnbase.get_nondom), its input and its answer in iteration order, as a
digest and a count, and the does_dominate calls made inside it (counted
on moso.does_dominate, the name front() reads, as 'front.does_dominate').
Records made before step 2c lack these fields; --compare checks them
only when both records have them.
"""
import contextlib
import hashlib
import io
import json
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import dtlz2_lattice as dl  # noqa: E402

import pymoso.chnbase as chnbase  # noqa: E402
import pymoso.moso as moso  # noqa: E402
from pymoso.layout import get_solv_prnstreams  # noqa: E402
from pymoso.paths import isp_run  # noqa: E402
from pymoso.prng import registry  # noqa: E402
from pymoso.problems import probexpensive as pe_mod  # noqa: E402
from pymoso.solvers.rminrle import RMINRLE  # noqa: E402
from pymoso.solvers.rperle import RPERLE  # noqa: E402

SEEDS = {'mrg32k3a': [(12345,) * 6, (42,) * 6, (271828,) * 6],
         'philox4x32': [(12345, 12345), (42, 42), (271828, 271828)]}
DTLZ_SEEDS = [(1, 12345), (2, 12345), (3, 12345)]


def configs():
    for M in (2, 3, 4, 5, 6):
        for seed in DTLZ_SEEDS:
            yield ('RMINRLE DTLZ2 M{0}'.format(M), dl.make_problem(M, 0.05, 4), RMINRLE,
                   (2,) * 7 + (0,), 30000, 'philox4x32', seed)
    for solver in (RPERLE, RMINRLE):
        for x0 in ((30, 30), (0, 20)):
            for gen in ('mrg32k3a', 'philox4x32'):
                for seed in SEEDS[gen]:
                    yield ('{0} Bi {1}'.format(solver.__name__, x0), pe_mod.ProbExpensiveBi,
                           solver, x0, 10000, gen, seed)


class Recorder:
    def __init__(self):
        self.digest = hashlib.sha256()
        self.calls = 0
        self.inside = 0
        self.counts = {}
        self.nondom_digest = hashlib.sha256()
        self.nondom_calls = 0
        self.in_nondom = 0

    def bump(self, key):
        if self.inside:
            self.counts[key] = self.counts.get(key, 0) + 1

    def bump_front(self):
        if self.in_nondom:
            self.counts['front.does_dominate'] = self.counts.get('front.does_dominate', 0) + 1


@contextlib.contextmanager
def recording():
    rec = Recorder()
    undo = []

    def patch(owner, name, value):
        undo.append((owner, name, getattr(owner, name)))
        setattr(owner, name, value)

    real_ncn = chnbase.RLESolver.get_ncn

    def get_ncn(self, mcS):
        before = sorted(mcS)
        rec.inside += 1
        try:
            ncn = real_ncn(self, mcS)
        finally:
            rec.inside -= 1
        rec.calls += 1
        rec.digest.update(repr((before, sorted(ncn))).encode())
        return ncn
    patch(chnbase.RLESolver, 'get_ncn', get_ncn)

    real_cd = chnbase.RLESolver.calc_delta

    def calc_delta(self, se):
        rec.bump('calc_delta')
        return real_cd(self, se)
    patch(chnbase.RLESolver, 'calc_delta', calc_delta)

    for name in ('does_dominate', 'does_weak_dominate', 'does_strict_dominate'):
        real = getattr(chnbase, name)

        def counted(*a, _real=real, _name=name):
            rec.bump(_name)
            return _real(*a)
        patch(chnbase, name, counted)

    real_nondom = chnbase.get_nondom

    def get_nondom(edict):
        before = sorted(edict.items())
        rec.in_nondom += 1
        try:
            nondom = real_nondom(edict)
        finally:
            rec.in_nondom -= 1
        rec.nondom_calls += 1
        rec.nondom_digest.update(repr((before, list(nondom))).encode())
        return nondom
    patch(chnbase, 'get_nondom', get_nondom)

    real_dd = moso.does_dominate

    def front_dd(*a):
        rec.bump_front()
        return real_dd(*a)
    patch(moso, 'does_dominate', front_dd)
    try:
        yield rec
    finally:
        for owner, name, value in reversed(undo):
            setattr(owner, name, value)


def run(name, cls, solver, x0, budget, gen, seed):
    orcstream, solvstream = get_solv_prnstreams(seed, registry.get_generator(gen))
    orc = cls(orcstream)
    orc.set_crnflag(False)
    with recording() as rec, contextlib.redirect_stdout(io.StringIO()), orc.set_simpar(1):
        res = isp_run(solver, budget, orc, solvprn=solvstream, x0=x0)
    last = max(res['itersoln'])
    if not rec.calls or not rec.counts.get('calc_delta') or not rec.counts.get('does_weak_dominate'):
        raise AssertionError('{0}: a counter was never reached'.format(name))
    if not rec.nondom_calls or not rec.counts.get('front.does_dominate'):
        raise AssertionError('{0}: a get_nondom counter was never reached'.format(name))
    return dict(config=name, generator=gen, seed=list(seed), soln=sorted(res['itersoln'][last]),
                endseed=list(res['endseed']), simcalls=res['simcalls'][last],
                ncn_calls=rec.calls, ncn_digest=rec.digest.hexdigest(),
                nondom_calls=rec.nondom_calls, nondom_digest=rec.nondom_digest.hexdigest(),
                counts=rec.counts)


def record(out):
    only = os.environ.get('STEP2_ONLY', '')
    with open(out, 'w') as f:
        for cfg in configs():
            if only not in cfg[0]:
                continue
            row = run(*cfg)
            f.write(json.dumps(row) + '\n')
            print(row['config'], row['generator'], row['seed'][0], row['ncn_calls'],
                  row['counts'], flush=True)


def compare(before, after, subset=False):
    a = [json.loads(line) for line in open(before)]
    b = [json.loads(line) for line in open(after)]
    if subset:
        keys = {(y['config'], y['generator'], tuple(y['seed'])) for y in b}
        a = [x for x in a if (x['config'], x['generator'], tuple(x['seed'])) in keys]
    assert len(a) == len(b) and len(a) > 0, (len(a), len(b))
    same = 0
    for x, y in zip(a, b):
        key = (x['config'], x['generator'], x['seed'])
        assert key == (y['config'], y['generator'], y['seed']), key
        fields = ['soln', 'endseed', 'simcalls', 'ncn_calls', 'ncn_digest']
        fields += [k for k in ('nondom_calls', 'nondom_digest') if k in x and k in y]
        ident = all(x[k] == y[k] for k in fields)
        same += ident
        print(*key, 'IDENTICAL' if ident else 'DIFFERS',
              {k: (x['counts'].get(k), y['counts'].get(k)) for k in sorted(set(x['counts']) | set(y['counts']))})
    nondom = all('nondom_digest' in r for r in a + b)
    print('{0} of {1} runs identical (solution, end seed, simcalls, every get_ncn answer{2})'.format(
        same, len(a), ', every get_nondom answer' if nondom else ''))
    return same == len(a)


if __name__ == '__main__':
    if sys.argv[1] in ('--compare', '--compare-subset'):
        sys.exit(0 if compare(sys.argv[2], sys.argv[3], sys.argv[1] == '--compare-subset') else 1)
    record(sys.argv[1])
