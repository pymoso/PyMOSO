#!/usr/bin/env python
from ..chnbase import DeterministicOrc


class ProbTrueTPA(DeterministicOrc):
    """Deterministic Test Problem A"""
    def __init__(self):
        self.num_obj = 2
        self.dim = 2
        super().__init__()

    def get_feasspace(self):
        dim = self.dim
        mcD = dict()
        for i in range(dim):
            mcD[i] = [(0, 51)]
        return mcD

    def g(self, x):
        chi2mean = 1
        obj1 = (x[0]**2)/100 - 4*x[0]*chi2mean/10 + 4*chi2mean**2 + (x[1]**2)/100 - 2*x[1]*chi2mean/10 + chi2mean**2
        obj2 = (x[0]**2)/100 + (x[1]**2)/100 - 4*x[1]*chi2mean/10 + 4*(chi2mean**2)
        return obj1, obj2
