#!/usr/bin/env python
from statistics import mean, variance
from math import sqrt


class SimOptSolver(object):
    def __init__(self, orc, sprn=None, x0=None, paramargs=None):
        self.orc = orc
        self.x0 = x0
        self.sprn = sprn
        if paramargs:
            for p in paramargs:
                setattr(self, p[0], p[1])
        self.num_calls = 0
        self.num_obj = self.orc.num_obj
        self.dim = self.orc.dim
        super().__init__()


class OrcBase(object):
    def check_xfeas(self, x):
        """check if x is in the feasible domain"""
        is_feas = True
        qx = len(x)
        qo = self.dim
        if not qx == qo:
            return False
        mcD = self.get_feasspace()
        i = 0
        while i < len(mcD) and is_feas == True:
            comp_feas = False
            j = 0
            while j < len(mcD[i]) and comp_feas == False:
                if x[i] >= mcD[i][j][0] and x[i] < mcD[i][j][1]:
                    comp_feas = True
                j += 1
            if not comp_feas:
                is_feas = False
            i += 1
        return is_feas


class Oracle(OrcBase):
    def __init__(self, prn):
        self.prn = prn
        self.num_calls = 0
        self.set_crnflag(True)
        super().__init__()

    def set_crnflag(self, crnflag):
        """set the crnflag and intialize the states"""
        self.crnflag = crnflag
        self.crnold_state = self.prn.getstate()
        self.crnnew_state = self.prn.getstate()

    def set_crnold(self, old_state):
        """sets the first crn which we will rewind to"""
        self.crnold_state = old_state

    def set_crnnew(self, new_state):
        """set the crn we will use in the next Retrospective iteration"""
        self.crnnew_state = new_state

    def crn_reset(self):
        """rewind to the first crn"""
        crn_state = self.crnold_state
        self.prn.setstate(crn_state)

    def crn_advance(self):
        """jump ahead to the new crn, and set the new rewind point"""
        self.num_calls = 0
        crn_state = self.crnnew_state
        self.crnold_state = self.crnnew_state
        self.prn.setstate(crn_state)

    def crn_check(self, num_calls):
        """rewind the crn if crnflag is True and set latest CRN flag"""
        if num_calls > self.num_calls:
            self.num_calls = num_calls
            prnstate = self.prn.getstate()
            self.set_crnnew(prnstate)
        if self.crnflag:
            self.crn_reset()

    def hit(self, x, m):
        """return the mean of spending m simulation effort at point x"""
        is_feas = self.check_xfeas(x)
        d = self.num_obj
        res = {j: [] for j in range(d)}
        if is_feas and m > 0:
            omean = []
            ovar = []
            ose = []
            for i in range(m):
                xi = self.get_xi(self.prn)
                objd = self.g(x, xi)
                for j in range(d):
                    res[j].append(objd[j])
            if m > 1:
                for j in range(d):
                    omean.append(mean(res[j]))
                    ovar.append(variance(res[j], omean[j]))
                    ose.append(sqrt(ovar[j])/sqrt(m))
            if m == 1:
                for j in range(d):
                    omean.append(res[j][0])
                    ose.append(0)
            self.crn_check(m)
        else:
            omean = []
            ose = []
        return is_feas, tuple(omean), tuple(ose)


class DeterministicOrc(OrcBase):
    def hit(self, x, m):
        """return the deterministic objective value g(x)"""
        is_feas = self.check_xfeas(x)
        d = self.num_obj
        res = {j: [] for j in range(d)}
        if is_feas and m > 0:
            omean = []
            ovar = []
            ose = []
            objd = self.g(x)
            for j in range(d):
                res[j].append(objd[j])
            for j in range(d):
                omean.append(res[j][0])
                ose.append(0)
        else:
            omean = []
            ose = []
        return is_feas, tuple(omean), tuple(ose)
