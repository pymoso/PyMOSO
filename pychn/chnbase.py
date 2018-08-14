#!/usr/bin/env python
"""Provide base classes for problem and solver implementations."""
from statistics import mean, variance
from math import sqrt
from .prng.mrg32k3a import get_next_prnstream
import multiprocessing as mp
from copy import deepcopy


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
        self.simpar = 1
        self.num_rand = 0
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
        """Rewind the prn if crnflag is True and set farthest CRN point."""
        if num_calls > self.num_calls:
            self.num_calls = num_calls
            prnstate = self.prn.getstate()
            self.set_crnnew(prnstate)
        if self.crnflag:
            self.crn_reset()

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
        d = self.num_obj
        dr = range(d)
        isfeas = False
        obmean = []
        obse = []
        mr = range(m)
        if m > 0:
            if m == 1:
                isfeas, objd = self.g(x, self.prn)
                obmean = objd
                obse = [0 for o in objd]
            else:
                if self.simpar == 1:
                    ## do not parallelize replications
                    feas = []
                    objm = []
                    for i in mr:
                        isfeas, objd = self.g(x, self.prn)
                        feas.append(isfeas)
                        objm.append(objd)
                    if all(feas):
                        isfeas = True
                        obmean = tuple([mean([objm[i][k] for i in mr]) for k in dr])
                        obvar = [variance([objm[i][k] for i in mr], obmean[k]) for k in dr]
                        obse = tuple([sqrt(obvar[i]/m) for i in dr])
                else:
                    sim_old = self.simpar
                    ## obtain replications in parallel
                    ## divide m into chunks for the processors
                    nproc = self.simpar
                    if self.simpar > m:
                        nproc = m
                    pr = range(nproc)
                    num_rands = [int(m/nproc) for i in pr]
                    for i in range(m % nproc):
                        num_rands[i] += 1
                    ## create prn for each process by jumping ahead 2^127 spots
                    ## and a hit function for each using an oracle object
                    start_seed = self.prn.get_seed()
                    ## turn off simpar during parallelization
                    self.simpar = 1
                    orclst = [self]
                    for i in range(len(num_rands) - 1):
                        nextprn = get_next_prnstream(start_seed)
                        start_seed = nextprn.get_seed()
                        myorc = deepcopy(self)
                        myorc.prn = nextprn
                        orclst.append(myorc)
                    ## take the replications in parallel
                    pres = []
                    feas = []
                    means = []
                    ses = []
                    with mp.Pool(nproc) as p:
                        for i, r in enumerate(num_rands):
                            pres.append(p.apply_async(orclst[i].hit, args=(x, r)))
                        for i in pr:
                            ## 0 = feas, 1 = mean, 2 = se
                            res = pres[i].get()
                            feas.append(res[0])
                            means.append(res[1])
                            ses.append(res[2])
                    ## turn simpar back on before returning
                    self.simpar = sim_old
                    if all(feas):
                        isfeas = True
                        ## weighted average of replications
                        obmean = tuple([sum([means[i][k]*num_rands[i]/m for i in pr]) for k in dr])
                        ### convert se output back to variance
                        obvar = [[num_rands[i]*ses[i][k]**2 for k in dr] for i in pr]
                        ### compute pooled variance
                        ##### special case 1 :(
                        if m == nproc:
                            pvar = [variance([means[i][k] for i in pr], obmean[k]) for k in dr]
                        else:
                            pvar = [sum([obvar[i][k]*(num_rands[i] - 1) for i in pr])/(m - nproc) for k in dr]
                        ### compute standard error
                        obse = tuple([sqrt(pvar[k]/m) for k in dr])
            self.crn_check(m)
        return isfeas, obmean, obse


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
        d = self.num_obj
        isfeas = False
        objd = []
        ose = []
        if m > 0:
            isfeas, objd = self.g(x)
            ose = tuple([0 for o in objd])
        return isfeas, objd, ose
