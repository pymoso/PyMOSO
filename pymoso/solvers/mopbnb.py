#!/usr/bin/env python
"""
Summary
-------
Provide an implementation of MOPBnB for users needing a
multi-objective probabilistic branch-and-bound solver.
"""
from math import ceil, log, sqrt
from itertools import islice, product

from ..chnbase import MOSOSolver
from ..chnutils import get_nondom


class MOPBnB(MOSOSolver):
    """
    MOPBnB solver for Pareto-optimal approximation via probabilistic branch and bound.

    This is our interpretation and implementation of MOPBnB. It has
    not been reviewed or validated by the algorithm's authors, and any
    deficiency in its performance should be attributed to this
    implementation rather than to the published method.

    H. Huang and Z. B. Zabinsky. 2014. Multiple objective probabilistic
    branch and bound for Pareto optimal approximation. In Proceedings
    of the 2014 Winter Simulation Conference, A. Tolk, S. Y. Diallo,
    I. O. Ryzhov, L. Yilmaz, S. Buckley, and J. A. Miller (Eds.). IEEE,
    Piscataway, NJ, 3916-3927. https://doi.org/10.1109/WSC.2014.7020217

    Compatibility only: this implementation runs correctly on the
    current branch, but its algorithmic behavior has not been validated
    against the paper. See docs/mocompass-mopbnb-known-issues.md for
    known caveats, and docs/rng-interface-design.md sections 4.1-4.3 for
    related RNG interface design work.

    Parameters
    ----------
    orc : chnbase.Oracle object
    kwargs : dict
        subregions : int, optional
            Number of subregions to branch each region into. Default 2.
        alpha : float, optional
            Overall confidence parameter. Default 0.05.
        delta : float, optional
            Sampling ratio for subregion elimination. Default 0.1.
        R0 : int, optional
            Initial number of replications per point. Default 20.
        lb : int
            Lower bound each feasible point's components may take.
            Required.
        ub : int
            Upper bound each feasible point's components may take.
            Required.

    See also
    --------
    chnbase.MOSOSolver
    """

    def __init__(self, orc, **kwargs):
        if orc.crnflag:
            raise RuntimeError(
                '{0} does not support --crn yet. It calls crn_advance() once, '
                'at the end of solve(), which the framework CRN protocol only '
                'ever advances once per algorithmic iteration for RASolver-family '
                'solvers -- for a solver that calls it just once, every '
                'intervening hit() call rewinds to the same frozen baseline, so '
                'every replication in the run would silently replay identical '
                'draws. CRN support for general MOSOSolvers is pending the RNG '
                'interface redesign (see docs/rng-interface-design.md, sections '
                '4.2-4.3, and docs/mocompass-mopbnb-known-issues.md). Run without '
                '--crn.'.format(type(self).__name__)
            )
        self.subregions = int(kwargs.pop('subregions', 2))
        self.alpha = float(kwargs.pop('alpha', 0.05))
        self.delta = float(kwargs.pop('delta', 0.1))
        self.R0 = int(kwargs.pop('R0', 20))
        try:
            self.sprn = kwargs.pop('sprn')
            self.ub = int(kwargs.pop('ub'))
            self.lb = int(kwargs.pop('lb'))
        except KeyError as e:
            raise TypeError(
                '{0} requires an upper and lower bound: specify --param ub '
                '<somenumber> and --param lb <somenumber>.'.format(type(self).__name__)
            ) from e
        super().__init__(orc)

    def solve(self, budget):
        nobj = self.orc.num_obj
        subreglst = dict()
        Nsamp = dict()
        Psamp = dict()
        simcalls = dict()
        alphak = dict()
        phat = dict()
        R = dict()
        xr = range(self.lb, self.ub + 1)
        arglist = [xr for i in range(self.dim)]
        mcX = set(product(*arglist))
        gbar = dict()
        s2 = dict()
        iterk = 0
        phat[iterk] = set()
        B = self.subregions
        delta = self.delta
        alpha = self.alpha
        alphak[0] = alphak[1] = alpha / B
        simcalls[iterk] = 0
        R[0] = self.R0
        subreglst[0] = subreglst[1] = self.get_isubreg(mcX, B)
        iterk += 1
        while self.num_calls <= budget and self.is_branchable(subreglst[iterk]):
            allspts = set()
            num_subs = len(subreglst[iterk])
            Nk = self.get_Nk(alphak[iterk], delta)
            Nsamp[iterk] = Nk
            Psamp[iterk] = dict()
            maxS2 = -float('inf')
            minS2 = float('inf')
            dmin = float('inf')
            print('-- -- Beginning iteration : ', iterk)
            print('-- -- Taking ', R[iterk - 1], ' replications at ',  Nk, ' points from each of ', B, ' regions. ')
            for i in range(num_subs):
                spoints = self.sample_region(subreglst[iterk][i], Nk)
                Psamp[iterk][i] = spoints
                allspts |= spoints
                for x in spoints:
                    gbar[x], s2[x] = self.get_reps(x, R[iterk - 1])
                    mtmp = max(s2[x])
                    if mtmp > maxS2:
                        maxS2 = mtmp
                    if mtmp < minS2:
                        minS2 = mtmp
            glst = list(zip(*[gbar[x] for x in allspts]))
            for j in range(nobj):
                tmplst = sorted(list(glst[j]))
                for k in range(len(tmplst) - 1):
                    dlen = tmplst[k + 1] - tmplst[k]
                    if dlen < dmin and dlen > 0:
                        dmin = dlen
            R[iterk] = max(R[iterk - 1], ceil(pow(bsm(1 - alphak[iterk]/2)*maxS2/(dmin/2), 2)))
            rdiff = R[iterk] - R[iterk - 1]
            print('-- -- Smallest distance between points is {:2.5f} and the largest variance is {:5.3f}.'.format(dmin, maxS2))
            print('-- -- Taking ', rdiff, ' additional replications at each point unless budget is insufficient.')
            if rdiff > 0 and rdiff*len(allspts) < budget:
                for x in allspts:
                    self.update_gbar(x, rdiff, gbar, s2, R[iterk - 1])
            tmp = {x: gbar[x] for x in allspts}
            phat[iterk] = get_nondom(tmp)
            print('-- -- Computing estimated non-dominated points and pruning subregions. ')
            alphak[iterk + 1] = alphak[iterk] / B
            prune = [len(phat[iterk] & subreglst[iterk][i]) > 0 for i in range(num_subs)]
            subreglst[iterk + 1] = self.gen_subreg(prune, subreglst[iterk], B)
            simcalls[iterk] = self.num_calls
            print('-- -- Ending iteration: ', iterk, ' after ', self.num_calls, ' replications. ')
            iterk += 1
        # Still reachable, and still meaningful, even though this solver is
        # restricted to crnflag=False (see __init__): crn_check() no-ops
        # under crnflag=False, but get_next_prnstream still performs a real
        # 2**127 jump, so this keeps this solver's own iteration bookkeeping
        # advancing correctly. The reported endseed itself comes from
        # orc.get_endseed() (docs/rng-interface-design.md §8.2/§12 step 8) --
        # the run's actual oracle-role coordinate high-water mark, not just
        # this call count, giving the standard "safely-spaced next seed for
        # an independent follow-up run" every other in-tree solver provides.
        self.orc.crn_advance()
        # oracle_high_water_mark: raw material for testsolve()'s own
        # cross-path aggregation (§12 step 8 stage 2), not a per-path
        # seed itself -- see Oracle.get_high_water_mark()'s docstring.
        mydat = {
            'itersoln': phat, 'simcalls': simcalls, 'endseed': self.orc.get_endseed(),
            'oracle_high_water_mark': self.orc.get_high_water_mark(),
        }
        return mydat

    def sample_region(self, reg, n):
        nk = min(len(reg), n)
        return set(self.sprn.sample(sorted(reg), nk))

    def gen_subreg(self, prune, slst, B):
        subreglst = []
        for i, p in enumerate(prune):
            if p and len(slst[i]) > 1:
                subreglst.extend(self.get_isubreg(slst[i], B))
        return subreglst

    def get_isubreg(self, mcX, B):
        xcard = len(mcX)
        subreglst = []
        for i in range(B):
            subreg = set(islice(mcX, i, xcard, B))
            subreglst.append(set(subreg))
        return subreglst

    def get_Nk(self, alphak, delta):
        return ceil(log(alphak) / log(1 - delta))

    def get_reps(self, x, m):
        isfeas, fx, sex = self.orc.hit(x, m)
        if isfeas:
            self.num_calls += m
            s2 = tuple(pow(sex[j], 2)*sqrt(m) for j in range(len(fx)))
            return fx, s2

    def update_gbar(self, x, ax, gbar, sehat, nx):
        isfeas, fx, sex = self.orc.hit(x, ax)
        s2 = tuple(pow(sex[j], 2)*sqrt(ax) for j in range(len(fx)))
        if isfeas:
            self.num_calls += ax
            for i, fi in enumerate(fx):
                sehat[x] = tuple((nx*(sehat[x][i] +gbar[x][i]**2) + ax*(s2[i] + fx[i]**2)) / (nx + ax) for i in range(self.orc.num_obj))
                gbar[x] = tuple((gbar[x][i]*nx + fi*ax)/(nx + ax) for i in range(self.orc.num_obj))

    def is_branchable(self, srlst):
        can_branch = False
        for sr in srlst:
            if len(sr) > 1:
                can_branch = True
        return can_branch


