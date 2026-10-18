"""
Synchronization problems for Phase 7 step 6b: where CRN fails because
neighbouring points consume different numbers of variates. Kept in
scratch/; whether any belongs in pymoso/problems/ is a decision for
after 2.0.

PyMOSO's CRN restarts every replication at the same position for every
point (oracle.py, `_block_for`: stream = iteration, offset =
replication * REPL_STRIDE), so a draw-count difference desynchronizes
only the rest of that one replication.

The inventory twins. Two items, x = (x1, x2) in {0..19}^2 (stock
levels). Each of T periods, in one interleaved stream: item 1's demand
D = floor(20 u) from one raw draw (not randint, which rejects); if
D > x1, an expediting cost P ~ Exp(mean MU); then the same for item 2.
Objective 1 is holding, H * sum (x - D)^+ / T; objective 2 is shortage,
sum [B (D - x)^+ + 1{D > x} P] / T. `SyncVar` draws P only on a
stockout, so at x and x + e1 the streams desynchronize in the first
period with D1 = x1 + 1 (probability 1/20 a period). `SyncFixed` always
draws P and discards it when there is no stockout: four draws a period
at every point. Each draw is a fresh uniform given the past, so a
replication's output at any one point has the same distribution in
both twins (the joint law of the demands and costs used is i.i.d. in
both): identical true means, variances and known answer; only the
coupling across points differs. `SyncVarSO`/`SyncFixedSO` are the
single-objective counterparts (the newsvendor cost, holding plus
shortage), for R-SPLINE, whose first-objective minimum on the
bi-objective twins is trivially x = 0.

The true means are closed-form, computed in exact Fractions and
rounded once to float, so points whose exact means are equal get equal
floats (the items are symmetric: (a, b) and (b, a) tie in both
objectives), and unequal exact means differ by far more than rounding
at these denominators.

Calibration (`Calib`, `CalibVar`): g = f(x) + (Z1 + C*Z2, Z2), with
CalibVar discarding (x1 + x2) % 2 raw draws between Z1 and Z2, so every
axis neighbour pair desynchronizes after Z1. Exact correlations under
CRN: 1 and 1 for Calib; 1/(1 + C^2) and 0 for CalibVar; 0 without CRN.
The variance ratio Var(difference) / (Var x + Var y) is 1 - rho.

`RandRange`: one dimension, x in {0..59}, g = randint(0, 4 + x) + Z.
The draw count's only dependence on x is randint's rejection loop over
a range that grows with x.
"""
import itertools
import os
import sys
from fractions import Fraction

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from barrier import certified_by  # noqa: E402

from pymoso.chnbase import Oracle  # noqa: E402
from pymoso.moso import dh, get_nondom  # noqa: E402

N = 19
M = 20          # demand levels 0..M-1
H = 1
B = 4
MU = 10
T = 30
BOX = [x for x in itertools.product(range(N + 1), repeat=2)]


def in_box(x):
    return all(0 <= v <= N for v in x)


def simulate(x, rng, periods, fixed, trace=None):
    """One replication: (holding, shortage), per-period averages. With
    `trace` a list, appends rng.raw_consumed() after each period."""
    hold = short = 0.0
    for _ in range(periods):
        for xi in x:
            d = int(M * rng.random())
            p = rng.expovariate(1.0 / MU) if fixed else None
            if d > xi:
                if p is None:
                    p = rng.expovariate(1.0 / MU)
                short += B * (d - xi) + p
            else:
                hold += H * (xi - d)
        if trace is not None:
            trace.append(rng.raw_consumed())
    return hold / periods, short / periods


def _item(xi):
    """Exact (E holding, E shortage) of one item at stock xi, one period."""
    hold = sum(Fraction(H * (xi - d), M) for d in range(M) if d < xi)
    short = sum(Fraction(B * (d - xi) + MU, M) for d in range(M) if d > xi)
    return hold, short


def exact_g(x):
    a, b = _item(x[0]), _item(x[1])
    return a[0] + b[0], a[1] + b[1]


def true_g(x):
    return tuple(float(v) for v in exact_g(x))


def true_cost(x):
    """The single-objective twins' mean: holding plus shortage."""
    return float(sum(exact_g(x)))


class _Sync(Oracle):
    FIXED = None
    PERIODS = T
    NUM_OBJ = 2

    def __init__(self, rng):
        self.num_obj = self.NUM_OBJ
        self.dim = 2
        super().__init__(rng)

    def g(self, x, rng):
        if not in_box(x):
            return False, ()
        return True, simulate(x, rng, self.PERIODS, self.FIXED)


class SyncVar(_Sync):
    """Draws an expediting cost only on a stockout."""
    FIXED = False


class SyncFixed(_Sync):
    """Always draws it: four draws a period at every point."""
    FIXED = True


class _SyncSO(_Sync):
    NUM_OBJ = 1

    def g(self, x, rng):
        if not in_box(x):
            return False, ()
        return True, (sum(simulate(x, rng, self.PERIODS, self.FIXED)),)


class SyncVarSO(_SyncSO):
    FIXED = False


class SyncFixedSO(_SyncSO):
    FIXED = True


def with_periods(cls, periods):
    """`cls` simulating `periods` periods (the T sweep)."""
    return type('{0}T{1}'.format(cls.__name__, periods), (cls,),
                {'PERIODS': periods, '__module__': __name__})


PROBLEMS = {c.__name__: c for c in (SyncVar, SyncFixed, SyncVarSO, SyncFixedSO)}


def values():
    return {x: true_g(x) for x in BOX}


def efficient_set():
    return get_nondom(values())


def certified(S, r):
    return certified_by(S, r, true_g, in_box)


def metric(soln):
    """Hausdorff distance between the true images of `soln` and of E."""
    return dh([true_g(x) for x in soln], [true_g(x) for x in efficient_set()])


def cost_min():
    return min(true_cost(x) for x in BOX)


def get_ranx0(rng):
    return rng.choice(BOX)


# ---- calibration ----

C = 1.0


class Calib(Oracle):
    """Synchronized by construction: exact CRN correlations 1 and 1."""
    SKIP = False

    def __init__(self, rng):
        self.num_obj = 2
        self.dim = 2
        super().__init__(rng)

    def g(self, x, rng):
        if not all(0 <= v <= 9 for v in x):
            return False, ()
        z1 = rng.normalvariate(0, 1)
        if self.SKIP:
            for _ in range((x[0] + x[1]) % 2):
                rng.random()
        z2 = rng.normalvariate(0, 1)
        return True, (x[0] + x[1] + z1 + C * z2, x[0] - x[1] + z2)


class CalibVar(Calib):
    """Desynchronized after Z1 at every axis pair: exact CRN correlations
    1/(1 + C^2) and 0."""
    SKIP = True


def calib_rho(cls, crn):
    if not crn:
        return (0.0, 0.0)
    return (1.0 / (1.0 + C * C), 0.0) if cls.SKIP else (1.0, 1.0)


CALIB_BOX = [x for x in itertools.product(range(10), repeat=2)]


class RandRange(Oracle):
    """g = randint(0, 4 + x) + Z on x in {0..59}."""

    def __init__(self, rng):
        self.num_obj = 1
        self.dim = 1
        super().__init__(rng)

    def g(self, x, rng):
        if not 0 <= x[0] <= 59:
            return False, ()
        return True, (rng.randint(0, 4 + x[0]) + rng.normalvariate(0, 1),)
