#!/usr/bin/env python
from ..chnbase import DeterministicOrc
import math


class ProbTrueTPB(DeterministicOrc):
    def __init__(self):
        self.num_obj = 2
        self.dim = 2
        super().__init__()

    def get_feasspace(self):
        dim = self.dim
        mcD = dict()
        for i in range(dim):
            mcD[i] = [(0, 101)]
        return mcD

    def g(self, x):
        g1 = 4*x[0]/100
        if x[1] >= 0 and x[1] <= 40:
            f2 = 4 - 3*math.exp(-math.pow((x[1]-20)/2, 2))
        else:
            f2 = 4 - 2*math.exp(-math.pow((x[1]-70)/20, 2))
        alpha = 0.25 + 3.75*(f2 - 1)
        if g1 <= f2:
            h = 1 - math.pow(g1/f2, alpha)
        else:
            h = 0
        obj1 = g1
        obj2 = f2*h
        return obj1, obj2
