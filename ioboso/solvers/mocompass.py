#!/usr/bin/env python
from math import ceil, floor, log, pow
from ..simoptutils import *
from ..simbase import SimOptSolver

class MOCOMPASS(SimOptSolver):
    def __init__(self, orc, sprn=None, x0=None, betaeps=None, betadel=None):
        super().__init__(orc, sprn, x0)

    def __str__(self):
        return 'moc'

    def solve(self, budget):
        nu = 0
        num_samples = 8
        mcD = set(feas2set(self.orc.get_feasspace()))
        self.seeds = dict()
        mcv = set()
        phat = dict()
        phat[nu] = set()
        simcalls = dict()
        gbar = dict()
        nx = dict(zip(mcD, [0 for i in mcD]))
        self.seeds[0] = self.orc.prn.getstate()
        simcalls[nu] = 0
        while self.num_calls <= budget:
            nu = nu + 1
            mcx = self.sample_mpr(phat[nu - 1], mcv, mcD, num_samples)
            mcv |= mcx
            mcnphat = get_setnbors(phat[nu - 1]) | phat[nu - 1]
            alen = len(mcv - phat[nu - 1])
            for x in mcv:
                ax = self.sar(x, mcnphat, nu, alen)
                self.update_gbar(x, ax, gbar, nx)
            simcalls[nu] = self.num_calls
            tmp = {x: gbar[x] for x in mcv}
            phat[nu] = get_biparetos(tmp)
        mydat = {'phat': phat, 'simcalls': simcalls}
        return mydat

    def sar(self, x, nbphat, nu, mult):
        if x in nbphat:
            return mult*ceil(min(1, log(nu)))
        else:
            return ceil(min(1, log(nu)))

    def update_gbar(self, x, ax, gbar, nx):
        if ax == 0:
            ax = 1
        start_num = nx[x]
        start_state = self.seeds[start_num]
        self.orc.prn.setstate(start_state)
        isfeas, fx, sex = self.orc.hit(x, ax)
        #print(isfeas, x, fx, ax)
        end_state = self.orc.prn.getstate()
        end_num = start_num + ax
        self.seeds[end_num] = end_state
        if isfeas:
            self.num_calls += ax
            nx[x] += ax
            if x in gbar:
                newbar = []
                for i, fi in enumerate(fx):
                    newbar.append((gbar[x][i]*nx[x] + fi*ax)/(nx[x] + ax))
                gbar[x] = tuple(newbar)
            else:
                gbar[x] = fx

    def sample_set(self, mcs, count):
        dlen = len(mcs)
        if dlen <= count:
            return mcs
        else:
            xlst = self.sprn.sample(mcs, count)
            return set(xlst)

    def cssample(self, p, cdir, mcc, mcs):
        dm = {x[cdir] for x in mcs}
        maxX = max(dm) - p[cdir]
        minX = min(dm) - p[cdir]
        capR = set(range(minX, maxX + 1)) - {0}
        dr = range(self.dim)
        is_ok = True
        ei = []
        for i, xi in enumerate(p):
            if i == cdir:
                ei.append(1)
            else:
                ei.append(0)
        ei = tuple(ei)
        for y in mcc:
            tmp1 = tuple(2*(y[i] - p[i]) for i in dr)
            tmp2 = pow(enorm(tuple(y[i] - p[i] for i in dr)), 2)
            tmp3 = sum([tmp1[i]*ei[i] for i in dr])
            if tmp3 == 0:
                c = edist(y, p)/2
            else:
                c = tmp2/tmp3
            if c < 0:
                capR &= set(range(ceil(c), maxX + 1))
            else:
                capR &= set(range(minX, floor(c) + 1))
            if not capR:
                is_ok = False
                break
        if is_ok:
            r = self.sprn.sample(capR, 1)[0]
            # print('stop', ' p: ', p, ' r: ', r, ' min: ', minX, ' max: ', maxX, ' lenR: ', len(capR))
            tmp1 = tuple(r*ei[i] for i in dr)
            myx = tuple(p[i] + tmp1[i] for i in dr)
            return is_ok, {myx}
        else:
            return is_ok, None

    def sample_mpr(self, phat, visited, mcs, count):
        if not phat:
            return self.sample_set(mcs, count)
        else:
            xpts = set()
            i = 0
            num_bad = 0
            while i < count:
                p = self.sprn.sample(phat, 1)[0]
                idir = self.sprn.sample(range(self.dim), 1)[0]
                is_ok, x = self.cssample(p, idir, visited - phat, mcs - visited - phat)
                if is_ok:
                    xpts |= x
                    visited |= x
                else:
                    num_bad += 1
                i = i + 1
            # if num_bad > 0:
            #     xpts |= self.sample_set(mcs, num_bad)
            return xpts
