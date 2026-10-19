"""
The sign of the CRN covariance, Phase 7 step 6b part 3: a threshold
problem, a conservation problem and an antithetic one. Kept in scratch/
with crnsync.py.

Each is synchronized: every point makes the same draws in the same
roles, so what a point's response to those draws looks like is all that
sets the covariance. Every period is i.i.d. and uses its own draws, so
a replication's correlation between two points equals one period's, at
any number of periods; each problem's exact one-period correlations are
computed here and are the measurement's known answer.

`Route`, the threshold case. x = (x1, x2) in {0..10}^2. Each period,
NC customers arrive; each draws a routing level R = floor(10 u) and goes
to server A if R < x1, else to B; then a service S = 1 + floor(3 u'),
drawn after the branch (always, at every point, so CRN shares it).
Server A's capacity is x2, B's is CB. Objective 1 is overflow,
(L_A - x2)^+ + (L_B - CB)^+; objective 2 is idle capacity plus a
transfer cost TAU per customer sent to B. At x and x + e1 the customers
with R = x1 change server and keep their service time.

`split_exact`, the conservation case, exact only (no simulation: the
enumeration is the answer). Two substitutable products stocked at
(x1, x2); a fixed total DS splits as D1 = floor((DS + 1) w), D2 = DS - D1
on one shared preference draw w. Objectives holding and shortage, as in
the inventory twins.

`Antithetic`, artificial on purpose: crnsync.SyncFixed, with every
uniform u read as 1 - u at points whose x1 + x2 is odd. Every axis
neighbour has the other parity. 1 - u is uniform, so each point's
marginal law, the closed form, the efficient set and the known answer
are SyncFixed's (checked empirically, as for the other twins); at even
points the output is SyncFixed's bit for bit.
"""
import itertools
import math
import os
import sys
from fractions import Fraction

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import crnsync  # noqa: E402
from barrier import certified_by  # noqa: E402

from pymoso.chnbase import Oracle  # noqa: E402
from pymoso.moso import get_nondom  # noqa: E402

# ---- Route ----

MR = 10         # routing levels; x1 = 0..MR
KS = 3          # service 1..KS
NC = 3          # customers per period
CB = 4          # server B's capacity
TAU = 1         # transfer cost per customer sent to B
NR = 10
T = 30
ROUTE_BOX = [x for x in itertools.product(range(NR + 1), repeat=2)]


def route_in_box(x):
    return all(0 <= v <= NR for v in x)


def route_costs(x, toa, services):
    """One period's (overflow, idle + transfer) from each customer's
    server (True: A) and service time."""
    la = sum(s for a, s in zip(toa, services) if a)
    lb = sum(s for a, s in zip(toa, services) if not a)
    nb = sum(not a for a in toa)
    return (max(la - x[1], 0) + max(lb - CB, 0),
            max(x[1] - la, 0) + max(CB - lb, 0) + TAU * nb)


def simulate_route(x, rng, periods, below=False):
    """`below` routes to A when R <= x1: the wrong closed form's model,
    for `mutations`."""
    tot = [0.0, 0.0]
    for _ in range(periods):
        toa, services = [], []
        for _ in range(NC):
            r = int(MR * rng.random())
            toa.append(r <= x[0] if below else r < x[0])
            services.append(1 + int(KS * rng.random()))
        for k, c in enumerate(route_costs(x, toa, services)):
            tot[k] += c
    return tot[0] / periods, tot[1] / periods


def _route_joint(x, y):
    """Per customer: [((A at x, A at y), weight)] over routing levels."""
    out = {}
    for r in range(MR):
        key = (r < x[0], r < y[0])
        out[key] = out.get(key, 0) + Fraction(1, MR)
    return list(out.items())


def _route_moments(x, y):
    """Exact one-period E f(x), E f(y), E f(x)^2, E f(y)^2, E f(x) f(y)
    per objective, under CRN (shared routing levels and services)."""
    per = [(ab, w * Fraction(1, KS), s) for ab, w in _route_joint(x, y) for s in range(1, KS + 1)]
    m = [[Fraction(0)] * 5 for _ in range(2)]
    for combo in itertools.product(per, repeat=NC):
        w = Fraction(1)
        for c in combo:
            w *= c[1]
        services = [c[2] for c in combo]
        fx = route_costs(x, [c[0][0] for c in combo], services)
        fy = route_costs(y, [c[0][1] for c in combo], services)
        for k in range(2):
            for j, v in enumerate((fx[k], fy[k], fx[k] ** 2, fy[k] ** 2, fx[k] * fy[k])):
                m[k][j] += w * v
    return m


def exact_route_g(x):
    m = _route_moments(x, x)
    return m[0][0], m[1][0]


def true_route_g(x):
    return tuple(float(v) for v in exact_route_g(x))


def _rho(m):
    ex, ey, exx, eyy, exy = m
    vx, vy = exx - ex * ex, eyy - ey * ey
    if vx == 0 or vy == 0:
        return None
    return float(exy - ex * ey) / math.sqrt(float(vx) * float(vy))


def route_rho(x, y):
    """Exact CRN correlation per objective, any number of periods."""
    return tuple(_rho(m) for m in _route_moments(x, y))


class Route(Oracle):
    NUM_OBJ = 2
    PERIODS = T
    TRUE_G = staticmethod(true_route_g)
    BELOW = False

    def __init__(self, rng):
        self.num_obj = self.NUM_OBJ
        self.dim = 2
        super().__init__(rng)

    @classmethod
    def run(cls, x, rng, periods=None):
        return simulate_route(x, rng, cls.PERIODS if periods is None else periods, cls.BELOW)

    def g(self, x, rng):
        if not route_in_box(x):
            return False, ()
        return True, self.run(x, rng)


