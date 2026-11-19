"""
The built-in testers' reference sets are decision points, and they are
the sets the dissertation says they are.

Definitions are the dissertation's (ch. 3, defn:LEP, defn:LES, defn:LWES).
N_1(x) is the lattice points within Euclidean distance 1 of x
(moso.get_nbors(x, 1)), intersected with the feasible box. g(a)
dominates g(b) if g(a) <= g(b) componentwise and g(a) != g(b); it
strictly dominates if g(a) < g(b) in every objective; it weakly
dominates if g(a) <= g(b) componentwise. A set L is an N_1-local
efficient set (LES) if (a) no member is dominated by a feasible
neighbour, (b) no member dominates another, and (c) every feasible point
of the deleted neighbourhood N_1(L) - L is dominated by a member; an
N_1-local weakly efficient set (LWES) is the same with strict dominance
in (a) and (b) and weak dominance in (c).

What each tester stores, and how sure we are:

- T_A: the global efficient set, checked here in exact integer
  arithmetic (100 * true_g is an integer polynomial: squared distances to
  (20, 10) and (0, 20), plus constants). Exhaustive and exact, so this
  is a proof, not an agreement with an enumeration.
- T_B: the N_1-LES in each of the rows x2 = 20 (x1 0-25, the global
  efficient set) and x2 = 70 (x1 0-50), checked in floats. Proved by
  hand: for 0 <= g1 <= f, g2 = f*h is strictly increasing in f (g1/f <= 1
  decreases and alpha increases, so (g1/f)^alpha decreases and h
  increases); f has its minima 1 at x2 = 20 and 2 at x2 = 70; along each
  row g2 decreases strictly in x1 until g1 = f, where g2 = 0 and every
  larger x1 is dominated. Every tie the float check meets is forced (equal
  x1, so g1 is computed identically; or g2 exactly 0). That T_B has no
  other N_1-LES is not shown.
- T_C: the dissertation's 516 N_1-LWESs (Online Appendix E), as its
  metric for T_C uses (the local weakly coverage error), converted from
  the 2018 work's own point sets (docs/reference/tpc-reference-sets.md).
  Checked in floats with a tolerance of 1e-12: some of these sets rest on
  ties in objective 2 between coordinate permutations, which sum the same
  three terms in a different order -- equal on this machine, but not
  guaranteed equal under another C library. A wrong point moves an image
  by at least 0.02. The 516 are not every LWES as point sets; that their
  66 image sets are every LWES's image set is not shown and cannot be
  from here.

The metric must also measure exactly zero at full coverage: both sides of
the comparison go through the same true_g on the same machine.
"""
import itertools

import pytest

from pymoso.moso import get_nbors
from pymoso.testers import tpatester, tpbtester, tpctester

TOL_C = 1e-12

BOX_A = list(itertools.product(range(51), repeat=2))
BOX_B = list(itertools.product(range(101), repeat=2))
BOX_C = list(itertools.product(range(-10, 11), repeat=3))


def g100_a(x):
    """100 * tpatester.true_g(x), exactly."""
    return ((x[0] - 20) ** 2 + (x[1] - 10) ** 2 + 1000,
            x[0] ** 2 + (x[1] - 20) ** 2 + 800)


def dominates(a, b, tol=0.0):
    return all(p <= q + tol for p, q in zip(a, b)) and any(p < q - tol for p, q in zip(a, b))


def strictly_dominates(a, b, tol=0.0):
    return all(p < q - tol for p, q in zip(a, b))


def weakly_dominates(a, b, tol=0.0):
    return all(p <= q + tol for p, q in zip(a, b))


def les_failures(L, g, box):
    """What stops L being an N_1-LES under g: a list, empty if it is one."""
    fails = []
    for x in L:
        for n in get_nbors(x, 1) & box:
            if n != x and dominates(g(n), g(x)):
                fails.append(('a', x, n))
    for p in L:
        for q in L:
            if dominates(g(p), g(q)):
                fails.append(('b', p, q))
    nbhd = set().union(*(get_nbors(x, 1) for x in L)) & box
    for n in nbhd - set(L):
        if not any(dominates(g(x), g(n)) for x in L):
            fails.append(('c', n))
    return fails


def lwes_failures(L, g, box, tol):
    """What stops L being an N_1-LWES under g (values within tol equal)."""
    fails = []
    for x in L:
        for n in get_nbors(x, 1) & box:
            if n != x and strictly_dominates(g(n), g(x), tol):
                fails.append(('a', x, n))
    for p in L:
        for q in L:
            if strictly_dominates(g(p), g(q), tol):
                fails.append(('b', p, q))
    nbhd = set().union(*(get_nbors(x, 1) for x in L)) & box
    for n in nbhd - set(L):
        if not any(weakly_dominates(g(x), g(n), tol) for x in L):
            fails.append(('c', n))
    return fails


