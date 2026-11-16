"""How far the platform's maths library moves PyMOSO's results, and how
far its solvers' decisions sit from flipping. Measurement only, on the
throwaway branch measure-platform; never merged.

    python measure/capture.py OUT.json

Writes, for this platform:
- bsm (the inverse-normal behind every normalvariate) on 200,000
  MRG32k3a uniforms, and log of each uniform, as hex. The uniforms are
  integer arithmetic and identical everywhere, so any difference is the
  C library's log/pow.
- For each run below, every mean and standard error hit() returned, as
  hex in call order, with the run's solution and end seed; and, for
  every comparison the solver made involving an estimate, in order, the
  signed difference of the two sides (the margin shadow: each estimate
  is wrapped in T, a float whose comparisons are logged; SPLI's floor
  is wrapped too, and its argument recorded), with the smallest gap in
  ulps.

Runs: the RA golden solve() cases and two golden testsolve() cases at
budget 1,000; 80 solve() runs on ProbTPA (four solver setups, seeds
100-119); R-PE through testsolve on T_A and T_C, with and without CRN,
at the beta sweep's budget of 4 x 10^5, four paths each.

Decided before any result was seen (2026-10-27): where a run makes the
same comparisons as on Linux, the safety factor is the least, over its
comparisons, of Linux's gap divided by how far this platform moved it.
The Python-version split gave about 10^8. At 10^6 or more the platform
split is safe in the same sense; between 10^3 and 10^6, safe but
thinner, and said so; below 10^3, thin, whatever the goldens do. Any
decision that differs from Linux's is the finding, whatever the factor.
"""
import contextlib
import io
import json
import math
import platform
import struct
import sys
import time
import traceback

from pymoso.oracle import Oracle


def ulps(a, b):
    if a == b:
        return 0
    if any(math.isinf(x) or math.isnan(x) for x in (a, b)):
        return None

    def key(x):
        i = struct.unpack('<q', struct.pack('<d', x))[0]
        return i if i >= 0 else -(i & 0x7fffffffffffffff)
    return abs(key(a) - key(b))


class Log:
    def __init__(self):
        self.reset()

    def reset(self):
        self.n = 0
        self.ties_distinct = 0
        self.min = None
        self.where = None
        self.floors = [0, None]
        self.estimates = []
        self.gaps = []


LOG = Log()


def _site():
    fr = [f for f in traceback.extract_stack()[:-3] if 'pymoso' in f.filename and 'measure' not in f.filename]
    return fr[-1].filename.replace('\\', '/').split('pymoso/')[-1] + ':' + str(fr[-1].lineno) if fr else '?'


def record(a, b):
    fa, fb = float(a), float(b)
    LOG.n += 1
    LOG.gaps.append((fa - fb).hex())
    u = ulps(fa, fb)
    if u is None:
        return
    if u == 0:
        if getattr(a, 'src', None) != getattr(b, 'src', None) or not isinstance(b, T):
            LOG.ties_distinct += 1
        return
    if LOG.min is None or u < LOG.min:
        LOG.min = u
        LOG.where = (fa, fb, _site())


def src(*xs):
    s = set()
    for x in xs:
        if isinstance(x, T):
            s |= x.src
    return frozenset(s)


class T(float):
    __slots__ = ('src',)

    def __new__(cls, v, s=frozenset()):
        o = float.__new__(cls, v)
        o.src = s
        return o


for _name in ['add', 'sub', 'mul', 'truediv', 'pow', 'floordiv', 'mod']:
    for _pre in ('', 'r'):
        _m = '__%s%s__' % (_pre, _name)

        def _op(self, other, f=getattr(float, _m)):
            r = f(float(self), float(other) if isinstance(other, float) else other)
            return T(r, src(self, other)) if isinstance(r, float) else r
        setattr(T, _m, _op)
T.__neg__ = lambda self: T(-float(self), self.src)
T.__abs__ = lambda self: T(abs(float(self)), self.src)
T.__pos__ = lambda self: self
for _m in ['__lt__', '__le__', '__gt__', '__ge__', '__eq__', '__ne__']:
    def _cmp(self, other, f=getattr(float, _m)):
        if isinstance(other, (int, float)):
            record(self, other)
        return f(float(self), float(other) if isinstance(other, float) else other)
    setattr(T, _m, _cmp)
T.__hash__ = lambda self: float.__hash__(float(self))
T.__reduce__ = lambda self: (float, (float(self),))

COUNTER = [0]


