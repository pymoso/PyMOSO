"""
A plateau problem for Phase 7 step 6: integer capacity thresholds,
where the objective is flat across a cell and changes only when a
threshold is crossed. Kept in scratch/; whether it belongs in
pymoso/problems/ is a decision for after 2.0.

On the box {0..59}^2, cut into W x W cells (W divides 60). Each
objective is a smooth function -- the same two isotropic quadratics as
the barrier problem, centred at A = (15, 30) and B = (45, 30) -- taken at
the centre of the point's cell, so every point of a cell has exactly the
same true value and the true pseudo-gradient is zero inside a cell.
W = 1 has no plateaus: the same functions at each point, the matched
control. Additive Gaussian noise, SIGMA on each objective; starts drawn
uniformly from the box.

The known answer comes from enumerating the box on the true means: the
efficient set E (the union of the optimal cells' points, all tied),
whether a set is certified at a radius (barrier.certified_by, the exact
certificate validated against PyMOSO's own), which ties exist between
points of different cells, and how many single points are certified
traps at each radius (`trap_count`): a property of the problem, not of
any solver.
"""
import itertools
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from barrier import certified_by  # noqa: E402

from pymoso.chnbase import Oracle  # noqa: E402
from pymoso.moso import dh, get_nbors, get_nondom  # noqa: E402

N = 59
A = (15, 30)
B = (45, 30)
SIGMA = 1.0
WIDTHS = (1, 5, 10, 20)
BOX = [x for x in itertools.product(range(N + 1), repeat=2)]


def in_box(x):
    return all(0 <= v <= N for v in x)


def cell(x, w):
    return tuple(v // w for v in x)


def centre(x, w):
    return tuple((v // w) * w + (w - 1) / 2.0 for v in x)


def true_g(x, w):
    c = centre(x, w)
    g1 = ((c[0] - A[0]) ** 2 + (c[1] - A[1]) ** 2) / 10.0
    g2 = ((c[0] - B[0]) ** 2 + (c[1] - B[1]) ** 2) / 10.0
    return g1, g2


class _Plateau(Oracle):
    WIDTH = None

    def __init__(self, rng):
        self.num_obj = 2
        self.dim = 2
        super().__init__(rng)

    def g(self, x, rng):
        if not in_box(x):
            return False, ()
        g1, g2 = true_g(x, self.WIDTH)
        return True, (g1 + rng.normalvariate(0, SIGMA), g2 + rng.normalvariate(0, SIGMA))


PROBLEMS = {}
for _w in WIDTHS:
    PROBLEMS['Plateau{0}'.format(_w)] = type('Plateau{0}'.format(_w), (_Plateau,), {
        'WIDTH': _w, '__doc__': 'Plateaus {0} x {0}.'.format(_w), '__module__': __name__})
globals().update(PROBLEMS)


def width(problem):
    return PROBLEMS[problem].WIDTH


def values(w):
    return {x: true_g(x, w) for x in BOX}


def efficient_set(w):
    return get_nondom(values(w))


def certified(S, r, w):
    return certified_by(S, r, lambda x: true_g(x, w), in_box)


def cross_cell_ties(w, k=None):
    """Pairs of points in different cells with equal true values: in both
    objectives (k None), or in objective k alone."""
    by = {}
    for x in BOX:
        v = true_g(x, w)
        by.setdefault(v if k is None else v[k], set()).add(cell(x, w))
    return sum(len(cells) - 1 for cells in by.values() if len(cells) > 1)


def trap_count(w, r, k=None):
    """
    How many single points are certified at radius r on the true means:
    for both objectives (k None), a point no feasible neighbour within r
    fails to be weakly dominated by; for objective k alone, a point no
    feasible neighbour within r is strictly better than (a local
    minimum at radius r, the trap of a single-objective search). The
    efficient set's own points are included; the count is of traps when
    it is much larger than the efficient set.
    """
    vals = values(w)
    n = 0
    for x in BOX:
        if k is None:
            n += certified({x}, r, w)
        else:
            fx = vals[x][k]
            n += all(vals[y][k] >= fx for y in get_nbors(x, r) if in_box(y))
    return n


def get_ranx0(rng):
    return rng.choice(BOX)


def metric(soln, w):
    """Hausdorff distance between the true images of `soln` and of E."""
    return dh([true_g(x, w) for x in soln], [true_g(x, w) for x in efficient_set(w)])


def first_objective_min(w):
    return min(true_g(x, w)[0] for x in BOX)
