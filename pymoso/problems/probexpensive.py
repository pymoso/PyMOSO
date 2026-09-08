#!/usr/bin/env python
"""
Summary
-------
Provides an Oracle whose per-replication objective values are cheap
and deterministic (the same distribution as ProbSimpleSO -- see
probsimpleso.py: a single feasible dimension in [-100, 100], true
minimizer x=0, observation x**2 + Normal(0, 3)) but whose per-
replication CPU cost is tunable and independent of that distribution.

Every existing test problem is cheap enough that --simpar/--proc
dispatch overhead dominates its runtime, so nothing in the test suite
exercises parallel replication in the regime the README recommends it
for: "the simulation takes a half second or more to generate a single
observation." This oracle exists to fill that gap.

`_burn` performs `burn_units` chained sha256 rounds on a fixed input --
real CPU work (not time.sleep, so it exercises the same contention and
serialization a genuinely expensive simulation would), and it never
reads `x` or `rng`. That decoupling is the whole point: g()'s return
value for a given (x, rng-state) is bit-identical regardless of
burn_units, so varying the cost never changes what a test asserts,
only how long producing it takes. Verified directly in
tests/test_expensive_oracle.py, not just claimed here.

`burn_units` is a plain class attribute, not a constructor parameter.
Two things need it to be resolvable from the class alone, by
reference, rather than passed at construction time:

- A --simpar worker rebuilds an Oracle from just (class, seed)
  (chnbase.mp_replicate) -- there is no channel for extra per-instance
  state to cross into that call.
- --proc's testsolve() path pickles a fully-built Oracle instance
  through multiprocessing.Pool, which pickles task data internally
  even under the 'fork' start method (a Pool's workers communicate
  through a real Queue/pipe, unlike a bare Process under fork, whose
  args are just inherited memory). A dynamically-constructed class
  (e.g. via type()) or a mutated global/env var would pickle-by-
  reference to a class a fresh worker import can't reconstruct under
  'spawn'/'forkserver' -- exactly the start method 3.14's forkserver
  default would hit. Fixing the cost in a concrete, statically-defined
  subclass avoids that regardless of start method.
"""
from hashlib import sha256

from ..chnbase import Oracle


def _burn(units):
    """
    Burn CPU: `units` chained sha256 rounds on a fixed input. Takes no
    input beyond `units`, so it never affects a replication's return
    value -- only wall-clock time.

    Parameters
    ----------
    units : int
    """
    digest = b'pymoso-expensive-oracle-burn'
    for _ in range(units):
        digest = sha256(digest).digest()


class ProbExpensive(Oracle):
    """
    An Oracle simulating the same problem as ProbSimpleSO, plus a
    tunable CPU burn per replication that does not affect g()'s output.

    Do not instantiate this directly for a parallel-dispatch test:
    burn_units=0 makes it behave like ProbSimpleSO with extra
    indirection and no real cost for --simpar/--proc to dispatch
    against. Use ProbExpensiveLight or ProbExpensiveModerate below (or
    add another named subclass fixing burn_units, following the same
    pattern) instead.

    Attributes
    ----------
    num_obj : int, 1
    dim : int, 1
    burn_units : int, class attribute, default 0
        Number of chained sha256 rounds g() performs per replication,
        before drawing. See the module docstring for why this is a
        class attribute rather than a constructor argument.

    Parameters
    ----------
    rng : prng.MRG32k3a object

    See also
    --------
    chnbase.Oracle
    problems.probsimpleso.ProbSimpleSO
    """
    burn_units = 0

    def __init__(self, rng):
        self.num_obj = 1
        self.dim = 1
        super().__init__(rng)

    def g(self, x, rng):
        """
        Simulates one replication. PyMOSO requires that all valid
        Oracles implement an Oracle.g.

        Parameters
        ----------
        x : tuple of int
        rng : prng.MRG32k3a object

        Returns
        -------
        isfeas : bool
        tuple of float
            simulated objective values
        """
        xr = range(-100, 101)
        isfeas = True
        for xi in x:
            if not xi in xr:
                isfeas = False
        obj1 = []
        if isfeas:
            _burn(self.burn_units)
            z1 = rng.normalvariate(0, 3)
            obj1 = x[0]**2 + z1
        return isfeas, (obj1, )


class ProbExpensiveLight(ProbExpensive):
    """
    ProbExpensive at a light cost tier: burn_units=2,000.

    Measured locally (CPython 3.10/3.14, single core, AMD Ryzen 5
    5600X3D) at ~1.3ms/replication -- roughly 15-20x the ~60-100us
    --simpar Queue round-trip dispatch overhead measured on the same
    machine. Cheap enough for tests that just need "not dispatch-
    overhead-dominated" without much added runtime.
    """
    burn_units = 2_000


class ProbExpensiveModerate(ProbExpensive):
    """
    ProbExpensive at a moderate cost tier: burn_units=20,000.

    Measured locally at ~13ms/replication -- roughly 150-200x measured
    dispatch overhead (see ProbExpensiveLight), the tier used by
    tests/test_expensive_oracle.py's and tests/test_parallel_dispatch.py's
    parallel-path exercises, where dispatch overhead needs to be
    clearly not dominant.
    """
    burn_units = 20_000


class ProbExpensiveHeavy(ProbExpensive):
    """
    ProbExpensive at a heavy cost tier: burn_units=60,000.

    Measured locally at ~35ms/replication. Not used by any pytest test
    (too slow to be worth the added CI time over what
    ProbExpensiveModerate already demonstrates) -- exists for
    docs/bench_parallel_dispatch.py, to show the regime where dispatch
    overhead is unambiguously negligible.
    """
    burn_units = 60_000