def wrap(res):
    isfeas, obj, se = res[0], res[1], res[2]
    if not isfeas:
        return res

    def w(seq):
        out = []
        for v in seq:
            COUNTER[0] += 1
            LOG.estimates.append(float(v).hex())
            out.append(T(v, frozenset([COUNTER[0]])))
        return tuple(out) if isinstance(seq, tuple) else out
    return (isfeas, w(obj), w(se)) + tuple(res[3:])


import pymoso.chnbase as _cb  # noqa: E402
import pymoso.moso as _moso  # noqa: E402

_sqrt, _floor = math.sqrt, math.floor


def tsqrt(x):
    r = _sqrt(x)
    return T(r, x.src) if isinstance(x, T) else r


def tfloor(x):
    if isinstance(x, T):
        v = float(x)
        lo = _floor(v)
        u = min(ulps(v, float(lo)), ulps(v, float(lo + 1)))
        LOG.floors[0] += 1
        LOG.gaps.append('floor ' + v.hex())
        if LOG.floors[1] is None or u < LOG.floors[1]:
            LOG.floors[1] = u
    return _floor(x)


_moso.sqrt = tsqrt
_cb.floor = tfloor
_hit, _many = Oracle.hit, Oracle.hit_many
Oracle.hit = lambda self, *a, **k: wrap(_hit(self, *a, **k))
Oracle.hit_many = lambda self, reqs, *a, **k: [wrap(r) for r in _many(self, reqs, *a, **k)]


def variates():
    from pymoso.prng import mrg32k3a
    rng = mrg32k3a.MRG32k3a((12345,) * 6)
    us = [rng.random() for _ in range(200000)]
    return dict(u=[u.hex() for u in us], log=[math.log(u).hex() for u in us],
                bsm=[mrg32k3a.bsm(u).hex() for u in us])


def main(path):
    from pymoso.chnutils import solve, testsolve
    from pymoso.problems.probtpa import ProbTPA
    from pymoso.solvers.rminrle import RMINRLE
    from pymoso.solvers.rpe import RPE
    from pymoso.solvers.rperle import RPERLE
    from pymoso.testers.tpatester import TPATester
    from pymoso.testers.tpctester import TPCTester
    sys.path.insert(0, 'tests')
    from test_solution_sensitivity import SOLVE_CASES

    def last(res):
        return {q: sorted(res[q]['itersoln'][max(res[q]['itersoln'])]) for q in res}

    rows = []

    def run(label, f, solution):
        LOG.reset()
        t = time.time()
        with contextlib.redirect_stdout(io.StringIO()):
            out = f()
        rows.append(dict(case=label, comparisons=LOG.n, distinct_ties=LOG.ties_distinct, min_ulps=LOG.min,
                         where=LOG.where, floors=LOG.floors, solution=str(solution(out)),
                         endseed=list(out[1]),
                         estimates=LOG.estimates, gaps=LOG.gaps, secs=round(time.time() - t, 1)))
        print(label, LOG.min, rows[-1]['secs'], 's', flush=True)

    for name, (p, s, x0, kw, _) in SOLVE_CASES.items():
        if 'example' in name or 'simpar' in name:
            continue
        a = dict(budget=1000, seed=(12345,) * 6, simpar=1, crn=False)
        a.update(kw)
        run(name, lambda: solve(p, s, x0, **a), lambda o: sorted(o[0]))
    for label, ranx0, x0 in [('testsolve_tpa', True, (0,)), ('testsolve_library', False, (40, 40))]:
        run(label, lambda: testsolve(TPATester, RPERLE, x0, budget=1000, seed=(12345,) * 6, isp=4, proc=1,
                                     crn=False, ranx0=ranx0), lambda o: last(o[0]))
    for k in range(20):
        for s, crn in [(RPERLE, False), (RMINRLE, False), (RPE, False), (RPERLE, True)]:
            a = dict(budget=1000, seed=(100 + k,) * 6, simpar=1, crn=crn)
            run('%s seed %d%s' % (s.__name__, 100 + k, ' crn' if crn else ''),
                lambda: solve(ProbTPA, s, (40, 40), **a), lambda o: sorted(o[0]))
    for tester in (TPATester, TPCTester):
        for crn in (False, True):
            run('RPE %s crn=%s budget=400000 isp=4' % (tester.__name__, crn),
                lambda: testsolve(tester, RPE, None, budget=400000, isp=4, proc=1, ranx0=True,
                                  seed=(12345,) * 6, crn=crn), lambda o: last(o[0]))
    info = dict(platform=platform.platform(), machine=platform.machine(), python=sys.version,
                libc=platform.libc_ver(), mac=platform.mac_ver()[0])
    with open(path, 'w') as f:
        json.dump(dict(info=info, variates=variates(), runs=rows), f)


if __name__ == '__main__':
    main(sys.argv[1])