#constants used for approximating the inverse standard normal cdf
## Beasly-Springer-Moro
bsma = [2.50662823884, -18.61500062529, 41.39119773534, -25.44106049637]
bsmb = [-8.47351093090, 23.08336743743, -21.06224101826, 3.13082909833]
bsmc = [0.3374754822726147, 0.9761690190917186, 0.1607979714918209, 0.0276438810333863, 0.0038405729373609,0.0003951896411919, 0.0000321767881768, 0.0000002888167364, 0.0000003960315187]

def bsm(u):
    """Approximate the uth quantile of the standard normal distribution."""
    y = u - 0.5
    if abs(y) < 0.42:
        ## approximate from the center (Beasly Springer 1973)
        r = pow(y, 2)
        r2 = pow(r, 2)
        r3 = pow(r, 3)
        r4 = pow(r, 4)
        asum = sum([bsma[0], bsma[1]*r, bsma[2]*r2, bsma[3]*r3])
        bsum = sum([1, bsmb[0]*r, bsmb[1]*r2, bsmb[2]*r3, bsmb[3]*r4])
        z = y*(asum/bsum)
    else:
        ## approximate from the tails (Moro 1995)
        if y < 0.0:
            signum = -1
            r = u
        else:
            signum = 1
            r = 1 - u
        s = log(-log(r))
        s0 = pow(s, 2)
        s1 = pow(s, 3)
        s2 = pow(s, 4)
        s3 = pow(s, 5)
        s4 = pow(s, 6)
        s5 = pow(s, 7)
        s6 = pow(s, 8)
        clst = [bsmc[0], bsmc[1]*s, bsmc[2]*s0, bsmc[3]*s1, bsmc[4]*s2, bsmc[5]*s3, bsmc[6]*s4, bsmc[7]*s5, bsmc[8]*s6]
        t = sum(clst)
        z = signum*t
    return z
