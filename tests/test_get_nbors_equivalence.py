"""
get_nbors builds a neighbourhood directly, and gives exactly what the
box enumeration it replaced gave: the same points, in the same set
iteration order.

Until Phase 4, `chnutils.get_nbors(x, r)` generated every integer
point of the box of side `2r+1` around `x` -- `3**dim` points at the
default radius -- and kept those within distance `r`. At radius 1 that
is `2*dim` points kept. The built-in RA solvers stalled on it from
about ten dimensions, which was recorded for a long time as a
structural limit of the algorithms. It was this function
(KNOWN_ISSUES.md issue 16's note; docs/spark-backend.md).

**Order is part of the contract, not a detail.** The result is a set,
and solvers iterate over it: `ne()` takes the first improving
neighbour at radius above 1, `get_ncn()` and `get_setnbors()` build
lists and unions from it. A set's iteration order follows from the
order its elements were inserted in. A replacement with the same
elements inserted in another order changes solver results --
`test_insertion_order_is_what_keeps_results_the_same` shows it doing
so -- and so the replacement here inserts in the order
`itertools.product` visited the box in.

`enumerated_box` below is the old implementation, kept verbatim as the
reference. Do not "tidy" it.
"""
import random
from itertools import filterfalse, product
from math import ceil, floor

import pytest

from pymoso import chnbase, moso
from pymoso.chnutils import edist, get_nbors, get_solv_prnstreams, isp_run
from pymoso.prng import mrg32k3a
from pymoso.problems.probtpa import ProbTPA
from pymoso.problems.probtpc import ProbTPC
from pymoso.solvers.rminrle import RMINRLE
from pymoso.solvers.rperle import RPERLE

pytestmark = pytest.mark.timeout(300)


def enumerated_box(x, r=1):
    """chnutils.get_nbors as it was through Phase 3 and in every
    release, unchanged."""
    # define a filter function for points too far away
    def edist_filter(x1):
        # also filter the input point
        if edist(x, x1) > r or x == x1:
            return True
    q = len(x)
    # generate all points in a box with sides length 2r around x
    bounds = []
    for i in range(q):
        a = int(ceil(x[i] - r))
        b = int(floor(x[i] + r))
        bounds.append(range(a, b+1))
    boxpts = product(*bounds)
    # remove those farther than r from x and return the list of neighbors
    nbors = set(filterfalse(edist_filter, boxpts))
    return set(nbors)


# (radius, dimensions, points per dimension): 1,066 points in all. The
# old implementation is the slow half; dimension is kept where one
# call of it stays well under a second.
CASES = [
    (1, range(1, 11), 40), (1, (11, 12), 3), (1.5, range(1, 9), 25), (2, range(1, 8), 25),
    (2.5, range(1, 7), 20), (3, range(1, 7), 15), (0.5, range(1, 6), 5), (1.0, range(1, 6), 10),
]


def _points():
    rnd = random.Random(7)
    for r, dims, count in CASES:
        for d in dims:
            for k in range(count):
                x = tuple(rnd.choice([0, 1, -1, rnd.randint(-10**6, 10**6), rnd.randint(-50, 50)]) for _ in range(d))
                yield r, x, k


def test_the_same_points_in_the_same_iteration_order_as_the_box_enumeration():
    compared = 0
    for r, x, k in _points():
        old, new = enumerated_box(x, r), get_nbors(x, r)
        assert new == old, (x, r)
        assert list(new) == list(old), (x, r)
        compared += 1
        if k % 5 == 0:
            # What callers do with it: a union over a set of points,
            # less the points themselves (get_setnbors, get_ncn).
            mcs = {x, tuple(v + 1 for v in x), tuple(v - 2 for v in x)}
            union_old, union_new = set(), set()
            for s in sorted(mcs):
                union_old |= enumerated_box(s, r)
                union_new |= get_nbors(s, r)
            assert list(union_new - mcs) == list(union_old - mcs), (x, r)
    assert compared == 1066


