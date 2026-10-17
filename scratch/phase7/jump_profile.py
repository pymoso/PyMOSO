"""Phase 7 step 3, profile before optimizing: where an MRG jump's time goes.

    python scratch/phase7/jump_profile.py runs   OUT.jsonl   # part A
    python scratch/phase7/jump_profile.py parts  OUT.json    # part B

Part A, real runs, both MRG generators: every call to the generator's
jump_seed_n (the one function stream_at and Stream.advance both reach),
classified by the path it takes -- a matrix cached at import (the
replication strides, ITER_STRIDE), a power of two, or the general
square-and-multiply -- with each general exponent's bit length, set
bits and trailing zeros, and the time spent in each path against the
run's wall time. Timing wrappers inflate what they wrap a little, so
part A's shares are upper bounds; part B is the clean measurement.

Part B, a microbenchmark of the general path's pieces, both generators,
at exponents shaped like part A's: the whole jump_seed_n; one 3x3
matrix product mod m (mrg_common.mat333sqmult_mod), with full-size
entries; the same product written out as straight-line arithmetic (the
floor for this arithmetic in Python); the closing matrix-vector product
and reduction; and constructing the Stream. The general jump is
2 x (bit length + set bits) products plus that tail, so the products'
share follows from the count and the unit cost; that model is checked
against the measured whole.
"""
import contextlib
import io
import json
import os
import statistics
import sys
import time
import timeit

from pymoso.layout import get_solv_prnstreams
from pymoso.paths import isp_run
from pymoso.prng import mrg_common, mrg31k3p, mrg32k3a
from pymoso.problems.bsprob import BSProb
from pymoso.problems.probsimpleso import ProbSimpleSO
from pymoso.problems.probtpa import ProbTPA
from pymoso.problems.probtpc import ProbTPC
from pymoso.solvers.rminrle import RMINRLE
from pymoso.solvers.rperle import RPERLE
from pymoso.solvers.rspline import RSPLINE

GENERATORS = {'mrg32k3a': mrg32k3a, 'mrg31k3p': mrg31k3p}
SEED = (12345,) * 6

RUNS = [
    ('RSPLINE ProbSimpleSO', ProbSimpleSO, RSPLINE, (97,), 1000),
    ('RPERLE ProbTPA', ProbTPA, RPERLE, (30, 30), 2000),
    ('RMINRLE ProbTPC', ProbTPC, RMINRLE, (3, 3, 3), 2000),
    ('RSPLINE BSProb', BSProb, RSPLINE, (2,) * 9, 300),
]


def classify(mod, n):
    if n in (mod.REPL_RESERVE_STRIDE, mod.REPL_STRIDE, mod.ITER_STRIDE):
        return 'cached'
    if n > 0 and n & (n - 1) == 0:
        return 'pow2'
    return 'general'


def tz(n):
    return (n & -n).bit_length() - 1 if n else 0


def one_run(gen, name, cls, solver, x0, budget):
    mod = GENERATORS[gen]
    real = mod.jump_seed_n
    rec = {'cached': [0, 0.0], 'pow2': [0, 0.0], 'general': [0, 0.0]}
    shapes = []

    def counted(seed, n):
        t0 = time.perf_counter()
        out = real(seed, n)
        el = time.perf_counter() - t0
        kind = classify(mod, n)
        rec[kind][0] += 1
        rec[kind][1] += el
        if kind == 'general':
            shapes.append((n.bit_length(), bin(n).count('1'), tz(n)))
        return out
    mod.jump_seed_n = counted
    try:
        orcstream, solvstream = get_solv_prnstreams(SEED, mod)
        orc = cls(orcstream)
        orc.set_crnflag(False)
        with contextlib.redirect_stdout(io.StringIO()), orc.set_simpar(1):
            t0 = time.perf_counter()
            res = isp_run(solver, budget, orc, solvprn=solvstream, x0=x0)
            wall = time.perf_counter() - t0
    finally:
        mod.jump_seed_n = real
    if not shapes:
        raise AssertionError('{0} {1}: the wrapper was never reached'.format(gen, name))
    last = max(res['simcalls'])
    bl = [s[0] for s in shapes]
    pc = [s[1] for s in shapes]
    tzs = [s[2] for s in shapes]
    return dict(generator=gen, run=name, budget=budget, wall=wall, simcalls=res['simcalls'][last],
                calls={k: v[0] for k, v in rec.items()}, secs={k: v[1] for k, v in rec.items()},
                general_bitlen=[min(bl), statistics.median(bl), max(bl)],
                general_popcount=[min(pc), statistics.median(pc), max(pc)],
                general_trailing_zeros=[min(tzs), statistics.median(tzs), max(tzs)],
                loadavg=os.getloadavg())


