#!/usr/bin/env python
"""
Summary
-------
Provide the tester for Test Problem B
"""
from ..problems import probtpa
from ..chnutils import dh


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
    soln : list of set of tuple of int
        The set of LES's which solve TPC locally
    get_ranx0 : function
    """
    def __init__(self):
        self.ranorc = probtpa.ProbTPA
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
        efrontier = []
        for point in eles:
            objs = self.true_g(point)
            efrontier.append(objs)
        haus = dh(efrontier, self.soln)
        return haus


soln = {(10.34, 10.74), (10.58, 10.18), (13.88, 8.08), (15.0, 8.0), (13.200000000000001, 8.2), (10.45, 10.45), (11.25, 9.25), (12.05, 8.649999999999999), (10.969999999999999, 9.57), (12.450000000000001, 8.45), (10.02, 12.42), (14.61, 8.01), (10.29, 10.89), (14.05, 8.05), (10.079999999999998, 11.879999999999999), (13.370000000000001, 8.17), (11.46, 9.06), (10.73, 9.93), (10.100000000000001, 11.7), (12.89, 8.29), (10.52, 10.32), (10.01, 12.61), (11.8, 8.8), (11.69, 8.89), (10.25, 11.05), (10.170000000000002, 11.37), (12.600000000000001, 8.4), (10.8, 9.8), (12.74, 8.34), (14.24, 8.04), (10.0, 13.0), (11.57, 8.969999999999999), (14.419999999999998, 8.02), (13.7, 8.1), (11.93, 8.73), (10.2, 11.2), (10.04, 12.24), (10.89, 9.69), (10.649999999999999, 10.05), (11.36, 9.16), (13.05, 8.25), (10.399999999999999, 10.6), (13.530000000000001, 8.129999999999999), (11.16, 9.36), (10.129999999999999, 11.530000000000001), (12.180000000000001, 8.58), (11.059999999999999, 9.46), (10.05, 12.05), (12.32, 8.52)}