def global_efficient(box, g):
    """Non-dominated points, by a sweep in g1 order (two objectives)."""
    pts = sorted(box, key=g)
    out, best2 = [], None
    for x in pts:
        v = g(x)
        if best2 is None or v[1] < best2:
            out.append(x)
            best2 = v[1]
    # a sweep keeps one of several points with equal images; keep them all
    imgs = {g(x) for x in out}
    return {x for x in box if g(x) in imgs}


def cached(f):
    memo = {}
    return lambda x: memo[x] if x in memo else memo.setdefault(x, f(x))


# ---- T_A


def test_ta_reference_is_the_global_efficient_set_in_exact_arithmetic():
    ges = global_efficient(BOX_A, g100_a)
    stored = set(tpatester.TPATester().soln)
    assert stored == ges
    assert len(ges) == 49
    assert les_failures(stored, g100_a, set(BOX_A)) == []


def test_ta_exact_objectives_are_true_g():
    # the integer form above is the tester's true_g, to rounding
    for x in BOX_A:
        assert all(abs(v / 100 - t) <= 1e-12 for v, t in zip(g100_a(x), tpatester.true_g(x)))


# ---- T_B


def test_tb_reference_sets_are_local_efficient_sets():
    g = cached(tpbtester.true_g)
    box = set(BOX_B)
    stored = tpbtester.TPBTester().soln
    assert sorted(len(L) for L in stored) == [26, 51]
    for L in stored:
        assert les_failures(set(L), g, box) == []
    assert set(min(stored, key=len)) == global_efficient(BOX_B, g)


# ---- T_C


def test_tc_reference_sets_are_local_weakly_efficient_sets():
    g = cached(tpctester.true_g)
    box = set(BOX_C)
    stored = tpctester.TPCTester().soln
    # the dissertation's Online Appendix E: 516 unique sets holding 73 points
    assert len(stored) == 516
    assert len({frozenset(L) for L in stored}) == 516
    assert len(set().union(*stored)) == 73
    assert sum(len(L) for L in stored) == 4273
    # as images they are 66 distinct sets (mirror pairs share an image)
    assert len({frozenset(tuple(round(v, 9) for v in g(x)) for x in L) for L in stored}) == 66
    for L in stored:
        assert set(L) <= box
        assert lwes_failures(set(L), g, box, TOL_C) == []


# ---- full coverage measures zero, and the reference is computed once


def ta_points():
    return global_efficient(BOX_A, g100_a)


def tb_points():
    return [{(x1, 70) for x1 in range(51)}, {(x1, 20) for x1 in range(26)}]


def tc_points():
    # one point set for each distinct set of images: the metric sees only
    # images. Sound only because test_tc_reference_sets_are_local_weakly_
    # efficient_sets asserts there are exactly 66 such sets; keep that
    # assertion, it is what catches true_g moving under this shortcut.
    by_images = {}
    for L in tpctester.TPCTester().soln:
        by_images.setdefault(frozenset(tuple(round(v, 9) for v in tpctester.true_g(x)) for x in L), L)
    return list(by_images.values())


@pytest.mark.parametrize("tester, sets", [
    (tpatester.TPATester, lambda: [ta_points()]),
    (tpbtester.TPBTester, tb_points),
    (tpctester.TPCTester, tc_points),
], ids=['TPA', 'TPB', 'TPC'])
def test_full_coverage_measures_exactly_zero(tester, sets):
    t = tester()
    for L in sets():
        assert t.metric(set(L)) == 0.0


@pytest.mark.parametrize("tester", [tpatester.TPATester, tpbtester.TPBTester, tpctester.TPCTester],
                         ids=['TPA', 'TPB', 'TPC'])
def test_metric_computes_true_g_only_for_the_solution_it_is_given(tester):
    t = tester()
    calls = []
    true_g = t.true_g

    def counting(x):
        calls.append(x)
        return true_g(x)

    t.true_g = counting
    eles = set(itertools.islice(iter(t.soln if isinstance(t.soln, set) else t.soln[0]), 3))
    t.metric(eles)
    assert sorted(calls) == sorted(eles)  # proves the substitute was reached, and nothing else was computed


# ---- the checks above can fail


def test_the_checks_reject_corrupted_sets():
    ges = ta_points()
    bad = (ges - {(10, 15)}) | {(10, 17)}  # a point off the band, dominated by (10, 16)
    assert les_failures(bad, g100_a, set(BOX_A))
    assert global_efficient(BOX_A, g100_a) != bad

    g = cached(tpbtester.true_g)
    row = {(x1, 20) for x1 in range(26)}
    assert les_failures((row - {(10, 20)}) | {(10, 21)}, g, set(BOX_B))
    assert les_failures(row - {(25, 20)}, g, set(BOX_B))  # incomplete: (25, 20) is undominated

    gc = cached(tpctester.true_g)
    L = max(tpctester.TPCTester().soln, key=len)
    x = min(L)
    moved = (L - {x}) | {min(get_nbors(x, 1) & set(BOX_C) - L)}
    assert lwes_failures(moved, gc, set(BOX_C), TOL_C)
