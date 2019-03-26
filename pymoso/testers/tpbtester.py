#!/usr/bin/env python
"""
Summary
-------
Provide the tester for Test Problem B
"""
from ..problems import probtpb
from math import exp
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
        The set of LES's which solve TPC locally
    get_ranx0 : function
    """
    def __init__(self):
        self.ranorc = probtpb.ProbTPB
        self.true_g = true_g
        self.soln = soln
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
        for les in self.soln:
            dist = dh(efrontier, les)
            distlist.append(dist)
        return min(distlist)


soln = [{(1.04, 1.85376768), (1.92, 0.3013068800000003), (0.12, 1.99997408), (0.04, 1.99999968), (1.52, 1.33275648), (0.28, 1.99923168), (1.32, 1.62050528), (0.16, 1.99991808), (1.44, 1.46252288), (1.28, 1.66445568), (1.68, 1.00425728), (0.48, 1.99336448), (0.88, 1.92503808), (1.6, 1.1807999999999998), (1.2, 1.7408000000000001), (1.16, 1.77367008), (0.08, 1.99999488), (1.36, 1.5723724799999999), (1.4, 1.5198), (1.0, 1.875), (1.56, 1.2596988799999997), (1.64, 1.0957564800000004), (1.24, 1.70447328), (0.2, 1.9998), (0.84, 1.93776608), (1.48, 1.40026848), (0.4, 1.9968), (0.92, 1.91045088), (0.32, 1.99868928), (1.8, 0.6878), (1.96, 0.15526368000000024), (1.76, 0.80060928), (1.84, 0.5672140799999998), (1.88, 0.43850208000000035), (1.72, 0.9059836800000001), (0.76, 1.95829728), (0.96, 1.89383168), (0.56, 1.98770688), (0.52, 1.99086048), (0.72, 1.96640768), (0.36, 1.99790048), (0.6, 1.9838), (0.8, 1.9488), (0.44, 1.99531488), (0.64, 1.97902848), (1.08, 1.82993888), (1.12, 1.80331008), (2.0, 0.0), (0.24, 1.99958528), (0.68, 1.97327328), (0.0, 2.0)}, {(0.16, 0.3675444679663241), (0.48, 0.16764170994243655), (0.64, 0.10557280900008414), (0.72, 0.0788441296806186), (0.08, 0.4681704103055011), (0.4, 0.20472927123294937), (0.12, 0.4114338087234576), (0.68, 0.09191348147682965), (0.36, 0.2254033307585166), (0.8, 0.05425839099682417), (0.6, 0.11988826320660662), (0.92, 0.020629638664440675), (0.56, 0.13493845458557785), (0.76, 0.06630851524278392), (0.96, 0.01015359923204695), (0.88, 0.03145307188309876), (0.28, 0.27257284748717403), (0.2, 0.331259695023578), (1.0, 0.0), (0.0, 1.0), (0.32, 0.24787938138272125), (0.24, 0.30007289768388334), (0.52, 0.15081789050122008), (0.04, 0.5527864045000421), (0.44, 0.18555236014150056), (0.84, 0.04265202826184045)}]
