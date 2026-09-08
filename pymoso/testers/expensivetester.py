#!/usr/bin/env python
"""
Summary
-------
Provide the tester for the tunable-cost expensive problem
(problems.probexpensive). Mirrors testers.simplesotester exactly --
same true_g, same feasible space, same true solution -- since
ProbExpensive simulates the identical distribution as ProbSimpleSO
with a CPU burn layered on top that does not change it.
"""
from ..problems import probexpensive
from ..chnutils import edist


def true_g(x):
    """
    Compute the expected values of a point.

    Parameters
    ----------
    x : tuple of int
        A feasible point

    Returns
    -------
    tuple of float
        The objective values
    """
    obj1 = x[0]**2
    return (obj1,)


def get_ranx0(rng):
    """
    Uniformly sample from the feasible space.

    Parameters
    ----------
    rng : prng.MRG32k3a object

    Returns
    -------
    x0 : tuple of int
        The randomly chosen point
    """
    xr = range(-100, 101)
    x1 = rng.choice(xr)
    x0 = (x1,)
    return x0


soln = (0,)


class ExpensiveTester(object):
    """
    Store useful data for working with the expensive test problem, at
    the ProbExpensiveModerate cost tier.

    Attributes
    ----------
    ranorc : chnbase.Oracle class
    true_g : function
    soln : tuple of int
        The true minimizer
    get_ranx0 : function
    """
    def __init__(self):
        self.ranorc = probexpensive.ProbExpensiveModerate
        self.true_g = true_g
        self.soln = soln
        self.get_ranx0 = get_ranx0

    def metric(self, eles):
        """
        Compute a metric from a simulated solution to the true solution.

        Parameters
        ----------
        eles : set of tuple of numbers
            Simulated solution

        Returns
        -------
        float
            The performance metric
        """
        point = eles.pop()
        dist = edist(point, self.soln)
        return dist
