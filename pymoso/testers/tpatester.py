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
    obj1 = (x[0]**2)/100 - 4*x[0]*chi2mean/10 + 4*chi2mean**2 + (x[1]**2)/100 - 2*x[1]*chi2mean/10 + chi2mean**2
    obj2 = (x[0]**2)/100 + (x[1]**2)/100 - 4*x[1]*chi2mean/10 + 4*(chi2mean**2)
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


soln = {(0.33999999999999986, 2.7399999999999998), (0.5799999999999996, 2.1799999999999997), (3.8800000000000003, 0.08000000000000007), (5.0, 0.0), (3.1999999999999997, 0.20000000000000018), (0.4500000000000002, 2.4499999999999997), (1.25, 1.25), (2.05, 0.6499999999999995), (0.9699999999999998, 1.5700000000000003), (2.4499999999999997, 0.4500000000000002), (0.020000000000000018, 4.42), (4.609999999999999, 0.009999999999999787), (0.29000000000000004, 2.89), (4.05, 0.050000000000000266), (0.08000000000000007, 3.88), (3.37, 0.17000000000000037), (1.46, 1.06), (0.73, 1.9299999999999997), (0.10000000000000009, 3.6999999999999993), (2.89, 0.29000000000000004), (0.5200000000000005, 2.3200000000000003), (0.010000000000000231, 4.609999999999999), (1.7999999999999998, 0.7999999999999998), (1.69, 0.8900000000000001), (0.24999999999999956, 3.05), (0.16999999999999948, 3.3699999999999997), (2.6, 0.3999999999999999), (0.8000000000000003, 1.8000000000000003), (2.7400000000000007, 0.3400000000000003), (4.24, 0.040000000000000036), (0.0, 5.0), (1.5699999999999998, 0.9699999999999998), (4.42, 0.020000000000000018), (3.7, 0.10000000000000009), (1.9300000000000002, 0.7300000000000004), (0.19999999999999973, 3.2), (0.040000000000000036, 4.24), (0.8900000000000001, 1.69), (0.6499999999999999, 2.0500000000000003), (1.3599999999999999, 1.1599999999999997), (3.0499999999999994, 0.25000000000000044), (0.009999999999999787, 4.81), (0.40000000000000036, 2.6), (3.5300000000000007, 0.1299999999999999), (1.1600000000000001, 1.3600000000000003), (0.13000000000000034, 3.5300000000000002), (2.18, 0.5800000000000001), (1.0599999999999996, 1.46), (0.04999999999999982, 4.05), (2.3199999999999994, 0.5199999999999996)}
