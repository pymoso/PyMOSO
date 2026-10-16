#!/usr/bin/env python
"""
Summary
-------
Provide an implementation of MO-COMPASS for users needing a
multi-objective discrete-optimization-via-simulation solver.
"""
from itertools import product
from math import ceil, floor, log

from ..chnbase import MOSOSolver, reject_unknown_params
from ..moso import get_setnbors, get_nondom, enorm, edist

#*************************
# algorithm-specific parameters
# numsamples [default: 8] -- number of feasible points to sample in a iteration
### e.g. pymoso solve --param numsamples 20 --param lb 0 --param ub 50 ProbTPA ExampleSearchSolver
# lb = lower bound that feasible point components can take
# ub = upper bound that feasible point components can take
### e.g. pymoso solve --param lb 0 --param ub 50 ProbTPA ExampleSearchSolver
### lb and ub are required for proper MOCOMPASS operation, choose them
### appropriately for the test problem


class ExampleSearchSolver(MOSOSolver):
    """
    Example implementation of MO-COMPASS, unverified against the source paper.

    This is our interpretation and implementation of MO-COMPASS. It has
    not been reviewed or validated by the algorithm's authors, and any
    deficiency in its performance should be attributed to this
    implementation rather than to the published method.

    H. Li, L. H. Lee, E. P. Chew, and P. Lendermann. 2015. MO-COMPASS: A
    fast convergent search algorithm for multi-objective discrete
    optimization via simulation. IIE Transactions 47, 11 (2015),
    1153-1169. https://doi.org/10.1080/0740817X.2015.1005778

    Compatibility only: this implementation runs correctly on the
    current branch, but its algorithmic behavior has not been validated
    against the paper. See docs/mocompass-mopbnb-known-issues.md for
    known caveats, and docs/rng-interface-design.md sections 4.1-4.3 for
    how its stream-management approach informed the RNG interface
    redesign.

    Parameters
    ----------
    orc : chnbase.Oracle object
    kwargs : dict
        numsamples : int, optional
            Number of feasible points to sample per iteration. Default 8.
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

    PARAMS = ('numsamples', 'ub', 'lb')

    def __init__(self, orc, **kwargs):
        if orc.crnflag:
            raise RuntimeError(
                '{0} does not support --crn. In this framework, common random '
                'numbers are defined per retrospective-approximation iteration: '
                'every hit() call in an iteration starts again from that '
                'iteration\'s baseline streams, and RASolver advances the '
                'iteration itself. {0} is not an RASolver and has no such '
                'iterations, so under --crn every hit() in the whole run would '
                'start from the same baseline -- a second hit() on a point '
                'would silently replay its first replications instead of adding '
                'new ones. What --crn should mean for a solver like this is an '
                'open design question (docs/rng-interface-design.md, section 11, '
                'question 11; see also sections 4.2-4.3 and '
                'docs/mocompass-mopbnb-known-issues.md). Run without '
                '--crn.'.format(type(self).__name__)
            )
        self.num_samples = int(kwargs.pop('numsamples', 8))
        try:
            self.sprn = kwargs.pop('sprn')
            self.ub = int(kwargs.pop('ub'))
            self.lb = int(kwargs.pop('lb'))
        except KeyError as e:
            raise TypeError(
                '{0} requires an upper and lower bound: specify --param ub '
                '<somenumber> and --param lb <somenumber>.'.format(type(self).__name__)
            ) from e
        # solve() hands every solver a starting point; this one has no
        # use for it.
        kwargs.pop('x0', None)
        reject_unknown_params(self, kwargs)
        super().__init__(orc)

    def solve(self, budget):
        nu = 0
        num_samples = self.num_samples
        xr = range(self.lb, self.ub + 1)
        arglist = [xr for i in range(self.dim)]
        mcD = set(product(*arglist))
        self.seeds = dict()
        mcv = set()
        phat = dict()
        phat[nu] = set()
        simcalls = dict()
        gbar = dict()
        nx = dict(zip(mcD, [0 for i in mcD]))
        self.seeds[0] = self.orc.rng.getstate()
        simcalls[nu] = 0
        while self.num_calls <= budget:
            nu = nu + 1
            mcx = self.sample_mpr(phat[nu - 1], mcv, mcD, num_samples)
            mcv |= mcx
            mcnphat = get_setnbors(phat[nu - 1], 1) | phat[nu - 1]
            alen = len(mcv - phat[nu - 1])
            for x in mcv:
                ax = self.sar(x, mcnphat, nu, alen)
                self.update_gbar(x, ax, gbar, nx)
            simcalls[nu] = self.num_calls
            tmp = {x: gbar[x] for x in mcv}
            phat[nu] = get_nondom(tmp)
        # No iteration bookkeeping here: this solver has no RA iterations
        # for the framework to advance (it used to call orc.crn_advance()
        # at this point -- removed, docs/rng-interface-design.md §4.2). The
        # reported endseed comes from orc.get_endseed() (§8.2/§12 step 8),
        # the run's actual oracle-role coordinate high-water mark -- the
        # standard "safely-spaced next seed for an independent follow-up
        # run" every other in-tree solver provides.
        # oracle_high_water_mark: raw material for testsolve()'s own
        # cross-path aggregation (§12 step 8 stage 2), not a per-path
        # seed itself -- see Oracle.get_high_water_mark()'s docstring.
        mydat = {
            'itersoln': phat, 'simcalls': simcalls, 'endseed': self.orc.get_endseed(),
            'oracle_high_water_mark': self.orc.get_high_water_mark(),
        }
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
        self.orc.rng.setstate(start_state)
        isfeas, fx, sex = self.orc.hit(x, ax)
        end_state = self.orc.rng.getstate()
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
            xlst = self.sprn.sample(sorted(mcs), count)
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
            r = self.sprn.sample(sorted(capR), 1)[0]
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
                p = self.sprn.sample(sorted(phat), 1)[0]
                idir = self.sprn.sample(range(self.dim), 1)[0]
                is_ok, x = self.cssample(p, idir, visited - phat, mcs - visited - phat)
                if is_ok:
                    xpts |= x
                    visited |= x
                else:
                    num_bad += 1
                i = i + 1
            return xpts
