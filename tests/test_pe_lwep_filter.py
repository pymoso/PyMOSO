"""
PE's Steps 1-3 (docs/algorithm-audit.md, finding 3).

1. Â⁰ = Min(Â_old ∪ {x0});
2. Âʷ = RemoveNonLWEP(Â⁰);
3. if Âʷ is empty, Âʷ = Â⁰.

The epsilon values are placed from Âʷ. The code filtered Â_old instead
and placed them from Min's output whatever the filter found. Here Min,
the filter and SPLINE are scripted: Min returns three points, the
standard errors are 0, and SPLINE returns the point lowest on the
constrained objective, so the traceback stops after one call per
epsilon value and the calls show the epsilons placed.
"""
import random

import pytest

from pymoso.solvers.rpe import RPE
from pymoso.solvers.rperle import RPERLE

A, B, C = (0, 10), (5, 5), (10, 0)          # the points are their own images
X0, OLD = (20, 20), (15, 15)
MIN_OUTPUT = {A, B, C}


def _scripted(cls, lweps, min_output=MIN_OUTPUT, se=0.0):
    class Scripted(cls):
        def __init__(self):
            self.x0 = X0
            self.nu = 1
            self.m = 4
            self.betaeps = 0.5
            self.num_obj = 2
            self.sprn = random.Random(0)
            self.gbar = {x: tuple(float(v) for v in x) for x in min_output | {X0, OLD}}
            self.sehat = {x: (se, se) for x in self.gbar}
            self.filtered = []
            self.epsilons = []
            self.starts = []

        def upsample(self, points):
            return points

        def get_min(self, points):
            return set(min_output)

        def remove_nlwep(self, points):
            self.filtered.append(set(points))
            return set(lweps) & points, set()

        def spline(self, x0, e, nobj, kcon):
            self.epsilons.append(e)
            self.starts.append(x0)
            low = min(self.gbar, key=lambda t: self.gbar[t][kcon])
            return set(), low, self.gbar[low], self.sehat[low]

    return Scripted()


@pytest.mark.parametrize("cls", [RPERLE, RPE])
def test_the_filter_is_applied_to_mins_output(cls):
    solver = _scripted(cls, {A, C})
    solver.pe({OLD})
    assert solver.filtered == [MIN_OUTPUT]


@pytest.mark.parametrize("cls", [RPERLE, RPE])
def test_epsilons_are_placed_from_the_lweps_only(cls):
    """B is not an LWEP: only C's or A's value, 10, is placed."""
    solver = _scripted(cls, {A, C})
    solver.pe({OLD})
    assert solver.epsilons == [10.0]


@pytest.mark.parametrize("cls", [RPERLE, RPE])
def test_with_no_lwep_epsilons_are_placed_from_mins_output(cls):
    """Step 3's fallback: B's value 5 and the far end's 10."""
    solver = _scripted(cls, set())
    solver.pe({OLD})
    assert solver.epsilons == [5.0, 10.0]


@pytest.mark.parametrize("seed", range(4))
@pytest.mark.parametrize("cls", [RPERLE, RPE])
def test_the_traceback_starts_from_mins_output_not_only_the_lweps(cls, seed):
    """The listing's start is the best point of T ∪ Â⁰ under the
    constraint. D = (1, 9) is not an LWEP, and with standard errors of 1
    the one epsilon, 9 on either objective, leaves A or C out: D is the
    best start whichever objective the tie-break picks."""
    d = (1, 9)
    solver = _scripted(cls, {A, C}, min_output={A, C, d}, se=1.0)
    solver.sprn = random.Random(seed)
    solver.pe({OLD})
    assert solver.epsilons == [9.0]
    assert solver.starts == [d]
