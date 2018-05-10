#!/usr/bin/env python
from .simbase import Oracle, DeterministicOrc
from itertools import product
from math import pow, sqrt, pi, exp, fabs, sin


class TP1a(Oracle):
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

    def g(self, x, xi):
        obj2 = pow(x[0], 2)/100.0 + pow(x[1]/10.0 - 2.0*xi[2], 2)
        obj1 = pow(x[0]/10.0 - 2.0*xi[0], 2) + pow(x[1]/10.0 - xi[1], 2)
        return obj1, obj2

    def get_xi(self, prn):
        z1 = prn.normalvariate(0, 1)
        z2 = prn.normalvariate(0, 1)
        z3 = prn.normalvariate(0, 1)
        xi0 = pow(z1, 2)
        xi1 = pow(z2, 2)
        xi2 = pow(z2, 2)
        return xi0, xi1, xi2


class TP1b(TP1a):
    def get_xi(self, prn):
        z1 = prn.normalvariate(0, 1)
        z2 = prn.normalvariate(0, 1)
        z3 = prn.normalvariate(0, 1)
        xi0 = sqrt(pow(z1, 2))
        xi1 = sqrt(pow(z2, 2))
        xi2 = sqrt(pow(z2, 2))
        return xi0, xi1, xi2


class TrueTP1a(DeterministicOrc):
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


class TrueTP1b(TrueTP1a):
    def g(self, x):
        chimean = sqrt(2)/sqrt(pi)
        obj1 = (x[0]**2)/100 - 4*x[0]*chimean/10 + 4*chimean**2 + (x[1]**2)/100 - 2*x[1]*chimean/10 + chimean**2
        obj2 = (x[0]**2)/100 + (x[1]**2)/100 - 4*x[1]*chimean/10 + 4*(chimean**2)
        return obj1, obj2


class TP2(Oracle):
    def __init__(self, prn):
        self.num_obj = 2
        self.dim = 3
        super().__init__(prn)

    def get_feasspace(self):
        dim = self.dim
        mcD = dict()
        for i in range(dim):
            mcD[i] = [(-25, 26)]
        return mcD

    def get_xi(self, prn):
        z1 = prn.normalvariate(0, 1)
        z2 = prn.normalvariate(0, 1)
        z3 = prn.normalvariate(0, 1)
        xi0 = pow(z1, 2)
        xi1 = pow(z2, 2)
        xi2 = pow(z2, 2)
        return xi0, xi1, xi2

    def g(self, x, xi):
        adjx = tuple(i/5 for i in x)
        sum1 = [-10*xi[i]*exp(-0.2*sqrt(x[i]**2 + x[i+1]**2)) for i in [0, 1]]
        sum2 = [xi[i]*(pow(fabs(x[i]), 0.8) + 5*pow(sin(x[i]), 3)) for i in [0, 1, 2]]
        obj1 = sum(sum1)
        obj2 = sum(sum2)
        return obj1, obj2


class TP2LowVar(TP2):
    def get_xi(self, prn):
        z1 = prn.normalvariate(0, 1)
        z2 = prn.normalvariate(0, 1)
        z3 = prn.normalvariate(0, 1)
        xi0 = sqrt(pow(z1, 2))
        xi1 = sqrt(pow(z2, 2))
        xi2 = sqrt(pow(z2, 2))
        return xi0, xi1, xi2


class TrueTP2(DeterministicOrc):
    def __init__(self):
        self.num_obj = 2
        self.dim = 3
        super().__init__()

    def get_feasspace(self):
        dim = self.dim
        mcD = dict()
        for i in range(dim):
            mcD[i] = [(-25, 26)]
        return mcD

    def g(self, x):
        x = tuple(i/5 for i in x)
        chisquare = 1
        sum1 = [-10*chisquare*exp(-0.2*sqrt(x[i]**2 + x[i+1]**2)) for i in [0, 1]]
        sum2 = [chisquare*(pow(fabs(x[i]), 0.8) + 5*pow(sin(x[i]), 3)) for i in [0, 1, 2]]
        obj1 = sum(sum1)
        obj2 = sum(sum2)
        return obj1, obj2


class TrueTP2LowVar(TrueTP2):
    def g(self, x):
        x = tuple(i/5 for i in x)
        chimean = sqrt(2)/sqrt(pi)
        sum1 = [-10*chimean*exp(-0.2*sqrt(x[i]**2 + x[i+1]**2)) for i in [0, 1]]
        sum2 = [chimean*(pow(fabs(x[i]), 0.8) + 5*pow(sin(x[i]), 3)) for i in [0, 1, 2]]
        obj1 = sum(sum1)
        obj2 = sum(sum2)
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
        xi0 = pow(z1, 2)
        xi1 = pow(z2, 2)
        return xi0, xi1


class TP3LowVar(TP3):
    def get_xi(self, prn):
        z1 = prn.normalvariate(0, 1)
        z2 = prn.normalvariate(0, 1)
        xi0 = sqrt(pow(z1, 2))
        xi1 = sqrt(pow(z2, 2))
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
