#!/usr/bin/env python
"""Provide base classes for problem and solver implementations."""

import numpy as np


class SimOptSolver(object):
    """Base class for solver implentations."""

    def __init__(self, orc, **kwargs):
        """Initialize a solver object by assigning an oracle problem."""
        self.orc = orc
        # yeah...  ¯\_(ツ)_/¯
        for p in kwargs:
            setattr(self, p, kwargs[p])
        self.num_calls = 0
        self.num_obj = self.orc.num_obj
        self.dim = self.orc.dim
        super().__init__()


class OrcBase(object):
    """Base class for problem implementations."""

    def check_xfeas(self, x):
        """Check if x is in the feasible domain."""
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
    """Base class for implementing problems with noise."""

    def __init__(self, prn):
        """Initialize a problem with noise with a pseudo-random generator."""
        self.prn = prn
        self.num_calls = 0
        self.set_crnflag(True)
        super().__init__()

    def set_crnflag(self, crnflag):
        """Set the common random number (crn) flag and intialize the crn states."""
        self.crnflag = crnflag
        self.crnold_state = self.prn.getstate()
        self.crnnew_state = self.prn.getstate()

    def set_crnold(self, old_state):
        """Set the current crn rewind state."""
        self.crnold_state = old_state

    def set_crnnew(self, new_state):
        """Jump forward to start a new realization of crn."""
        self.crnnew_state = new_state

    def crn_reset(self):
        """Rewind to the first crn."""
        crn_state = self.crnold_state
        self.prn.setstate(crn_state)

    def crn_advance(self):
        """Jump ahead to the new crn, and set the new rewind point."""
        self.num_calls = 0
        crn_state = self.crnnew_state
        self.crnold_state = self.crnnew_state
        self.prn.setstate(crn_state)

    def crn_check(self, num_calls):
        """Rewind the crn if crnflag is True and set latest CRN flag."""
        if num_calls > self.num_calls:
            self.num_calls = num_calls
            prnstate = self.prn.getstate()
            self.set_crnnew(prnstate)
        if self.crnflag:
            self.crn_reset()

    def old_stuf(self, x, m):
        """Generate the mean of spending m simulation effort at point x."""
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

        def hit(self, x, m):
            """Generate the mean of spending m simulation effort at point x.

            Positional Arguments:
            x -- point to generate estimates
            m -- number of estimates to generate at x

            Return Values:
            isfeas -- boolean indicating feasibility of x
            omean -- mean of m estimates of each objective at x (tuple)
            ose -- mean of m estimates of the standard error of each objective
                at x (tuple)
            """
            is_feas = self.check_xfeas(x)
            d = self.num_obj
            if is_feas and m > 0:
                if m == 1:
                    xi = self.get_xi(self.prn)
                    objd = self.g(x, xi)
                    omean = objd
                    ose = [0 for o in objd]
                else:
                    objm = []
                    for i in range(m):
                        xi = self.get_xi(self.prn)
                        objd = self.g(x, xi)
                        objm.append(objd)
                    objv = np.array(objm)
                    print(objm)
                self.crn_check(m)
            else:
                omean = []
                ose = []
            return is_feas, tuple(omean), tuple(ose)


class DeterministicOrc(OrcBase):
    """Base class for implementing deterministic problems."""

    def hit(self, x, m=1):
        """Generate the deterministic objective values g(x).

        Positional Arguments:
        x -- point to generate estimates
        m -- number of estimates to generate at x. Anything greater than 0 is
            identical for deterministic problems

        Return Values:
        isfeas -- boolean indicating feasibility of x
        omean -- g(x) (tuple of lenth self.num_obj)
        ose -- 0 (tuple of lenth self.num_obj)
        """
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
