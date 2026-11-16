"""compare.py REF.json OTHER.json ... : each capture against the reference"""
import json
import math
import struct
import sys


def key(x):
    i = struct.unpack('<q', struct.pack('<d', x))[0]
    return i if i >= 0 else -(i & 0x7fffffffffffffff)


def ulps(a, b):
    if a == b:
        return 0
    if not (math.isfinite(a) and math.isfinite(b)):
        return math.inf
    return abs(key(a) - key(b))


def hexes(xs):
    return [float.fromhex(x) for x in xs]


def floor_gap(v):
    # distance from v to the nearest integer, the margin floor() has
    return min(v - math.floor(v), math.floor(v) + 1 - v)


def main(ref_path, others):
    ref = json.load(open(ref_path))
    print('reference', ref['info']['platform'], ref['info']['python'].split()[0])
    for path in others:
        o = json.load(open(path))
        print('\n==', path, '|', o['info']['platform'], o['info']['machine'], o['info']['python'].split()[0])
        rv, ov = ref['variates'], o['variates']
        assert rv['u'] == ov['u'], 'uniforms differ: not a maths-library difference'
        for name in ('log', 'bsm'):
            d = [ulps(a, b) for a, b in zip(hexes(rv[name]), hexes(ov[name]))]
            nz = [x for x in d if x]
            print('  %-4s %d of %d differ, max %s ulps' % (name, len(nz), len(d), max(nz) if nz else 0))
        worst = (math.inf, None)
        est_dev = 0
        for r, x in zip(ref['runs'], o['runs']):
            assert r['case'] == x['case']
            same = r['solution'] == x['solution'] and r['endseed'] == x['endseed']
            re_, xe = hexes(r['estimates']), hexes(x['estimates'])
            ed = [ulps(a, b) for a, b in zip(re_, xe)]
            nd = sum(1 for d in ed if d)
            est_dev = max([est_dev] + ed)
            rg, xg = r['gaps'], x['gaps']
            line = '  %-42s %s est %d/%d differ max %s' % (r['case'], 'same' if same else 'SOLUTION/ENDSEED DIFFER',
                                                             nd, len(ed), max(ed) if ed else 0)
            if len(re_) != len(xe):
                print(line, '| estimates %d vs %d: trajectories diverge' % (len(re_), len(xe)))
                continue
            if len(rg) != len(xg):
                # the interpreter itself can make a different number of
                # comparisons (3.10 against 3.14), so these do not align
                print(line, '| comparisons %d vs %d: not alignable' % (len(rg), len(xg)))
                continue
            factor, flips, tiebreaks = math.inf, 0, 0
            for a, b in zip(rg, xg):
                if a.startswith('floor'):
                    va, vb = float.fromhex(a.split()[1]), float.fromhex(b.split()[1])
                    if math.floor(va) != math.floor(vb):
                        flips += 1
                    elif va != vb:
                        factor = min(factor, floor_gap(va) / abs(va - vb))
                    continue
                ga, gb = float.fromhex(a), float.fromhex(b)
                if ga == gb or (math.isinf(ga) and math.isinf(gb)):
                    continue
                if ga == 0 or gb == 0:
                    tiebreaks += 1
                    continue
                if (ga > 0) != (gb > 0):
                    flips += 1
                    continue
                factor = min(factor, abs(ga) / abs(ga - gb))
            if factor < worst[0]:
                worst = (factor, r['case'])
            print(line, '| factor %.3g, flips %d, ties broken %d, min gap ref %s here %s'
                  % (factor, flips, tiebreaks, r['min_ulps'], x['min_ulps']))
        print('  largest estimate deviation %s ulps; least safety factor %.3g (%s)' % (est_dev, worst[0], worst[1]))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2:])
