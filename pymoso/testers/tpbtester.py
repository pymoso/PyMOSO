#!/usr/bin/env python
"""
Summary
-------
Provide the tester for Test Problem B
"""
from ..problems import probtpb
from math import exp
from ..moso import dh


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
    g1 = 4*x[0]/100
    if x[1] >= 0 and x[1] <= 40:
        f2 = 4 - 3*exp(-pow((x[1]-20)/2, 2))
    else:
        f2 = 4 - 2*exp(-pow((x[1]-70)/20, 2))
    alpha = 0.25 + 3.75*(f2 - 1)
    if g1 <= f2:
        h = 1 - pow(g1/f2, alpha)
    else:
        h = 0
    obj1 = g1
    obj2 = f2*h
    return obj1, obj2


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
    xr = range(0, 101)
    x1 = rng.choice(xr)
    x2 = rng.choice(xr)
    x0 = (x1, x2)
    return x0


class TPBTester(object):
    """
    Store useful data for working with Test Problem B.

    Attributes
    ----------
    ranorc : chnbase.Oracle class
    true_g : function
    soln : list of set of tuple of int
        The N_1-local efficient sets, as decision points
    soln_images : list of list of tuple of float
        true_g of each point of each set in soln, computed when the
        tester is made
    get_ranx0 : function
    """
    def __init__(self):
        self.ranorc = probtpb.ProbTPB
        self.true_g = true_g
        self.soln = soln
        self.soln_images = [[self.true_g(x) for x in les] for les in soln]
        self.get_ranx0 = get_ranx0

    def metric(self, eles):
        """
        Compute a metric from a simulated solution to the true solution.

        Parameters
        ----------
        eles : set of tuple of numbers
            The simulated solution

        Returns
        -------
        float
            The performance metric
        """
        efrontier = []
        for point in eles:
            objs = self.true_g(point)
            efrontier.append(objs)
        distlist = []
        for les in self.soln_images:
            dist = dh(efrontier, les)
            distlist.append(dist)
        return min(distlist)


# The N_1-local efficient set in each of the rows x2 = 70 and x2 = 20, as
# decision points; the second is the global efficient set. f has its
# minima 2 at x2 = 70 and 1 at x2 = 20, and for 0 <= g1 <= f, g2 = f*h is
# strictly increasing in f, so each row's points dominate their
# neighbours off the row; along a row g2 falls strictly until g1 = f
# (x1 = 50 and 25), where g2 = 0 and every larger x1 is dominated. The
# full argument is in tests/test_tester_reference_sets.py, which also
# checks both sets against the definition. These are the efficient sets,
# not the weakly efficient ones: each whole row is an N_1-local weakly
# efficient set, and the metric is the local coverage error.
soln = [{(x1, 70) for x1 in range(51)}, {(x1, 20) for x1 in range(26)}]
