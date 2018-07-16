#!/usr/bin/env python
from ioboso.chnbase import DeterministicOrc
import math


class ProbTrueTPC(DeterministicOrc):
    def __init__(self):
        self.num_obj = 2
        self.dim = 3
        self.density_factor = 2
        super().__init__()

    def get_feasspace(self):
        dim = self.dim
        df = self.density_factor
        mcD = dict()
        for i in range(dim):
            mcD[i] = [(-5*df, 5*df + 1)]
        return mcD

    def g(self, x):
        df = self.density_factor
        x = tuple(i/df for i in x)
        s = [math.sin(i) for i in x]
        chisquare = 1.0
        sum1 = [-10*chisquare*math.exp(-0.2*math.sqrt(x[i]**2 + x[i+1]**2)) for i in [0, 1]]
        sum2 = [chisquare*(math.pow(math.fabs(x[i]), 0.8) + 5*math.pow(s[i], 3)) for i in [0, 1, 2]]
        obj1 = math.fsum(sum1)
        obj2 = math.fsum(sum2)
        return obj1, obj2
