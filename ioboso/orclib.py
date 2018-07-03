#!/usr/bin/env python
from .simbase import Oracle, DeterministicOrc
from itertools import product
from math import pow, sqrt, pi, exp, fabs, sin


class TP1(Oracle):
    def __init__(self, prn):
        self.num_obj = 2
        self.dim = 2
        super().__init__(prn)

    def get_feasspace(self):
        dim = self.dim
        mcD = dict()
        for i in range(dim):
            mcD[i] = [(0, 51)]
        return mcD

    def get_xi(self, prn):
        z1 = prn.normalvariate(0, 1)
        z2 = prn.normalvariate(0, 1)
        z3 = prn.normalvariate(0, 1)
        xi0 = math.pow(z1, 2)
        xi1 = math.pow(z2, 2)
        xi2 = math.pow(z3, 2)
        return xi0, xi1, xi2

    def g(self, x, xi):
        obj2 = math.pow(x[0], 2)/100.0 + math.pow(x[1]/10.0 - 2.0*xi[2], 2)
        obj1 = math.pow(x[0]/10.0 - 2.0*xi[0], 2) + math.pow(x[1]/10.0 - xi[1], 2)
        return obj1, obj2


class TrueTP1(DeterministicOrc):
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


class TPCi(Oracle):
    def __init__(self, prn):
        self.num_obj = 2
        self.dim = 3
        self.density_factor = 2
        super().__init__(prn)

    def get_feasspace(self):
        dim = self.dim
        df = self.density_factor
        mcD = dict()
        for i in range(dim):
            mcD[i] = [(-5*df, 5*df + 1)]
        return mcD

    def get_xi(self, prn):
        z1 = prn.normalvariate(0, 1)
        z2 = prn.normalvariate(0, 1)
        z3 = prn.normalvariate(0, 1)
        z4 = prn.normalvariate(0, 1)
        z5 = prn.normalvariate(0, 1)
        xi0 = math.pow(z1, 2)
        xi1 = math.pow(z2, 2)
        xi2 = math.pow(z3, 2)
        return xi0, xi1, xi2

    def g(self, x, xi):
        df = self.density_factor
        x = tuple(i/df for i in x)
        s = [sin(i) for i in x]
        sum1 = [-10*xi[i]*exp(-0.2*sqrt(x[i]**2 + x[i+1]**2)) for i in [0, 1]]
        sum2 = [xi[i]*(math.pow(fabs(x[i]), 0.8) + 5*math.pow(s[i], 3)) for i in [0, 1, 2]]
        obj1 = fsum(sum1)
        obj2 = fsum(sum2)
        return obj1, obj2


class TrueTPCi(DeterministicOrc):
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
        s = [sin(i) for i in x]
        chisquare = 1.0
        sum1 = [-10*chisquare*exp(-0.2*sqrt(x[i]**2 + x[i+1]**2)) for i in [0, 1]]
        sum2 = [chisquare*(math.pow(fabs(x[i]), 0.8) + 5*math.pow(s[i], 3)) for i in [0, 1, 2]]
        obj1 = fsum(sum1)
        obj2 = fsum(sum2)
        return obj1, obj2


class TP3(Oracle):
    def __init__(self, prn):
        self.num_obj = 2
        self.dim = 2
        super().__init__(prn)

    def get_feasspace(self):
        dim = self.dim
        mcD = dict()
        for i in range(dim):
            mcD[i] = [(0, 101)]
        return mcD

    def g(self, x, xi):
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
        obj2 = xi[0]*g1
        obj1 = xi[0]*xi[1]*f2*h
        return obj1, obj2

    def get_xi(self, prn):
        z1 = prn.normalvariate(0, 1)
        z2 = prn.normalvariate(0, 1)
        xi0 = math.pow(z1, 2)
        xi1 = math.pow(z2, 2)
        return xi0, xi1


class TrueTP3(DeterministicOrc):
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


class TPBi(TP3):
    def get_xi(self, prn):
        z1 = prn.normalvariate(0, 1)
        z2 = prn.normalvariate(0, 1)
        z3 = prn.normalvariate(0, 1)
        xi0 = math.pow(z1, 2)
        xi1 = math.pow(z2, 2)
        xi2 = math.pow(z3, 2)
        return xi0, xi1, xi2

    def g(self, x, xi):
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
        obj2 = xi[0]*g1
        obj1 = xi[1]*xi[2]*f2*h
        return obj1, obj2