def runs(out):
    with open(out, 'w') as f:
        for gen in GENERATORS:
            for cfg in RUNS:
                row = one_run(gen, *cfg)
                f.write(json.dumps(row) + '\n')
                share = {k: round(100 * v / row['wall'], 1) for k, v in row['secs'].items()}
                print(gen, row['run'], 'wall {0:.2f}s'.format(row['wall']), 'calls', row['calls'],
                      'share %', share, 'general bitlen', row['general_bitlen'],
                      'popcount', row['general_popcount'], 'tz', row['general_trailing_zeros'], flush=True)


def best(stmt, number, repeat=7, glb=None):
    return min(timeit.repeat(stmt, number=number, repeat=repeat, globals=glb)) / number


def unrolled(a, b, m):
    a0, a1, a2 = a
    b0, b1, b2 = b
    return [
        [(a0[0] * b0[0] + a0[1] * b1[0] + a0[2] * b2[0]) % m,
         (a0[0] * b0[1] + a0[1] * b1[1] + a0[2] * b2[1]) % m,
         (a0[0] * b0[2] + a0[1] * b1[2] + a0[2] * b2[2]) % m],
        [(a1[0] * b0[0] + a1[1] * b1[0] + a1[2] * b2[0]) % m,
         (a1[0] * b0[1] + a1[1] * b1[1] + a1[2] * b2[1]) % m,
         (a1[0] * b0[2] + a1[1] * b1[2] + a1[2] * b2[2]) % m],
        [(a2[0] * b0[0] + a2[1] * b1[0] + a2[2] * b2[0]) % m,
         (a2[0] * b0[1] + a2[1] * b1[1] + a2[2] * b2[1]) % m,
         (a2[0] * b0[2] + a2[1] * b1[2] + a2[2] * b2[2]) % m],
    ]


def parts(out):
    result = {'python': sys.version.split()[0], 'loadavg_before': os.getloadavg(), 'generators': {}}
    for gen, mod in GENERATORS.items():
        m1 = mod.mrgm1i if gen == 'mrg32k3a' else mod.mrg31m1
        cls = mod.MRG32k3a if gen == 'mrg32k3a' else mod.MRG31k3p
        full = mrg_common.mat_pow_mod(mod._m1_step, 3 ** 40 + 12345, m1)   # full-size entries
        seed = mod.jump_seed_n(SEED, 987654321)
        s1 = list(seed[0:3])
        r = {}
        r['product_us'] = 1e6 * best(lambda: mrg_common.mat333sqmult_mod(full, full, m1), 20000)
        r['product_unrolled_us'] = 1e6 * best(lambda: unrolled(full, full, m1), 20000)
        assert unrolled(full, full, m1) == mrg_common.mat333sqmult_mod(full, full, m1)
        r['matvec_mod_us'] = 1e6 * best(lambda: mrg_common.mat311mod(mrg_common.mat333mult(full, s1), m1), 20000)
        r['construct_stream_us'] = 1e6 * best(lambda: cls(seed), 20000)
        r['cached_jump_us'] = 1e6 * best(lambda: mod.jump_seed_n(seed, mod.REPL_RESERVE_STRIDE), 20000)
        shapes = {}
        # Exponent shapes from part A: a dim-1 point's offset, a dim-2
        # point's, a 75-bit code's, and stream_at(root, k, 0) at k = 20.
        for label, n in [('offset, code 3 bits', 0b101 << 52),
                         ('offset, code 44 bits', ((1 << 43) + 0x5a5a5a5a5a5) << 52),
                         ('offset, code 75 bits', ((1 << 74) + (1 << 60) + 0x123456789abcdef) << 52),
                         ('stream 20, offset 0', 20 * mod.ITER_STRIDE)]:
            total = 1e6 * best(lambda: mod.jump_seed_n(seed, n), 300)
            nprod = 2 * (n.bit_length() + bin(n).count('1'))
            model = nprod * r['product_us'] + 2 * r['matvec_mod_us']
            shapes[label] = dict(bitlen=n.bit_length(), popcount=bin(n).count('1'), trailing_zeros=tz(n),
                                 jump_us=total, products=nprod,
                                 products_share=nprod * r['product_us'] / total,
                                 squarings_share=2 * n.bit_length() * r['product_us'] / total,
                                 multiplies_share=2 * bin(n).count('1') * r['product_us'] / total,
                                 model_over_measured=model / total)
        r['shapes'] = shapes
        result['generators'][gen] = r
        print(gen, json.dumps(r, indent=1), flush=True)
    result['loadavg_after'] = os.getloadavg()
    with open(out, 'w') as f:
        json.dump(result, f, indent=1)


if __name__ == '__main__':
    {'runs': runs, 'parts': parts}[sys.argv[1]](sys.argv[2])
