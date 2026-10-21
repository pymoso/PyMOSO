#!/usr/bin/env python
"""
Summary
-------
Provide an implementation of R-Pe for users needing a 
bi-objective simulation optimization solver. 
"""
from ..chnbase import RASolver, _check_warm_start, _warn_if_beta_not_positive
from ..moso import get_biparetos


class RPE(RASolver):
    """
    R-Pe solver for bi-objective simulation optimization.
    
    Parameters
    ----------
    orc : chnbase.Oracle object
	kwargs : dict
	
	See also
	--------
	chnbase.RASolver
    """

    PARAMS = ('betaeps',)

    def __init__(self, orc, **kwargs):
        self.betaeps = kwargs.pop('betaeps', 0.5)
        super().__init__(orc, **kwargs)
        _warn_if_beta_not_positive('betaeps', self.betaeps)

    def spsolve(self, warm_start):
        """
        Set P-epsilon as the sample path solver. RASolvers require that 
        this function is implemented.
        
		Parameters
		----------
		warm_start : set of tuple of int
		
		Returns
		-------
		next_start : set of tuple of int
        """
        next_start = self.pe(warm_start)
        return next_start

    def pe(self, aold):
        """
        Generate candidate bi-objective LEPs using the P-Epsilon 
        algorithm.
        
        Parameters
        ----------
        aold : set of tuple of int
			The ALES of the previous iteration
			
		Returns
		-------
		phatp : set of tuple of int
			A candidate ALES
        """
        # x0 is a candidate in every iteration. Every point is estimated
        # at this iteration's sample size; none may have become infeasible
        aold = aold | {self.x0}
        self.upsample(aold)
        _check_warm_start(self, aold)
        mnumin = self.get_min(aold)
        aold, domset = self.remove_nlwep(aold)
        a0new = mnumin | aold
        tmp = {x: self.gbar[x] for x in mnumin | a0new}
        a1new = get_biparetos(tmp) | mnumin
        # print(' ------ iteration ', self.nu, ' -------')
        # for x in a1new:
        #     print(x, self.gbar[x])
        c0 = len(a1new)
        epslst = dict()
        ck = dict()
        Lk = dict()
        J = dict()
        HI = 1
        LO = 0
        krange = range(self.num_obj)
        for k in krange:
            kcon = 1 - k % 2
            sphat = sorted(a1new, key=lambda t: self.gbar[t][kcon])
            Lk[k] = self.gbar[sphat[0]][kcon] + self.fse(self.sehat[sphat[0]][kcon])
            mcJ = []
            for i in range(1, c0):
                low_b = self.gbar[sphat[i]][kcon] - self.fse(self.sehat[sphat[i]][kcon])
                hi_b = self.gbar[sphat[i]][kcon] + self.fse(self.sehat[sphat[i]][kcon])
                mcJ.append((low_b, hi_b))
            overlap = []
            for i1 in range(c0 - 1):
                is_inJ = False
                eps_c = mcJ[i1][LO]
                for j in mcJ:
                    low = j[LO]
                    hi = j[HI]
                    # check if eps_c in half open interval (low, hi]
                    if eps_c > low and eps_c <= hi:
                        is_inJ = True
                overlap.append(is_inJ)
            epslst[k] = [mcJ[i][LO] for i in range(c0 - 1) if mcJ[i][LO] > Lk[k] and not overlap[i]]
            ck[k] = len(epslst[k])
            J[k] = mcJ
        # the objective with the fewest epsilon values is minimized; ties
        # are broken randomly (docs/algorithm-audit.md, finding 7), with a
        # draw from the solver's stream only when there is a tie
        fewest = [k for k in krange if ck[k] == min(ck.values())]
        k_opt = fewest[0] if len(fewest) == 1 else fewest[int(self.sprn.random()*len(fewest))]
        k_con = 1 - k_opt % 2
        # the traceback's bounds are the intervals on the objective it
        # constrains, not the last pass's (docs/algorithm-audit.md, finding 1)
        mcJ = J[k_opt]
        L = Lk[k_opt]
        eps = sorted(epslst[k_opt])
        c = len(eps)
        mcAeps = set()
        if c > 0:
            for ep in eps:
                lmax = float('-inf')
                hi_blist = [mcJ[i][HI] for i in range(c0 - 1) if mcJ[i][HI] < ep]
                if hi_blist:
                    lmax = max(hi_blist)
                #print('minlst: ', hi_blist)
                epL = max(lmax, L)
                epnew = ep
                mcA = set()
                mcT = set()
                while epL < epnew:
                    # print('epL: ', epL)
                    # print('epnew: ', epnew)
                    #print('a1new: ', {x: self.gbar[x][k_con] for x in a1new})
                    stpts = {x: self.gbar[x] for x in a1new | mcT if self.gbar[x][k_con] <= epnew}
                    #print('starts: ', stpts)
                    tbx0 = min(stpts, key=lambda t: self.gbar[t][k_opt])
                    fxtb0 = self.gbar[tbx0]
                    #print('found: ', tbx0, fxtb0[k_con])
                    setbx0 = self.sehat[tbx0]
                    mcTp, xst, fxst, sexst = self.spline(tbx0, epnew, k_opt, k_con)
                    mcA |= {xst}
                    mcT |= mcTp
                    back_dist = self.fse(sexst[k_con])
                    if back_dist == 0.0:
                        back_dist = 0.000001
                    epnew = fxst[k_con] - back_dist
                mcAeps |= mcA
        tmp = {x: self.gbar[x] for x in mcAeps | a1new}
        phatp = get_biparetos(tmp)
        return phatp

    def fse(self, se):
        """
        Compute diminishing standard error function for an iteration.
        
        Parameters
        ----------
        se : float
			Standard error of an objective value
		
		Returns
		-------
		relax : float
        """
        m = self.m
        relax = se*pow(m, 0.5 - self.betaeps)
        return relax
