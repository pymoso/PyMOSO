#!/usr/bin/env python
from ..chnbase import SimOptSolver
from ..chnutils import *
from math import pow, ceil, floor


class RPERLE(SimOptSolver):
    """For bi-objective simulation optimization on integer lattices"""

    def __init__(self, orc, **kwargs):
        if 'betaeps' not in kwargs:
            self.betaeps = 0.5
        if 'betadel' not in kwargs:
            self.betadel = 0.5
        if 'nbor_rad' not in kwargs:
            self.nbor_rad = 1
        sprn = kwargs.get('sprn', None)
        x0 = kwargs.get('x0', None)
        if not sprn or not x0:
            # we need both. Fail ungracefully for now.
            pass
        super().__init__(orc, **kwargs)

    def solve(self, budget):
        """initialize and invoke the rperle algorithm"""
        # R-PERLE benefits from CRN
        self.orc.set_crnflag(True)
        seed1 = self.orc.prn._current_seed
        # initialize output data objects
        self.crawl_ptsnu = dict()
        self.tb_ptsnu = dict()
        self.crwl_cnt = dict()
        self.spli_bind = dict()
        self.num_splines = dict()
        self.num_splines[0] = 0
        self.num_grad = dict()
        self.num_grad[0] = 0
        self.rle_bind = dict()
        self.rle_bind[0] = 0
        self.kstar = dict()
        self.kstar[0] = 0
        self.epsilons = dict()
        self.epsilons[0] = set()
        phatnu = dict()
        simcalls = dict()
        phatnu[0] = set() | {self.x0}
        simcalls[0] = 0
        # initialize the iteration counter
        self.nu = 0
        # invoke R-PERLE
        self.rperle(phatnu, simcalls, budget)
        # name the data keys and return the results
        datanames = ('phat', 'simcalls', 'crpts', 'tb_pts', 'crwl_cnt', 'num_spli_bind', 'num_splines', 'num_grad', 'num_rle_bind', 'epsilons', 'runseed', 'kstar')
        datad = (phatnu, simcalls, self.crawl_ptsnu, self.tb_ptsnu, self.crwl_cnt, self.spli_bind, self.num_splines, self.num_grad, self.rle_bind, self.epsilons, seed1, self.kstar)
        zipdata = zip(datanames, datad)
        outdata = dict(zipdata)
        return outdata

    def rperle(self, phatnu, simcalls, budget):
        """return a LES, see Cooper, Hunter, Nagaraj 2017"""
        while self.num_calls < budget:
            self.nu += 1
            self.spli_bind[self.nu] = 0
            self.rle_bind[self.nu] = 0
            self.num_splines[self.nu] = 0
            self.num_grad[self.nu] = 0
            self.m = self.calc_m(self.nu)
            self.b = self.calc_b(self.nu)
            self.gbar = dict()
            self.sehat = dict()
            aold = phatnu[self.nu - 1]
            phatnu[self.nu], _, _ = self.perle(aold)
            simcalls[self.nu] = self.num_calls
            self.orc.crn_advance()

    def perle(self, aold):
        """return an LWEP at a particular sample size m """
        a1 = self.pe(aold)
        anew = self.rle(a1)
        return anew, self.gbar, self.sehat

    def upsample(self, mcS):
        """sample a set at the current sample size"""
        outset = set()
        for s in mcS:
            isfeas, fs, ses = self.estimate(s)
            if isfeas:
                outset |= {s}
        return outset

    def get_min(self, mcS):
        """return a minimum for every objective using spline"""
        self.upsample(mcS)
        unconst = float('inf')
        kcon = 0
        xmin = set()
        krange = range(self.num_obj)
        for k in krange:
            kmin = min(mcS, key=lambda t: self.gbar[t][k])
            _, xmink, _, _ = self.spline(kmin, self.gbar[kmin], self.sehat[kmin], unconst, k, kcon)
            xmin |= {xmink}
        return xmin

    def remove_nlwep(self, mcS):
        """return subset of mcS which are LWEP"""
        r = self.nbor_rad
        lwepset = set()
        domset = set()
        delz = [0]*self.num_obj
        nbors = get_setnbors(mcS, r)
        nbors = self.upsample(nbors)
        tmpd = {x: self.gbar[x] for x in mcS | nbors}
        for s in mcS:
            islwep, dompts = is_lwep(s, r, tmpd)
            if islwep:
                lwepset |= {s}
            else:
                domset |= dompts
        return lwepset, domset

    def pe(self, aold):
        """return the solutions to a sequence of epsilon-constraint problems"""
        aold = self.upsample(aold | {self.x0})
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
        k_opt = min(ck, key=lambda k: ck[k])
        k_con = 1 - k_opt % 2
        L = Lk[k_opt]
        self.kstar[self.nu] = k_con
        eps = sorted(epslst[k_opt])
        self.epsilons[self.nu] = set(eps)
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
                    mcTp, xst, fxst, sexst = self.spline(tbx0, fxtb0, setbx0, epnew, k_opt, k_con)
                    mcA |= {xst}
                    mcT |= mcTp
                    back_dist = self.fse(sexst[k_con])
                    if back_dist == 0.0:
                        back_dist = 0.000001
                    epnew = fxst[k_con] - back_dist
                mcAeps |= mcA
        self.tb_ptsnu[self.nu] = mcAeps
        tmp = {x: self.gbar[x] for x in mcAeps | a1new}
        phatp = get_biparetos(tmp)
        return phatp

    def rle(self, mcS):
        """return a complete LWES"""
        mcXw = {self.x0}
        mcS = self.upsample(mcS | mcXw)
        b = self.b
        n = 0
        tmp = {s: self.gbar[s] for s in mcS | mcXw}
        mcS = get_biparetos(tmp)
        self.crawl_ptsnu[self.nu] = set()
        mcNnc = self.get_ncn(mcS)
        self.crwl_cnt[self.nu] = 0
        while n <= b and mcNnc:
            self.crwl_cnt[self.nu] += 1
            old_calls = self.num_calls
            mcNw, mcNd = self.remove_nlwep(mcNnc)
            mcNd -= mcS
            rlwepcalls = self.num_calls - old_calls
            mcS |= mcNw
            if not mcNw:
                mcXw = self.seek_lwep(mcNd, mcS)
                mcS |= mcXw
            tmp = {s: self.gbar[s] for s in mcS | {self.x0}}
            mcS = get_biparetos(tmp)
            old_calls = self.num_calls
            mcNnc = self.get_ncn(mcS)
            self.crawl_ptsnu[self.nu] |= mcNw | mcXw
            ncncalls = self.num_calls - old_calls
            n += rlwepcalls + ncncalls
        if n > b:
            self.rle_bind[self.nu] += 1
        return mcS

    def seek_lwep(self, mcNd, mcS):
        b = self.b
        n = 0
        delz = [0]*self.num_obj
        mcXw = set()
        xnew = set() | mcNd
        while not mcXw and n <= b:
            old_calls = self.num_calls
            mcXw, mcXd = self.remove_nlwep(xnew)
            xnew = set([x for x in mcXd])
            n += self.num_calls - old_calls
        if not mcXw:
            #print('**binding b**')
            mcXw |= xnew
        #print('New LWEPs: ', mcXw)
        return mcXw

    def fse(self, se):
        """return diminishing standard error function for an iteration nu"""
        m = self.m
        relax = se/pow(m, self.betaeps)
        return relax

    def calc_delta(self, se):
        """return RLE relaxation for an iteration nu"""
        m = self.m
        relax = se/pow(m, self.betadel)
        return relax

    def calc_m(self, nu):
        """return the sample size for an iteration nu, as in rspline"""
        mmul = 1.1
        m_init = 2
        return ceil(m_init*pow(mmul, nu))

    def calc_b(self, nu):
        """return the limit on spline calls for an iteration nu"""
        mmul = 1.2
        m_init = 8*(self.dim - 1)
        return ceil(m_init*pow(mmul, nu))

    def get_ncn(self, mcS):
        # initialize the non-conforming neighborhood
        ncn = set()
        d = self.num_obj
        r = self.nbor_rad
        dr = range(d)
        delN = get_setnbors(mcS, r)
        delzero = tuple(0 for i in dr)
        # defintion 9 (a) -- check for strict domination in the deleted nbors
        for s in mcS:
            fs = self.gbar[s]
            ses = self.sehat[s]
            dels = tuple(self.calc_delta(ses[i]) for i in dr)
            snb = get_nbors(s, r) - mcS
            for x in snb:
                isfeas, fx, sex = self.estimate(x)
                if isfeas:
                    delx = tuple(self.calc_delta(sex[i]) for i in dr)
                    if does_strict_dominate(fx, fs, delzero, delzero):
                        ncn |= {x}
        # definition 9 (b) initialization
        for x in delN - ncn:
            isfeas, fx, sex = self.estimate(x)
            if isfeas:
                # definition 9 (b) (i) initialization
                notweakdom = True
                # definition 9 (b) (ii) initialization
                notrelaxdom = True
                # definition 9 (b) (iii) initialization
                wouldnotchange = True
                doesweakdom = False
                delx = tuple(self.calc_delta(sex[i]) for i in dr)
                for s in mcS:
                    fs = self.gbar[s]
                    ses = self.sehat[s]
                    dels = tuple(self.calc_delta(ses[i]) for i in dr)
                    # definition 9 (b) (i)
                    if does_weak_dominate(fs, fx, delzero, delzero):
                        notweakdom = False
                    # definition 9 (b) (ii)
                    if does_dominate(fx, fs, delzero, delzero) and does_dominate(fs, fx, dels, delx):
                        notrelaxdom = False
                    # definition 9 (b) (iii)
                    if does_weak_dominate(fx, fs, delzero, delzero):
                        doesweakdom = True
                    if does_weak_dominate(fs, fx, dels, delx) or does_weak_dominate(fx, fs, delx, dels):
                        wouldnotchange = False
                # definition 9 (b)
                if notweakdom and notrelaxdom and (wouldnotchange or doesweakdom):
                    ncn |= {x}
        return ncn

    def spline(self, x0, fx0, sex0, e, nobj, kcon):
        """
        return an estimated local minimizer using pseudo-gradients

        Keyword Arguments:
        x0 -- feasible starting point, tuple of length self.dim
        fx0 -- estimate of x0, tuple of length self.num_obj
        sex0 -- standard error of x0, tuple of length self.num_obj
        e -- objective function constraint, scalar real number
            or float('inf') for unconstrained
        nobj -- objective to minimize, natural number < self.num_obj
        kcon -- objective to constrain, natural number < self.num_obj

        Return Values:
        mcs -- search trajectory of SPLI, set of point tuples
        xn -- estimated local minimizer, tuple of length self.dim
        fxn -- estimate of xn, tuple of length self.num_obj
        sexn -- standard error of xn, tuple of length self.num_obj

        See Wang et. al 2013, R-SPLINE.
        """
        self.num_splines[self.nu] += 1
        b = self.b
        bp = 0
        xn = x0
        fxn = fx0
        sexn = sex0
        mcT = set()
        should_stop = False
        while not should_stop:
            xs, fxs, sexs, np = self.spli(xn, fxn, sexn, e, nobj, kcon, b)
            mcT |= {xs}
            xn, fxn, sexn, npp = self.ne(xs, fxs, sexs, nobj, e, kcon)
            mcT |= {xn}
            bp += np + npp
            if bp >= b or fxn[nobj] == fxs[nobj]:
                should_stop = True
        if bp >= b:
            self.spli_bind[self.nu] += 1
        return mcT, xn, fxn, sexn

    def ne(self, x, fx, sex, nobj, e=float('inf'), kcon=0):
        """
        return the minimizer of the neighborhood of x

        Keyword Arguments:
        x -- a candidate local minimizer, tuple of length self.dim
        fx -- estimate of x on each objective, tuple of length self.num_obj
        sex -- standard error of x, tuple of length self.num_obj
        nobj -- objective to minimize, natural number < self.num_obj
        e -- objective function constraint, scalar real number
            or float('inf') for unconstrained (default)
        kcon -- objective to constrain, natural number < self.num_obj

        Return Values:
        xs -- estimated local minimizer, tuple of length self.dim
        fxs -- objective values of xs, tuple of length self.num_obj
        sexs -- standard errors of xs, tuple of length self.num_obj

        See Wang et. al 2013, R-SPLINE.
        """
        q = self.dim
        m = self.m
        n = 0
        xs = x
        fxs = fx
        vxs = sex
        nbor_rad = self.nbor_rad
        # optimize the case for neighborhood radius of 1
        if nbor_rad == 1:
            for i in range(q):
                xp1 = tuple(x[j] + 1 if i == j else x[j] for j in range(q))
                xm1 = tuple(x[j] - 1 if i == j else x[j] for j in range(q))
                isfeas1, fxp1, vxp1 = self.estimate(xp1, e, kcon)
                if isfeas1:
                    n += m
                    if fxp1[nobj] < fxs[nobj]:
                        xs = xp1
                        fxs = fxp1
                        vxs = vxp1
                        return xs, fxs, vxs, n
                isfeas2, fxm1, vxm1 = self.estimate(xm1, e, kcon)
                if isfeas2:
                    n += m
                    if fxm1[nobj] < fxs[nobj]:
                        xs = xm1
                        fxs = fxm1
                        vxs = vxm1
                        return xs, fxs, vxs, n
        else:
            # for neighborhoods not 1, generate the list of neighbors
            nbors = get_nbors(x, nbor_rad)
            # and check each neighbor until we find a better one
            i = 0
            while i < len(nbors):
                n = nbors[i]
                isfeas, fn, sen = self.estimate(n, e, kcon)
                if isfeas:
                    n += m
                    if fn[nobj] < fxs[nobj]:
                        xs = n
                        fxs = fn
                        vxs = sen
                        break
                i += 1
        return xs, fxs, vxs, n

    def pli(self, x, nobj):
        """
        return a search direction for seeking a local minimizer

        Keyword Arguments:
        x -- a feasible starting point, tuple of length self.dim
        nobj -- objective to minimize, natural number < self.num_obj

        Return Values:
        gamma -- gradient at perturbed x
        gbat -- estimated interpolated function value at perturbed x

        See Wang et. al 2013, R-SPLINE.
        """
        q = self.dim
        x0 = tuple(floor(x[i]) for i in range(q))
        simp = [x0]
        zi = [x[i] - x0[i] for i in range(q)]
        zi.extend((0, 1))
        p = argsort(zi)
        p.reverse()
        z = sorted(zi, reverse=True)
        w = tuple(z[p[i]] - z[p[i + 1]] for i in range(q + 1))
        prevx = x0
        for i in range(1,q + 1):
            x1 = tuple(prevx[j] + 1 if j == p[i] else prevx[j] for j in range(q))
            simp.append(x1)
            prevx = x1
        n = 0
        t = 0
        gbat = 0
        ghat = {}
        for i in range(q + 1):
            isfeas, fx, vx = self.estimate(simp[i])
            if isfeas:
                n += 1
                t += w[i]
                gbat += w[i]*fx[nobj]
                ghat[simp[i]] = fx
        if t > 0:
            gbat /= t
        else:
            gbat = float('inf')
        if n < q + 1:
            gamma = None
        else:
            gamma = [0]*q
            for i in range(1, q + 1):
                gamma[p[i]] = ghat[simp[i]][nobj] - ghat[simp[i - 1]][nobj]
        return gamma, gbat

    def spli(self, x0, fx0, sex0, e, nobj, kcon, b):
        """
        return a candidate minimizer by following a search direction

        Keyword Arguments:
        x0 -- a feasible starting point, tuple of length self.dim
        fx0 -- estimate of x0 on each objective, tuple of length self.num_obj
        sex0 -- standard error of x0, tuple of length self.num_obj
        e -- value to constrain the feasible space, scalar real number
            or float('inf') for unconstrained
        nobj -- the objective to minimize, a natural number < self.num_obj
        kcon -- the objective to constrain, a natural number < self.num_obj

        Return Values:
        xs -- a candidate local minimizer, tuple of length self.dim
        fxs -- estimate of xs, tuple of length self.num_obj
        sexs -- standard error of xs, tuple of length self.dim

        See Wang et. al 2013, R-SPLINE.
        """
        sprn = self.sprn
        m = self.m
        q = len(x0)
        ss = 2.0
        xs = x0
        fxs = fx0
        sexs = sex0
        n = 0
        c = 2.0
        stop_loop = False
        while not stop_loop:
            x1 = perturb(x0, sprn)
            gamma, gbat = self.pli(x1, nobj)
            n += m*(q + 1)
            if not gamma or gamma == [0.0]*q:
                stop_loop = True
                break
            if n > b:
                stop_loop = True
                break
            i = 0
            x0 = xs
            should_stop = False
            self.num_grad[self.nu] += 1
            while not should_stop:
                i += 1
                s = ss*pow(c, i - 1)
                x1 = tuple(int(floor(x0[j] - s*gamma[j]/enorm(gamma))) for j in range(q))
                isfeas, fx1, sex1 = self.estimate(x1, e, kcon)
                if isfeas:
                    n += m
                    if fx1[nobj] < fxs[nobj]:
                        xs = x1
                        fxs = fx1
                        sexs = sex1
                if not x1 == xs:
                    should_stop = True
            if i <= 2:
                stop_loop = True
        return xs, fxs, sexs, n

    def estimate(self, x, con=float('inf'), nobj=0):
        """
        return esimates of g(x) while checking objective feasibility

        Keyword Arguments:
        x -- the vector, or system, to estimate
        con -- the constraint on the objective nobj, default to unconstrained
        nobj -- the objective to constrain, default to 0 (arbitrary)

        Return Values:
        isfeas -- boolean indicating feasibility
        fx -- tuple of estimates of each objective
        vx -- tuple of standard error of each objective

        The RPERLE object should ensure self.m is set as the sample size,
        self.gbar is a dictionary of objective values, and self.sehat is
        a dictionary of standard errors.
        """
        m = self.m
        #first, check if x has already been sampled in this iteration
        if x in self.gbar:
            isfeas = True
            fx = self.gbar[x]
            vx = self.sehat[x]
        #if not, perform sampling
        else:
            isfeas, fx, vx = self.orc.hit(x, m)
            if isfeas:
                self.gbar[x] = fx
                self.sehat[x] = vx
        #next, check feasibility against the constraint which may be different
        # than oracle feasibility
        if isfeas:
            self.num_calls += m
            if fx[nobj] > con:
                isfeas = False
        return isfeas, fx, vx
