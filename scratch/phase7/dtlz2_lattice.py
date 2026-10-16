"""
DTLZ2 on an integer lattice, with additive Gaussian noise: the test
problem for the many-objective experiments (docs/many-objective-baseline.md).

Decision dimension is fixed at N_DIM = 8 for every objective count M,
so that M can vary without decision dimension varying with it. Each
x_i is an integer in {0, ..., L}, mapped to t_i = (x_i + 1/2)/(L + 1),
which is never 0 or 1 (so no cos(pi/2) = 0 collapses several position
tuples onto one objective vector) and is exactly 1/2 at x_i = L/2.

Position variables are t_1..t_{M-1}; distance variables t_M..t_8,
g = sum (t_i - 1/2)^2 over them. True objectives are (1 + g) * u, u on
the unit sphere, so:

- the lattice's efficient set is exactly {x : every distance variable
  is L/2} -- (1+g) u is dominated by u, and u is a lattice point;
- a point's distance to the front is g(x), exactly.

Noise: f_m(x) + sigma * Z_m, Z_m independent standard normal,
homoscedastic. `sigma_for(M, arm)` gives arm A (fixed sigma) and arm B
(sigma * sqrt(2/M), holding the per-component signal-to-noise ratio of
a typical front point at its M = 2 value).

Not part of pymoso. Whether it earns a place in pymoso/problems/ is a
decision for after 2.0.
"""
from math import cos, sin, pi, sqrt

from pymoso.chnbase import Oracle

N_DIM = 8
L = 10          # default lattice: x_i in {0..L}; L even
MID = L // 2


def t_of(xi, L=L):
    return (xi + 0.5) / (L + 1)


def is_feasible(x, L=L):
    return len(x) == N_DIM and all(xi == int(xi) and 0 <= xi <= L for xi in x)


def g_dist(x, M, L=L):
    """Distance to the front: exact, O(N_DIM)."""
    return sum((t_of(xi, L) - 0.5) ** 2 for xi in x[M - 1:])


def true_f(x, M, L=L):
    """The noise-free objective vector (tuple of M floats)."""
    th = [t_of(xi, L) * pi / 2 for xi in x[:M - 1]]
    r = 1.0 + g_dist(x, M, L)
    f = []
    for m in range(M):
        # f_1 = r cos th_1 ... cos th_{M-1}; f_m replaces the last
        # (m-1) cosines' final one with a sine; f_M = r sin th_1.
        v = r
        for j in range(M - 1 - m):
            v *= cos(th[j])
        if m > 0:
            v *= sin(th[M - 1 - m])
        f.append(v)
    return tuple(f)


def is_efficient(x, M, L=L):
    return all(xi == L // 2 for xi in x[M - 1:])


def sigma_for(M, arm, sigma0):
    if arm == 'A':
        return sigma0
    if arm == 'B':
        return sigma0 * sqrt(2.0 / M)
    raise ValueError(arm)


_CLASSES = {}


def make_problem(M, sigma, L=L):
    """An Oracle class for M objectives at noise sigma. A class per
    configuration, because a worker rebuilds an Oracle from its class
    alone (CLAUDE.md, Testing). Runs here are serial; `g_calls` counts
    every g() call on the instance, infeasible ones included, which
    `simcalls` does not (rng-interface-design.md §11 entry 13)."""
    key = (M, sigma, L)
    if key in _CLASSES:
        return _CLASSES[key]

    class DTLZ2Lattice(Oracle):
        num_obj_ = M
        sigma_ = sigma
        lattice_ = L

        def __init__(self, rng):
            self.num_obj = M
            self.dim = N_DIM
            self.g_calls = 0
            super().__init__(rng)

        def g(self, x, rng):
            self.g_calls += 1
            if not is_feasible(x, L):
                return False, (None,) * M
            f = true_f(x, M, L)
            return True, tuple(fm + sigma * rng.normalvariate(0, 1) for fm in f)

    DTLZ2Lattice.__name__ = 'DTLZ2Lattice_M{0}_L{1}'.format(M, L)
    DTLZ2Lattice.__qualname__ = DTLZ2Lattice.__name__
    _CLASSES[key] = DTLZ2Lattice
    return DTLZ2Lattice
