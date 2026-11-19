#!/usr/bin/env python
"""
Summary
-------
Provide the tester for Test Problem B
"""
from ..problems import probtpa
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
    chi2mean = 1
    chi2mean2 = 3
    obj1 = (x[0]**2)/100 - 4*x[0]/10 + (x[1]**2)/100 - 2*x[1]/10 + 15
    obj2 = (x[0]**2)/100 + (x[1]**2)/100 - 4*x[1]/10 + 12
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
    xr = range(0, 51)
    x1 = rng.choice(xr)
    x2 = rng.choice(xr)
    x0 = (x1, x2)
    return x0


class TPATester(object):
    """
    Store useful data for working with Test Problem A.

    Attributes
    ----------
    ranorc : chnbase.Oracle class
    true_g : function
    soln : set of tuple of int
        The global efficient set, as decision points
    soln_images : list of tuple of float
        true_g of each point of soln, computed when the tester is made
    get_ranx0 : function
    """
    def __init__(self):
        self.ranorc = probtpa.ProbTPA
        self.true_g = true_g
        self.soln = soln
        self.soln_images = [self.true_g(x) for x in soln]
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
        efrontier = []
        for point in eles:
            objs = self.true_g(point)
            efrontier.append(objs)
        haus = dh(efrontier, self.soln_images)
        return haus


# The global efficient set, as decision points. 100 * true_g is an
# integer polynomial -- squared distances to (20, 10) and (0, 20), plus
# constants -- so this set is checked exactly, in integer arithmetic, by
# tests/test_tester_reference_sets.py. It is (0, 20), (20, 10), and the
# band around the segment between the centres: x2 in {19, 20, 21} - x1/2
# for even x1 in 2..18, x2 in {20 - (x1+1)/2, 20 - (x1-1)/2} for odd x1.
# Before 2.0 soln held these points' images, computed by code no longer
# in the repository; 11 of them differed from true_g in the last bit, so
# full coverage measured about 2e-15 instead of 0.
soln = {
    (0, 20), (1, 19), (1, 20), (2, 18), (2, 19), (2, 20), (3, 18),
    (3, 19), (4, 17), (4, 18), (4, 19), (5, 17), (5, 18), (6, 16),
    (6, 17), (6, 18), (7, 16), (7, 17), (8, 15), (8, 16), (8, 17),
    (9, 15), (9, 16), (10, 14), (10, 15), (10, 16), (11, 14), (11, 15),
    (12, 13), (12, 14), (12, 15), (13, 13), (13, 14), (14, 12), (14, 13),
    (14, 14), (15, 12), (15, 13), (16, 11), (16, 12), (16, 13), (17, 11),
    (17, 12), (18, 10), (18, 11), (18, 12), (19, 10), (19, 11), (20, 10),
}
