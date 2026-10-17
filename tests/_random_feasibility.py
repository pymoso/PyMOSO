"""A problem whose feasibility depends on its random numbers, for
tests/test_warm_start.py (KNOWN_ISSUES.md issue 19). In a module of its
own so that a worker started by spawn or forkserver can import it by
name."""
from pymoso.problems.probexpensive import ProbExpensiveBi
from pymoso.testers.tpatester import TPATester


class RandomEdgeBi(ProbExpensiveBi):
    """ProbExpensiveBi, except that where x[0] is between 0 and 5 a
    replication is infeasible with probability 0.03. A block of m
    replications there is feasible with probability 0.97^m, so a point
    the solver found feasible at one sample size can be found
    infeasible at the next: the warm start the RA solvers rely on."""

    def g(self, x, rng):
        if 0 <= x[0] <= 5 and rng.random() < 0.03:
            return False, (None, None)
        return super().g(x, rng)


class RandomEdgeTester(TPATester):
    """TPATester over RandomEdgeBi, for testsolve()."""

    def __init__(self):
        super().__init__()
        self.ranorc = RandomEdgeBi