class RouteBelow(Route):
    """Routes to A when R <= x1; for `mutations` only."""
    BELOW = True


def route_values():
    return {x: true_route_g(x) for x in ROUTE_BOX}


def route_efficient_set():
    return get_nondom(route_values())


def route_get_ranx0(rng):
    return rng.choice(ROUTE_BOX)


# ---- Split, exact ----

DS = 20
SPLIT_BOX = [x for x in itertools.product(range(DS + 1), repeat=2)]


def _split_costs(x, d1):
    d = (d1, DS - d1)
    return (sum(max(a - b, 0) for a, b in zip(x, d)), sum(max(b - a, 0) for a, b in zip(x, d)))


def split_rho(x, y):
    """Exact correlation per objective of the one-period costs at x and y
    on a shared preference draw; any number of periods."""
    out = []
    w = Fraction(1, DS + 1)
    for k in range(2):
        m = [Fraction(0)] * 5
        for d1 in range(DS + 1):
            a, b = _split_costs(x, d1)[k], _split_costs(y, d1)[k]
            for j, v in enumerate((a, b, a * a, b * b, a * b)):
                m[j] += w * v
        out.append(_rho(m))
    return tuple(out)


def split_exact():
    """Rows for every axis pair (x, x + e_i) and swap pair (x + e1,
    x + e2) in the box: (kind, x, y, rho per objective)."""
    rows = []
    for x in SPLIT_BOX:
        cands = [('axis', x, (x[0] + 1, x[1])), ('axis', x, (x[0], x[1] + 1)),
                 ('swap', (x[0] + 1, x[1]), (x[0], x[1] + 1))]
        for kind, a, b in cands:
            if max(a + b) <= DS:
                rows.append((kind, a, b, split_rho(a, b)))
    return rows


# ---- Antithetic ----

class _Flipped:
    """Reads every uniform of `rng` as 1 - u, through the two methods
    the inventory simulation calls (Random.expovariate's own formula)."""

    def __init__(self, rng):
        self._rng = rng

    def random(self):
        return 1.0 - self._rng.random()

    def expovariate(self, lambd):
        return -math.log(1.0 - self.random()) / lambd

    def raw_consumed(self):
        return self._rng.raw_consumed()


def flipped(x):
    return (x[0] + x[1]) % 2 == 1


class Antithetic(crnsync.SyncFixed):
    """SyncFixed, with 1 - u for u at odd points."""

    @classmethod
    def run(cls, x, rng, periods=None, trace=None):
        return super().run(x, _Flipped(rng) if flipped(x) else rng, periods, trace)


class AntitheticSO(crnsync.SyncFixedSO):
    run = Antithetic.__dict__['run']


# Exact one-period correlation of the inventory twins' synchronized
# arm and of Antithetic. Per item, shortage is a(d) + b(d) P with P the
# expediting cost; holding is h(d). P = -MU log(1 - u), its flip
# -MU log(u): E P = MU, E P^2 = 2 MU^2, E P P' = MU^2 (2 - pi^2 / 6).
# Items use separate draws, so per-objective moments add over items.

def _item_parts(xi, flip):
    """[(weight, holding, a, b)] over the 20 demand levels, demand read
    from the uniform as D, or as M - 1 - D when flipped."""
    M = crnsync.M
    out = []
    for d in range(M):
        dd = M - 1 - d if flip else d
        hold = crnsync.H * max(xi - dd, 0)
        a = crnsync.B * max(dd - xi, 0)
        b = 1 if dd > xi else 0
        out.append((1.0 / M, hold, a, b))
    return out


def inventory_rho(x, y, flip_x=None, flip_y=None, wrong_epp=False):
    """Exact CRN correlation per objective between x and y, each read
    flipped or not (default: Antithetic's parity rule). `wrong_epp`
    takes a cost and its flip as independent (E P P' = MU^2), for
    `mutations`."""
    MU = crnsync.MU
    fx = flipped(x) if flip_x is None else flip_x
    fy = flipped(y) if flip_y is None else flip_y
    epp = 2 * MU * MU if fx == fy else MU * MU * (1 if wrong_epp else 2 - math.pi ** 2 / 6)
    cov = [0.0, 0.0]
    vx = [0.0, 0.0]
    vy = [0.0, 0.0]
    for xi, yi in zip(x, y):
        px, py = _item_parts(xi, fx), _item_parts(yi, fy)
        # holding
        hx = sum(p[0] * p[1] for p in px)
        hy = sum(p[0] * p[1] for p in py)
        cov[0] += sum(p[0] * p[1] * q[1] for p, q in zip(px, py)) - hx * hy
        vx[0] += sum(p[0] * p[1] ** 2 for p in px) - hx * hx
        vy[0] += sum(p[0] * p[1] ** 2 for p in py) - hy * hy
        # shortage: a + b P
        sx = sum(p[0] * (p[2] + MU * p[3]) for p in px)
        sy = sum(p[0] * (p[2] + MU * p[3]) for p in py)
        cov[1] += sum(p[0] * (p[2] * q[2] + MU * p[2] * q[3] + MU * p[3] * q[2] + epp * p[3] * q[3])
                      for p, q in zip(px, py)) - sx * sy
        vx[1] += sum(p[0] * (p[2] ** 2 + 2 * MU * p[2] * p[3] + 2 * MU * MU * p[3]) for p in px) - sx * sx
        vy[1] += sum(p[0] * (p[2] ** 2 + 2 * MU * p[2] * p[3] + 2 * MU * MU * p[3]) for p in py) - sy * sy
    return tuple(None if a == 0 or b == 0 else c / math.sqrt(a * b) for c, a, b in zip(cov, vx, vy))


def certified(S, r, table):
    return certified_by(S, r, table.__getitem__, table.__contains__)