def test_only_points_within_reach_are_examined(monkeypatch):
    """The work is proportional to what is returned, not to the box.
    Counted, not timed: at radius 1 in ten dimensions the box has
    59,049 points and the neighbourhood 20."""
    examined = []
    monkeypatch.setattr(moso, 'edist', lambda a, b: examined.append(b) or edist(a, b))
    x = (3,) * 10
    assert len(get_nbors(x, 1)) == 20
    assert len(examined) == 21                              # the 20 neighbours and x itself
    examined.clear()
    found = get_nbors((0,) * 6, 2)
    assert len(found) == 484 and len(examined) == 485       # against a box of 15,625


def test_high_dimensions_return():
    for dim in (20, 50, 200):
        x = tuple(range(dim))
        found = get_nbors(x, 1)
        assert len(found) == 2 * dim
        assert all(sum(abs(a - b) for a, b in zip(x, p)) == 1 for p in found)


def _whole_run(nbors, problem, solver, x0, crn, radius, monkeypatch):
    # Two readers, and each reads its own module's name: the solver
    # bases call `chnbase.get_nbors`, and `get_setnbors` calls the one
    # beside it in `moso`. A patch on any other module's name for the
    # same function (`chnutils.get_nbors` re-exports it) reaches
    # neither. test_a_missing_neighbour_is_noticed_by_every_run fails
    # if either of these two stops reaching its reader.
    with monkeypatch.context() as patch:
        patch.setattr(moso, 'get_nbors', nbors)
        patch.setattr(chnbase, 'get_nbors', nbors)
        orcstream, solvstream = get_solv_prnstreams((12345,) * 6, mrg32k3a)
        orc = problem(orcstream)
        orc.set_crnflag(crn)
        kwargs = dict(solvprn=solvstream, x0=x0)
        if radius != 1:
            kwargs['radius'] = radius
        res = isp_run(solver, 600, orc, **kwargs)
    return res['itersoln'], res['simcalls'], res['endseed']


RUNS = [
    (problem, solver, x0, crn, radius)
    for problem, x0 in ((ProbTPA, (30, 30)), (ProbTPC, (3, 3, 3)))
    for solver in (RPERLE, RMINRLE)
    for crn in (False, True)
    for radius in (1, 2, 3)
]


@pytest.mark.parametrize("problem,solver,x0,crn,radius", RUNS)
def test_whole_solver_runs_are_identical_to_runs_on_the_box_enumeration(problem, solver, x0, crn, radius, monkeypatch):
    """Every iteration's solution, the call counts and the end seed."""
    assert _whole_run(get_nbors, problem, solver, x0, crn, radius, monkeypatch) == \
        _whole_run(enumerated_box, problem, solver, x0, crn, radius, monkeypatch)


def test_insertion_order_is_what_keeps_results_the_same(monkeypatch):
    """The detector, shown detecting, and the reason the test above
    compares order: the same neighbours handed over in a different
    order change what a solver returns."""
    def shuffled(x, r=1):
        return set(sorted(enumerated_box(x, r), key=lambda p: hash((p, 17))))

    assert all(shuffled(x, r) == enumerated_box(x, r) for r, x, _ in list(_points())[:50])
    moved = [
        run for run in RUNS if run[4] == 3
        and _whole_run(shuffled, *run, monkeypatch) != _whole_run(enumerated_box, *run, monkeypatch)
    ]
    assert moved


def test_a_missing_neighbour_is_noticed_by_every_run(monkeypatch):
    """The patching itself, shown reaching both readers. A
    neighbourhood one point short changes every radius-1 run when it
    replaces `get_nbors` everywhere, and only half of them when it
    reaches the solver bases and not `get_setnbors` -- which is what
    happens, with nothing failing, if the function `get_setnbors`
    calls is patched under a module name it does not read. Measured
    when the helpers moved to `pymoso.moso` (Phase 5): 8 of 8 with
    both, 4 of 8 with `chnbase` alone."""
    def one_short(x, r=1):
        return set(list(enumerated_box(x, r))[:-1])

    runs = [run for run in RUNS if run[4] == 1]
    unmoved = [
        run for run in runs
        if _whole_run(one_short, *run, monkeypatch) == _whole_run(enumerated_box, *run, monkeypatch)
    ]
    assert len(runs) == 8 and unmoved == []
