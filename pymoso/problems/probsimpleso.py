#!/usr/bin/env python
"""
Summary
-------
Provides implementation of the Test Simple SO Problem
Oracle for use in PyMOSO.
"""
from ..chnbase import Oracle


class ProbSimpleSO(Oracle):
    """
    An Oracle that simulates the Test Simple SO problem.

    Attributes
    ----------
    num_obj : int, 1
    dim : int, 1

    Parameters
    ----------
    rng : prng.MRG32k3a object

    See also
    --------
    chnbase.Oracle
    """
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
            z1 = rng.normalvariate(0, 3)
            obj1 = x[0]**2 + z1
        return isfeas, (obj1, )
