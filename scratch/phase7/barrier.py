"""
A barrier problem for Phase 7 step 5b: a local efficient set that a
neighbourhood of radius r certifies exactly when r <= t, for a ridge t
cells thick. Kept in scratch/; whether it belongs in pymoso/problems/ is
a decision for after 2.0.

On the integer box {0..50}^2, two isotropic quadratics centred at
A = (20, 25) and B = (30, 25), so the true efficient set E is the
eleven lattice points of the segment between them. Around E, a square
annulus of thickness t -- the points with RHO <= ||x - C||_inf < RHO + t,
C = (25, 25), RHO = 8 -- costs PENALTY more on both objectives, so any
point off it dominates any point on it. Outside the annulus the
non-dominated set T is a trap: crossing the annulus needs some
coordinate to change by t + 1, a lattice step of Euclidean length at
least t + 1, so T is certified at radius r exactly when r <= t
(neighbourhoods are Euclidean balls, moso.get_nbors).

The known answer comes from enumerating the box on the true means:
E, T, and for any set and radius whether it is certified (`certified`).
Additive Gaussian noise, SIGMA on each objective. Starts are drawn
uniformly from outside the annulus.
"""
import itertools

from pymoso.chnbase import Oracle
from pymoso.moso import dh, does_weak_dominate, get_nbors, get_nondom

N = 50
C = (25, 25)
RHO = 8
A = (20, 25)
B = (30, 25)
PENALTY = 1000.0
SIGMA = 1.0
BOX = [x for x in itertools.product(range(N + 1), repeat=2)]


def in_box(x):
    return all(0 <= v <= N for v in x)


def linf(x):
    return max(abs(x[i] - C[i]) for i in range(2))


def true_g(x, t):
    """The objectives' expected values; t is the annulus's thickness."""
    g1 = ((x[0] - A[0]) ** 2 + (x[1] - A[1]) ** 2) / 10.0
    g2 = ((x[0] - B[0]) ** 2 + (x[1] - B[1]) ** 2) / 10.0
    p = PENALTY if RHO <= linf(x) < RHO + t else 0.0
    return g1 + p, g2 + p


class _Barrier(Oracle):
    THICKNESS = None

    def __init__(self, rng):
        self.num_obj = 2
        self.dim = 2
        super().__init__(rng)

    def g(self, x, rng):
        if not in_box(x):
            return False, ()
        g1, g2 = true_g(x, self.THICKNESS)
        return True, (g1 + rng.normalvariate(0, SIGMA), g2 + rng.normalvariate(0, SIGMA))


class Barrier1(_Barrier):
    """The annulus one cell thick: a trap at radius 1, escaped at 2."""
    THICKNESS = 1


class Barrier2(_Barrier):
    """Two cells thick: a trap at radii 1 and 2, escaped at 3."""
    THICKNESS = 2


PROBLEMS = {'Barrier1': Barrier1, 'Barrier2': Barrier2}


def efficient_set(t):
    return get_nondom({x: true_g(x, t) for x in BOX})


def trap(t):
    return get_nondom({x: true_g(x, t) for x in BOX if linf(x) >= RHO + t})


def certified(S, r, t):
    """
    Whether S is certified at radius r on the barrier's true means, with
    no relaxation (`certified_by`).
    """
    return certified_by(S, r, lambda x: true_g(x, t), in_box)


def certified_by(S, r, f, feasible):
    """
    Whether S is certified at radius r for objectives `f` on the feasible
    points `feasible` accepts, with no relaxation: S is mutually
    non-dominated, and every feasible point of N_r(S) outside S is weakly
    dominated by a member of S. A neighbour that is not would be
    non-conforming (chnbase.RLESolver.get_ncn, Definition 9), so S would
    not be returned as certified.
    """
    S = set(S)
    if not S or len(get_nondom({s: f(s) for s in S})) != len(S):
        return False
    zero = (0,) * len(f(next(iter(S))))
    nbors = set().union(*(get_nbors(s, r) for s in S)) - S
    return all(any(does_weak_dominate(f(s), f(x), zero, zero) for s in S)
               for x in nbors if feasible(x))


def outside_points(t):
    return [x for x in BOX if linf(x) >= RHO + t]


def get_ranx0(rng, t):
    return rng.choice(outside_points(t))


def metric(soln, t):
    """Hausdorff distance between the true images of `soln` and of E,
    as the built-in testers measure."""
    return dh([true_g(x, t) for x in soln], [true_g(x, t) for x in efficient_set(t)])


def first_objective_min(t):
    return min(true_g(x, t)[0] for x in BOX)
