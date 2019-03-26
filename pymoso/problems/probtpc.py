#!/usr/bin/env python
"""
Summary
-------
Provides implementation of the Test Problem C Oracle for use in PyMOSO.
"""
from ..chnbase import Oracle
from math import exp, sqrt, sin


class ProbTPC(Oracle):
    """
    An Oracle that simulates Test Problem C.

    Attributes
    ----------
    num_obj : int, 2
    dim : int, 3
    density_factor : int, 2

    Parameters
    ----------
    rng : prng.MRG32k3a object

    See also
    --------
    chnbase.Oracle
    """

    def __init__(self, rng):
        self.num_obj = 2
        self.dim = 3
        self.density_factor = 2
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
        df = self.density_factor
        xr = range(-5*df, 5*df + 1)
        obj1 = None
        obj2 = None
        isfeas = True
        for xi in x:
            if not xi in xr:
                isfeas = False
        if isfeas:
            z1 = rng.normalvariate(0, 1)
            z2 = rng.normalvariate(0, 1)
            z3 = rng.normalvariate(0, 1)
            xi = (z1**2, z2**2, z3**2)
            x = tuple(i/df for i in x)
            s = [sin(i) for i in x]
            sum1 = [-10*xi[i]*exp(-0.2*sqrt(x[i]**2 + x[i+1]**2)) for i in [0, 1]]
            sum2 = [xi[i]*(pow(abs(x[i]), 0.8) + 5*pow(s[i], 3)) for i in [0, 1, 2]]
            obj1 = sum(sum1)
            obj2 = sum(sum2)
        return isfeas, (obj1, obj2)
