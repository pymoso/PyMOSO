"""
get_nondom's merge compares each point of the bottom half's front only
with the top half's front, and gives the answer it always gave
(docs/phase7-plan.md, step 2).

`reference_front` below is the implementation before Phase 7, kept
verbatim as the reference. Do not "tidy" it: it is what the current
`front` is held to, answer for answer and in the same order.

The change rests on one property: nothing front() returns is dominated
by anything earlier in its own output. That is checked here directly,
at every level of the recursion, and not only through the answers.

The work is counted, never timed.
"""
import math
import random

import pytest

from pymoso import moso
from pymoso.moso import argsort, does_dominate


def reference_front(points, objs):
    cardP = len(points)
    if cardP == 1:
        return points, objs
    elif cardP > 1:
        nondom = set()
        halfind = int(cardP/2)
        Tpts, Tobjs = reference_front(points[0:halfind], objs[0:halfind])
        Bpts, Bobjs = reference_front(points[halfind:cardP], objs[halfind:cardP])
        brange = range(len(Bpts))
        for i in brange:
            pt = Bpts[i]
            gvals = Bobjs[i]
            delz = [0]*len(gvals)
            pt_nondom = True
            j = 0
            while j < len(Tpts) and pt_nondom:
                if does_dominate(Tobjs[j], gvals, delz, delz):
                    pt_nondom = False
                j += 1
            if pt_nondom:
                Tpts.append(pt)
                Tobjs.append(gvals)
        return Tpts, Tobjs


def _sets():
    """Objective vectors as get_nondom sees them: small integers, so
    ties and equal vectors are common; floats; and some with a nan."""
    rng = random.Random(20261017)
    out = []
    for _ in range(400):
        d = rng.randint(1, 4)
        n = rng.randint(1, 40)
        kind = rng.choice(('int', 'float', 'nan'))
        objs = []
        for _ in range(n):
            if kind == 'int':
                v = tuple(rng.randint(0, 4) for _ in range(d))
            else:
                v = tuple(rng.random() for _ in range(d))
                if kind == 'nan' and rng.random() < 0.2:
                    v = tuple(math.nan if rng.random() < 0.5 else c for c in v)
            objs.append(v)
        out.append([((i,), v) for i, v in enumerate(objs)])
    return out


SETS = _sets()


def _sorted(pairs):
    """The order get_nondom hands front()."""
    vals = [v for _, v in pairs]
    return [pairs[i] for i in argsort(vals)]


def _split(pairs):
    return [p for p, _ in pairs], [v for _, v in pairs]


@pytest.mark.parametrize("order", ["as get_nondom sorts them", "unsorted"])
def test_the_answer_and_its_order_are_unchanged(order):
    for pairs in SETS:
        if order == "as get_nondom sorts them":
            pairs = _sorted(pairs)
        points, objs = _split(pairs)
        assert moso.front(list(points), list(objs)) == reference_front(list(points), list(objs))


def test_get_nondom_is_unchanged():
    for pairs in SETS:
        edict = dict(pairs)
        points, objs = _split(_sorted(pairs))
        assert list(moso.get_nondom(edict)) == list(set(reference_front(points, objs)[0]))


@pytest.mark.parametrize("order", ["as get_nondom sorts them", "unsorted"])
def test_nothing_front_returns_is_dominated_by_an_earlier_point_of_it(order, monkeypatch):
    """The property the bound rests on, checked on every front() output,
    the recursive calls' included (front calls itself through the module
    name, which this wraps)."""
    real = moso.front
    outputs = []

    def checked(points, objs):
        result = real(points, objs)
        outputs.append(result)
        return result
    monkeypatch.setattr(moso, 'front', checked)
    for pairs in SETS:
        if order == "as get_nondom sorts them":
            pairs = _sorted(pairs)
        points, objs = _split(pairs)
        moso.front(points, objs)
    assert len(outputs) > len(SETS)        # the recursion was reached
    for _, objs in outputs:
        delz = [0] * len(objs[0])
        for k, later in enumerate(objs):
            for earlier in objs[:k]:
                assert not does_dominate(earlier, later, delz, delz), (earlier, later)


def _count(monkeypatch, objs):
    calls = []
    real = moso.does_dominate
    monkeypatch.setattr(moso, 'does_dominate', lambda *a: (calls.append(1), real(*a))[1])
    points = [(i,) for i in range(len(objs))]
    moso.front(points, list(objs))
    return len(calls)


def test_a_front_with_nothing_dominated_compares_each_pair_once(monkeypatch):
    """Sixteen mutually non-dominated points: each pair is compared
    exactly once, n(n-1)/2 = 120."""
    objs = [(i, 15 - i) for i in range(16)]
    assert _count(monkeypatch, objs) == 16 * 15 // 2


def test_a_comparison_stops_at_the_first_point_that_dominates(monkeypatch):
    """The top half (0,4)..(3,1) is non-dominated: 6 comparisons, one per
    pair. In the bottom half (5,5) dominates the rest: 3. (5,5) is then
    dominated by (0,4), the first point it meets: 1. Ten in all."""
    objs = [(0, 4), (1, 3), (2, 2), (3, 1), (5, 5), (6, 6), (7, 7), (8, 8)]
    assert _count(monkeypatch, objs) == 10
