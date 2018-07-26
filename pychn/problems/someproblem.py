#!/usr/bin/env python
from pychn.chnbase import Oracle
import numpy as np

class SomeProblem(Oracle):
    """Example problem to help implement your problems in pychn."""

    def __init__(self, prn):
        """Initialize SomeProblem with a prn object.

        Also set the dimensionality of the feasible space and the number
        of objectives. Depending on the algorithm you're using, you can also
        set the common random number flag.
        """
        self.num_obj = 2
        self.dim = 2
        self.crnflag = False
        super().__init__(prn)

    def get_feasspace(self):
        """Provide a representation of the feasible domain."""
        ## todo -- make a better way
        dim = self.dim
        mcD = dict()
        for i in range(dim):
            mcD[i] = [(0, 51)]
        return mcD

    def get_xi(self, prn):
        """Realize random variables used to estimate g(x).

        If your implementation of g is a wrapper to a C library or something
        that handles randomness on its own, get_xi can return an empty list or
        None or anything. Just don't use the result in g.
        """
        z1 = prn.normalvariate(0, 1)
        z2 = prn.normalvariate(0, 1)
        z3 = prn.normalvariate(0, 1)
        z = np.array([z1, z2, z3])
        xi = np.power(z, 2)
        return xi

    def g(self, x, xi):
        """Estimate g(x) given randomness xi."""
        obj1 = (x[0]/10.0 - 2.0*xi[0])**2 + (x[1]/10.0 - xi[1])**2
        obj2 = (x[0]**2)/100.0 + (x[1]/10.0 - 2.0*xi[2])**2
        return obj1, obj2


def main():
    from pychn.prng import mrg32k3a
    prn = mrg32k3a.MRG32k3a()
    orc = SomeProblem(prn)
    orc.set_crnflag(False)
    x0 = (20, 20)
    for i in range(10):
        gx = orc.hit(x0, 3)
        print(gx)
        
if __name__ == '__main__':
    main()
