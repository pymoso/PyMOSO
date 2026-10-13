#!/usr/bin/env python
"""
Provide base classes and supporting functions for problem  and solver
implementations.

Listing
--------------
_mp_objmethod, function
MOSOSolver(object), class
RASolver(MOSOSolver), class
RLESolver(RASolver), class
Oracle(object), class
"""
from statistics import mean, variance
from math import sqrt, ceil, floor
from .prng import registry
from .prng.base import (
    ReplicationOverflow, IterationOverflow, SyncOverflow, PointCodeCollision, one_past,
)
from .executor import (
    ReplicationBlock, SerialExecutor, PoolExecutor, InProcessHandle, ClassHandle,
    build_transport_descriptor, reconstruct_transport_descriptor,
)
from .chnutils import perturb, argsort, enorm, get_setnbors, get_nbors, is_lwep, get_nondom, does_strict_dominate, does_weak_dominate, does_dominate, get_biparetos


class MOSOSolver(object):
    """
    Base class for solver implentations.

    Attributes
    ----------
    orc : Oracle
    The problem implementation to solve
    num_calls : int
    The total number of calls to orc.g
    num_obj : int
    The number of objectives returned by orc.g
    dim : The cardinality of points in the domain of orc.g

    Parameters
    ----------
    orc: Oracle object

    Notes
    -----
    The solve attribute must be implemented in sub-classes for use in
    PyMOSO.
    """

    def __init__(self, orc):
        self.orc = orc
        self.num_calls = 0
        self.num_obj = self.orc.num_obj
        self.dim = self.orc.dim
        super().__init__()

    # def solve(self, budget):
    #     raise NotImplementedError


class RASolver(MOSOSolver):
    """
    Base class for Retrospective Approximation algorithm
    implementations. The class methods assume integer-ordered feasible
    points.

    Attributes
    ----------
    orc : Oracle
    The problem implementation to solve
    num_calls : int
    The total number of calls to orc.g
    num_obj : int
    The number of objectives returned by orc.g
    dim : int
    The cardinality of points in the domain of orc.g
    nbor_rad : int
    The radius used to determine point neighbors, defaults is 1
    mconst : int
    Affects the iteration sample sizes. Default is 2
    bconst : int
    Affects the iteration sampling search limits.
    sprn : prng.MRG32k3a object. Default is 8.
    Pseudo-random number stream available to the solver, should
    generate independently of orc.rng.
    x0 : tuple of numbers
    Vector points such that x0[0] is its first component, and
    x0[orc.dim - 1] is the last.
    gbar : dict
    Dictionary of {tuple of int: tuple of float} mapping feasible
    points to their objective values. In RA algorithms, it is
    cleared every iteration.
    sehat : dict
    Like gbar, but maps feasible points to standard errors of
    the objective values.
    m : int
    Iteration sample size which is automatically updated
    b : int
    Iteration search sampling limit which is automatically updated
    nu : int
    The iteration number
    endseed : tuple of int
    The next seed to be used by 'orc.rng'

    Parameters
    ----------
    orc : Oracle object
    kwargs : dict

    Notes
    -----
    The method spsolve must be implemented to use an RASolver in
    PyMOSO
    """

    def __init__(self, orc, **kwargs):
        self.nbor_rad = kwargs.pop('radius', 1)
        self.mconst = kwargs.pop('mconst', 2)
        self.bconst = kwargs.pop('bconst', 8)
        try:
            self.sprn = kwargs.pop('sprn')
            self.x0 = kwargs.pop('x0')
        except KeyError as e:
            raise TypeError(
                '{0} requires an x0 and a random number seed (sprn).'.format(type(self).__name__)
            ) from e
        super().__init__(orc)

    def solve(self, budget):
        """
        Solves the MOSO problem implicitly implemented in orc.

        Parameters
        ----------
        budget : int
    The maximum number of calls allowed to orc.g

    Returns
    -------
    resdict : dict
        """
        self.endseed = self.orc.get_endseed()
        lesnu = dict()
        simcalls = dict()
        lesnu[0] = set() | {self.x0}
        simcalls[0] = 0
        # initialize the iteration counter
        self.nu = 0
        # invoke the Retrospective approximation algorithm
        self.rasolve(lesnu, simcalls, budget)
        # name the data keys and return the results. oracle_high_water_mark
        # (docs/rng-interface-design.md §12 step 8 stage 2) is raw material
        # for testsolve()'s own cross-path aggregation, not a per-path
        # seed itself -- see Oracle.get_high_water_mark()'s own docstring.
        resdict = {
            'itersoln': lesnu, 'simcalls': simcalls, 'endseed': self.endseed,
            'oracle_high_water_mark': self.orc.get_high_water_mark(),
        }
        return resdict

    def rasolve(self, phatnu, simcalls, budget):
        """
        Repeatedly solve the sample-path problem using a sequence of
        increasing sample sizes.

        Parameters
        ----------
        phatnu : dict
    Stores the set of tuples of int for each iteration
    simcalls : dict
    Dictionary of {iteration int : int of calls to orc.g}
    budget : int
    Total number of calls allowed to orc.g across all iterations

    Notes
    -----
    This updates does not return anything, it updates the simcalls,
    phatnu dictionaries and the endseed value.
        """

        while self.num_calls < budget:
            self.nu += 1
            # No iteration-count guard here (docs/rng-interface-design.md
            # §12 step 4b, open question 9, settled): MAX_RI's collision-
            # avoidance reason is gone -- coordinates are computed
            # directly from (isp, iteration, ...), not reserved by a
            # pre-walked window, so there is nothing left to overrun. No
            # replacement runaway-loop guard was added either (§6, §11
            # open question 9's own reasoning): a solver whose iterations
            # never terminate is a defect in that solver (see
            # KNOWN_ISSUES.md's MyRAAlg entry for the concrete
            # consequence), not something this layer should paper over
            # with an arbitrary constant.
            self.m = self.calc_m(self.nu)
            self.b = self.calc_b(self.nu)
            self.gbar = dict()
            self.sehat = dict()
            #print(self.nu)
            #print('warm start: ', phatnu[self.nu - 1])
            aold = phatnu[self.nu - 1]
            phatnu[self.nu] = self.spsolve(aold)
            #print('spsolve: ', phatnu[self.nu])
            simcalls[self.nu] = self.num_calls
            self.orc._advance_iteration()
            self.endseed = self.orc.get_endseed()

    def get_min(self, mcS):
        """
        Generate a sample path minimizer for every objective and other
        visited, non-dominated points.

        Parameters
        ----------
        mcS : set
    Set of tuples of int representing feasible point of orc.

    Returns
    -------
    xmin : set
    Set of non-dominated points searched by spline in every
    objective.
        """
        self.upsample(mcS | {self.x0})
        if self.x0 not in self.gbar:
            raise ValueError(
                'x0={0} is infeasible. RA solvers require a feasible starting point.'.format(self.x0)
            )
        unconst = float('inf')
        kcon = 0
        xmin = set()
        krange = range(self.num_obj)
        mcT = set()
        for k in krange:
            kmin = min(mcS | {self.x0}, key=lambda t: self.gbar[t][k])
            tb, xmink, _, _ = self.spline(kmin, unconst, k, kcon)
            xmin |= {xmink}
            mcT |= tb
        tmp = {x: self.gbar[x] for x in xmin | mcS | mcT | {self.x0}}
        xmin = get_nondom(tmp)
        return xmin

    def spline(self, x0, e=float('inf'), nobj=0, kcon=0):
        """
        Generate an sample path local minimizer using pseudo-gradients

        Parameters
        ----------
        x0 : tuple of int
    Feasible point of orc
        e : float
    Constraint such the minimum 'fxn' < 'e'. Defaults to
    float('inf'), i.e. unconstrained.
    nobj : int
    Index of the objective to minimize, takes {0, 1,..., dim-1}
    Defaults to 0, the first objective
    kcon : int
    Index of the objective to constrain, takes {0, 1,..., dim-1}
    Defaults to 0.

        Returns
        -------
        mcT : set of tuples of numbers
    The set of visited points
    xn : tuple of int
    The feasible minimizer
    fxn : tuple of float
    Objective values of 'xn'
    sexn : tuple of float
    Standard errors of 'fxn'
        """

        fx0 = self.gbar[x0]
        sex0 = self.sehat[x0]
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
        return mcT, xn, fxn, sexn

    def ne(self, x, fx, sex, nobj, e=float('inf'), kcon=0):
        """
        Finds a neighborhood point with an objective value smaller than
        that of a given point.

        Parameters
        ----------
        x : tuple of int
    Feasible point around which to perform the neighborhood
    search
    fx : tuple of float
    Objective values of 'x'
    sex : tuple of float
    Standard errors of 'fx'
    nobj : int
    index of the objective to minimize, takes values in
    {0, 1, ..., dim-1}, default is 0
    e : float
    constraint such that solution objective value < 'e', default
    is float('inf') i.e. unconstrained
    kcon : int
    index of the objective to constrain less than 'e', takes
    values in {0, 1, ..., dim-1}, default is 0

    Returns
    -------
    xs : tuple of int
    Feasible point which minimizes the neighborhood of 'x'
    fxs : tuple of float
    Objective values of 'xs'
    sexs : tuple of float
    Standard errors of 'fxs'
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
            for nb in nbors:
                isfeas, fn, sen = self.estimate(nb, e, kcon)
                if isfeas:
                    n += m
                    if fn[nobj] < fxs[nobj]:
                        xs = nb
                        fxs = fn
                        vxs = sen
                        break
        return xs, fxs, vxs, n

    def pli(self, x, e, nobj, kcon):
        """
        Generate a convex hull and construct a pseudo-gradient

        Parameters
        ----------
        x : tuple of int
    Feasible point
    e : float
    Feasibility constraint on points in the convex hull
    nobj : int
    Index of objective on which to construct the pseudo-gradient
    kcon : int
    Index on objective to constrain

        Returns
        -------
        gamma : tuple of float
    direction of the pseudo-gradient
    gbat : tuple of float
    interpolated objective values of the perturbed 'x'
        xbest : tuple of int
    minimizer of 'x' and its convex hull
    fxbest : tuple of float
    minimum value of 'x' and its convex hull
        """
        q = self.dim
        x0 = tuple(floor(x[i]) for i in range(q))
        simp = [x0]
        zi = [x[i] - x0[i] for i in range(q)]
        zi.extend((0, 1))
        p = argsort(zi)
        p.reverse()
        z = sorted(zi, reverse=True)
        w = tuple(z[i] - z[i + 1] for i in range(q + 1))
        prevx = x0
        for i in range(1,q + 1):
            x1 = tuple(prevx[j] + 1 if j == p[i] else prevx[j] for j in range(q))
            simp.append(x1)
            prevx = x1
        n = 0
        t = 0
        gbat = 0
        ghat = {}
        xbest = None
        fxbest = None
        # The whole simplex is estimated whatever the results are.
        estimates = self.estimate_many(simp)
        for i in range(q + 1):
            isfeas, fx, vx = estimates[i]
            if isfeas:
                isfeas2, fx, vx = self.estimate(simp[i], e, kcon)
                if isfeas2:
                    if not xbest:
                            xbest = simp[i]
                            fxbest = fx
                    else:
                        if fx[nobj] < fxbest[nobj]:
                            xbest = simp[i]
                            fxbest = fx
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
        return gamma, gbat, xbest, fxbest

    def spli(self, x0, fx0, sex0, e, nobj, kcon, b):
        """
        Repeatedly construct pseudo-gradients and search the direction
        for optimal feasible points.

        Parameters
        ----------
        x0 : tuple of int
    Feasible point from which to search
    fx0 : tuple of float
    Objective values of 'x0'
    sex0 : tuple of float
    Standard errors of 'fx0'
    e : float
    Constraint on the values of the minimizer
    nobj : int
    Index of objective to minimize, takes values in
    {0, 1, ..., dim-1}
    kcon : int
    Index of objective to constrain less than 'e', takes values
    in {0, 1, ..., dim-1}
    b : int
    Limit on calls to orc.g when searching

        Returns
        -------
        xs: tuple of int
    The point with the smallest value found by searching the
    psuedo-gradients
    fxs : tuple of float
    The objective values of 'xs'
    sexs : tuple of float
    The standard errors of 'fxs'
    n : int
    The number of new calls to orc.g
        """
        sprn = self.sprn
        m = self.m
        q = len(x0)
        ss = 2.0
        c = 2.0
        xs = x0
        fxs = fx0
        sexs = sex0
        n = 0
        stop_loop = False
        while not stop_loop:
            x1 = perturb(x0, sprn)
            gamma, gbat, xbest, fxbest = self.pli(x1, e, nobj, kcon)
            if xbest:
                if fxbest[nobj] < fxs[nobj]:
                    xs = xbest
                    fxs = fxbest
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
                if not x1 == xs or n > b:
                    should_stop = True
            x0 = xs
            if i <= 2:
                stop_loop = True
        return xs, fxs, sexs, n

    def _simulate(self, call, *args):
        """
        Call into the oracle, reporting anything its simulation raises
        as a RuntimeError that names the problem and the likely cause.

        Parameters
        ----------
        call : callable
            `self.orc.hit` or `self.orc.hit_many`.
        args
            Its arguments.
        """
        try:
            return call(*args)
        except TypeError as e:
            raise RuntimeError(
                'Unable to simulate {0}. Ensure the g signature is g(self, x, rng) '
                'and returns isfeas, (obj1, obj2, ...). Message: {1}'.format(type(self.orc).__name__, e)
            ) from e
        except ZeroDivisionError as e:
            raise RuntimeError(
                'Unable to simulate {0}. Message: {1}'.format(type(self.orc).__name__, e)
            ) from e
        except ValueError as e:
            raise RuntimeError(
                'Unable to simulate {0}. Ensure the g signature is g(self, x, rng) '
                'and returns isfeas, (obj1, obj2, ...). Message: {1}'.format(type(self.orc).__name__, e)
            ) from e
        except AttributeError as e:
            raise RuntimeError(
                'Unable to simulate {0}. Are you missing an import? Message: {1}'.format(type(self.orc).__name__, e)
            ) from e
        except IndexError as e:
            raise RuntimeError(
                'Unable to simulate {0}. Ensure len(obj1, obj2, ..) == num_obj. Message: {1}'.format(type(self.orc).__name__, e)
            ) from e
        except Exception as e:
            raise RuntimeError(
                'Unable to simulate {0}. Message: {1}'.format(type(self.orc).__name__, e)
            ) from e

    def estimate_many(self, points):
        """
        The same results, and the same effect on `gbar`, `sehat` and
        `num_calls`, as `[self.estimate(x) for x in points]` -- with
        every point that needs simulating submitted to the oracle
        together (`Oracle.hit_many`), so that under `--simpar` the
        workers share all of their replications rather than one
        point's at a time (docs/simpar-ceiling.md).

        Use it wherever a set of points is estimated before any of the
        results is looked at. It cannot help where the next point
        depends on the last result (`ne`'s first-improvement search,
        `spli`'s line search).

        Parameters
        ----------
        points : iterable of tuple of int

        Returns
        -------
        list of (isfeas, fx, vx)
            One per point, in order, each as `estimate(x)` returns it.

        Notes
        -----
        An infeasible point is not stored, so `estimate` simulates it
        again each time it is asked. A point that occurs more than
        once in `points` is therefore simulated in rounds: once with
        everything else, then again -- only if that came back
        infeasible -- for its next occurrence. That is exactly what
        the one-at-a-time loop does, and it has to be reproduced:
        each repeat draws further replications, which can change the
        point's outcome (a problem whose feasibility is random) and
        can move the end seed.
        """
        points = list(points)
        m = self.m
        results = [None]*len(points)
        remaining = range(len(points))
        while remaining:
            batch = []
            in_batch = set()
            later = []
            for i in remaining:
                x = points[i]
                if x in self.gbar:
                    results[i] = (True, self.gbar[x], self.sehat[x])
                elif x in in_batch:
                    later.append(i)
                else:
                    in_batch.add(x)
                    batch.append(i)
            if batch:
                outcomes = self._simulate(self.orc.hit_many, [(points[i], m) for i in batch])
                for i, (isfeas, fx, vx) in zip(batch, outcomes):
                    if isfeas:
                        self.num_calls += m
                        self.gbar[points[i]] = fx
                        self.sehat[points[i]] = vx
                    results[i] = (isfeas, fx, vx)
            remaining = later
        return results

    def estimate(self, x, con=float('inf'), nobj=0):
        """
        Wraps simulation calls, updates the number of simulation calls,
        performs feasibility checks, and stores the resulting objective
        values.

        Parameters
        ----------
        x : tuple of int
    Point to simulate
    con : float
    Constraint value to check feasibility, default is
    float('inf') i.e. unconstrained
    nobj : int
    Index of objective to minimize, default is 0, takes values
    in {0, 1, ..., len('x') -1}

    Returns
    -------
    isfeas : bool
    True if 'fx' < 'e' and 'x' is feasible to the simulation
    fx : tuple of float
    Objective values of 'x'
    vx : tuple of float
    Standard errors of 'fx'
        """
        m = self.m
        #first, check if x has already been sampled in this iteration
        if x in self.gbar:
            isfeas = True
            fx = self.gbar[x]
            vx = self.sehat[x]
        #if not, perform sampling
        else:
            #print('in: ', self.orc.rng.get_seed())
            isfeas, fx, vx = self._simulate(self.orc.hit, x, m)
            if isfeas:
                #print('out: ', self.orc.rng.get_seed())
                self.num_calls += m
                self.gbar[x] = fx
                self.sehat[x] = vx
        #next, check feasibility against the constraint which may be different
        # than oracle feasibility
        if isfeas:
            if fx[nobj] > con:
                isfeas = False
        return isfeas, fx, vx

    # def spsolve(self, warm_start):
    #     """Solve a sample path problem. Implement this in the child class."""
    #     pass

    def upsample(self, mcS):
        """
        Estimate points at the sample size of the current iteration and
        store the results.

        Parameters
        ----------
        mcS : set of tuple of int
    Set of feasible points of which to estimate

    Returns
    -------
    outset : set of tuple of int
    Subset of 'mcS' which are feasible
        """
        outset = set()
        points = list(mcS)
        for s, (isfeas, fs, ses) in zip(points, self.estimate_many(points)):
            if isfeas:
                outset |= {s}
        return outset

    def calc_m(self, nu):
        """
        Compute the iteration sample size

        Parameters
        ----------
        nu : int
    the iteration number

    Returns
    -------
    int
    The sample size
        """

        mmul = 1.1
        m_init = self.mconst
        return ceil(m_init*pow(mmul, nu))

    def calc_b(self, nu):
        """
        Compute the iteration search sample limit

        Parameters
        ----------
        nu : int
    the iteration number

    Returns
    -------
    int
    The sample limit
        """
        mmul = 1.2
        m_init = self.bconst*(self.dim - 1)
        return ceil(m_init*pow(mmul, nu))

    def remove_nlwep(self, mcS):
        """
        Remove non-LWEP's a set and return the points that cause the
        removals.

        Parameters
        ----------
        mcS : set of tuple of int
    Set of feasible points

    Returns
    -------
    lwepset : set of tuple of int
    Subset of 'mcS' which are LWEP's
    domset : set of tuple of int
    Set which causes points in 'mcS' to be removed
        """
        if not mcS:
            raise ValueError('remove_nlwep received an empty set.')
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


class RLESolver(RASolver):
    """
    Base class for Retrospective Approximation algorithm
    implementations which rely on the RLE routine for convergence.

    Attributes
    ----------
    orc : Oracle
    The problem implementation to solve
    num_calls : int
    The total number of calls to orc.g
    num_obj : int
    The number of objectives returned by orc.g
    dim : int
    The cardinality of points in the domain of orc.g
    nbor_rad : int
    The radius used to determine point neighbors, defaults is 1
    mconst : int
    Affects the iteration sample sizes. Default is 2
    bconst : int
    Affects the iteration sampling search limits.
    sprn : prng.MRG32k3a object. Default is 8.
    Pseudo-random number stream available to the solver, should
    generate independently of orc.rng. Required.
    x0 : tuple of numbers
    Vector points such that x0[0] is its first component, and
    x0[orc.dim - 1] is the last. Required.
    gbar : dict
    Dictionary of {tuple of int: tuple of float} mapping feasible
    points to their objective values. In RA algorithms, it is
    cleared every iteration.
    sehat : dict
    Like gbar, but maps feasible points to standard errors of
    the objective values.
    m : int
    Iteration sample size which is automatically updated
    b : int
    Iteration search sampling limit which is automatically updated
    nu : int
    The iteration number
    endseed : tuple of int
    The next seed to be used by 'orc.rng'
    betadel : float
    Affects the search relaxation in RLE. Defaults to 0.5.

    Parameters
    ----------
    orc : Oracle object
    kwargs : dict

    Notes
    -----
    The method accel must be implemented to use a RLESolver in
    PyMOSO.
    """

    def __init__(self, orc, **kwargs):
        self.betadel = kwargs.pop('betadel', 0.5)
        super().__init__(orc, **kwargs)

    def spsolve(self, warm_start):
        """
        Skeleton function which solve sthe sample path probem implicit
        in 'orc.g' by calling 'accel' then 'rle'.

        Parameters
        ----------
        warm_start : set of tuple of int
    Set of feasible points which solve the sample path problem
    of the previous iteration

    Returns
    -------
    ales : set of tuple of int
    Set of feasible points which solve the sample path problem
    of the current iteration
        """
        try:
            anew = self.accel(warm_start)
        except ValueError:
            # a deliberate, already-clear error (e.g. an infeasible x0,
            # raised by get_min) -- do not bury it in a generic wrapper
            raise
        except AttributeError as e:
            raise RuntimeError(
                '{0}: Unable to run accel(). Missing an import, or accel() not implemented? '
                'Message: {1}'.format(type(self).__name__, e)
            ) from e
        except ZeroDivisionError as e:
            raise RuntimeError(
                '{0}: Unable to run accel(). Message: {1}'.format(type(self).__name__, e)
            ) from e
        except TypeError as e:
            raise RuntimeError(
                '{0}: Unable to run accel(). Points must be tuples. Message: {1}'.format(type(self).__name__, e)
            ) from e
        except Exception as e:
            raise RuntimeError(
                '{0}: Unable to run accel(). Message: {1}'.format(type(self).__name__, e)
            ) from e
        ales = self.rle(anew)
        return ales

    # def accel(self, warm_start):
    #     """Accelerate RLE - Implement this function in a child class."""
    #     return warm_start

    def rle(self, mcS):
        """
        Generate an ALES from a set of feasible points

        Parameters
        ----------
        mcS : set of tuple of int
    Set of feasible points

    Returns
    -------
    mcS : set of tuple of int
    Set of feasible points which are an ALES
        """
        mcXw = {self.x0}
        # try:
        mcS = self.upsample(mcS | mcXw)
        # except TypeError:
        #     print('--* RLE Error: Failed to upsample.')
        #     print('--* Message: ', sys.exc_info()[1])
        #     print('--* Ensure accel function returns a set.')
        #     print('--* Aborting. ')
        #     sys.exit()
        # except:
        #     print('--* RLE Error: Failed to upsample.')
        #     print('--* Message: ', sys.exc_info()[1])
        #     print('--* Aborting. ')
        #     sys.exit()
        b = self.b
        n = 0
        # try:
        tmp = {s: self.gbar[s] for s in mcS | mcXw}
        # except KeyError:
        #     print('--* RLE Error: No simulated points.')
        #     print('--* Message: ', sys.exc_info()[1])
        #     print('--* Is x0 feasible?')
        #     print('--* Aborting. ')
        #     sys.exit()
        mcS = get_nondom(tmp)
        mcNnc = self.get_ncn(mcS)
        while n <= b and mcNnc:
            old_calls = self.num_calls
            mcNw, mcNd = self.remove_nlwep(mcNnc)
            mcNd -= mcS
            rlwepcalls = self.num_calls - old_calls
            mcS |= mcNw
            if not mcNw:
                mcXw = self.seek_lwep(mcNd, mcS)
                mcS |= mcXw
            tmp = {s: self.gbar[s] for s in mcS | {self.x0}}
            mcS = get_nondom(tmp)
            old_calls = self.num_calls
            mcNnc = self.get_ncn(mcS)
            ncncalls = self.num_calls - old_calls
            n += rlwepcalls + ncncalls
        return mcS

    def get_ncn(self, mcS):
        """
        Generate the Non-Conforming neighborhood of a candidate ALES.

        Parameters
        ----------
        mcS : set of tuple of int
    Set of feasible points which do not dominate each other

    Returns
    -------
    ncn : set of tuple of int
    Set of feasible points which cause mcS to not be an ALES
        """
        # initialize the non-conforming neighborhood
        ncn = set()
        #nisdom = set()
        d = self.num_obj
        r = self.nbor_rad
        dr = range(d)
        delN = get_setnbors(mcS, r)
        delzero = tuple(0 for i in dr)
        # defintion 9 (a) -- check for strict domination in the deleted nbors
        # Every deleted neighbour is estimated whatever the results
        # are, so they are estimated together.
        pairs = [(s, x) for s in mcS for x in get_nbors(s, r) - mcS]
        estimates = self.estimate_many([x for s, x in pairs])
        for (s, x), (isfeas, fx, sex) in zip(pairs, estimates):
            fs = self.gbar[s]
            ses = self.sehat[s]
            #dels = tuple(self.calc_delta(ses[i]) for i in dr)
            if isfeas:
                #delx = tuple(self.calc_delta(sex[i]) for i in dr)
                if does_strict_dominate(fx, fs, delzero, delzero):
                    ncn |= {x}
                # if does_strict_dominate(fs, fx, delzero, delzero):
                #     nisdom |= {x}
        # definition 9 (b) initialization
        candidates = list(delN - ncn)
        for x, (isfeas, fx, sex) in zip(candidates, self.estimate_many(candidates)):
            if isfeas:
                # definition 9 (b) (i) initialization
                notweakdom = True
                # definition 9 (b) (ii) initialization
                notrelaxdom = True
                # definition 9 (b) (iii) initialization
                wouldnotchange = True
                doesweakdom = False
                # set the relaxation of the neighbor
                delx = tuple(self.calc_delta(sex[i]) for i in dr)
                for s in mcS:
                    fs = self.gbar[s]
                    ses = self.sehat[s]
                    if does_weak_dominate(fx, fs, delzero, delzero):
                        doesweakdom = True
                for s in mcS:
                    fs = self.gbar[s]
                    ses = self.sehat[s]
                    # set the relaxation of the LES candidate member
                    dels = tuple(self.calc_delta(ses[i]) for i in dr)
                    # definition 9 (b) (i)
                    if does_weak_dominate(fs, fx, delzero, delzero):
                        notweakdom = False
                    # definition 9 (b) (ii)
                    if does_dominate(fx, fs, delzero, delzero) and does_weak_dominate(fs, fx, dels, delx):
                        notrelaxdom = False
                    # definition 9 (b) (iii)
                    if does_weak_dominate(fs, fx, dels, delx) or does_weak_dominate(fx, fs, delx, dels):
                        wouldnotchange = False
                # definition 9 (b)
                if notweakdom and notrelaxdom and (doesweakdom or wouldnotchange):
                    ncn |= {x}
        return ncn

    def seek_lwep(self, mcNd, mcS):
        """
        Find a sample path LWEP

        Parameters
        ----------
        mcNd : set of tuple of int
    Set of points which dominate non-conforming points
    mcS : set of tuple of int
    Set of candidate ALES points

    Returns
    -------
    mcXw : set of tuple of int
    Set of new LWEP's neither in nor dominated by members of
    mcS or mcNd.
        """
        b = self.b
        n = 0
        mcXw = set()
        xnew = set() | mcNd
        while not mcXw and n <= b:
            old_calls = self.num_calls
            mcXw, mcXd = self.remove_nlwep(xnew)
            xnew = set([x for x in mcXd])
            n += self.num_calls - old_calls
        if not mcXw:
            mcXw |= xnew
        return mcXw

    def calc_delta(self, se):
        """
        Compute the RLE parameter for the current iteration.

        Parameters
        ----------
        se : float
    Standard error of the objective value to be relaxed

    Returns
    -------
    relax : float
        """
        m = self.m
        relax = se/pow(m, self.betadel)
        return relax


class Oracle(object):
    """
    Base class to implement black-box simulations that implicitly
    define a MOSO problem.

    Attributes
    ----------
    rng : Stream object
    The stream the Oracle was constructed over. It identifies the
    selected generator (`type(self.rng)`, set_crnflag()) and supplies
    the root every coordinate is computed from (`rng.root_seed()`,
    stored as `_orc_root`). hit() never draws from it and never moves
    it: each replication's `g(x, rng)` call is handed its own fresh
    stream at that replication's coordinate (docs/rng-interface-
    design.md §12 step 9). Its state between calls means nothing to the
    framework -- MOCOMPASS, in-tree, still saves and restores it via
    getstate()/setstate() as its own attempted cross-point
    synchronization, which has no effect on what hit() draws (see
    docs/mocompass-mopbnb-known-issues.md and §4.2/§4.3).
    _iteration : int
    Count of completed _advance_iteration() calls (one per RA
    iteration). The
    `stream` half of every default- and CRN-branch coordinate: under
    crnflag=True, iteration k's replication r is drawn at
    `stream_at(_orc_root, k, r*REPL_STRIDE)` for every point (§2 --
    that sharing across points *is* what "common random numbers" means
    here); under crnflag=False, at `stream_at(_orc_root, k,
    offset_within_iteration(x, visit, r, W))`.
    _executor : executor.Executor, or None
    What actually runs replications: hit() describes each call as a
    `ReplicationBlock` and hands it over (pymoso/executor.py). Opened
    lazily, on the first hit(). By default a SerialExecutor over this
    instance -- so `g()` is called on this very object, with whatever
    state it carries; after set_simpar(n > 1), a PoolExecutor of n
    worker processes over this Oracle's class. The serial one (here,
    or inside each worker) holds the per-stream cache that keeps
    crnflag=True hit()s cheap; see SerialExecutor's own docstring
    before touching that. `None` until first needed, and again after
    mp_cleanup().
    _orc_root : tuple of int
    Fixed for the Oracle's entire lifetime (set once, in set_crnflag(),
    never reassigned) -- the reference point every hit() coordinate is
    computed from (§4.1/§4.3, §12 step 9): `rng.root_seed()`.
    crnflag : bool
    Indicates whether common random numbers is turned on or off.
    Defaults to off.
    simpar : int
    Number of processes to use when doing simulations. Defaults to 1
    dim : int
    Number of dimensions of feasible points
    num_obj : int
    Number of objectives returned by g

    Parameters
    ----------
    rng : prng.MRG32k3a object

    """

    def __init__(self, rng):
        self.rng = rng
        self.crnflag = False
        self._iteration = 0
        # commands/solve.py/testsolve.py construct a throwaway Oracle
        # over a plain random.Random() -- no root_seed() -- purely to
        # read .dim, and never call set_crnflag() on it. So nothing
        # here touches `rng`: _orc_root gets its real value in
        # set_crnflag(), which every real solve()/testsolve()/
        # mp_replicate() path calls before any hit().
        self._executor = None
        self._orc_root = None
        # §12 step 6b: the selected generator's own canonical NAME
        # (a string, not the module itself -- see the `_backend`
        # property below for why), resolved from type(self.rng) the
        # first time set_crnflag() runs (same "not dereferenced until a
        # real path sets it" posture as the three seed attributes
        # above) -- see registry.backend_for_stream.
        self._backend_name = None
        # crnflag=False continuation tracking (§4.1) -- how many
        # replications hit() has already drawn for (x, visit) within
        # the current iteration, so a repeat call gets the next
        # contiguous block instead of restarting at 0 (MOPBnB's own
        # need, see hit()). Reset whenever the iteration advances.
        self._replications_drawn = {}
        self._point_codes = {}
        # §12 step 6c/8: the oracle-role coordinate high-water mark --
        # (stream, offset), the *last* coordinate actually touched via
        # hit() (any branch) or _hit_via_coordinate, relative to
        # `_orc_root` -- see get_endseed()'s own docstring for the full
        # contract, its oracle-role-only scope, and why this tracks the
        # last touch rather than "one past" it (§3.9's stream/offset
        # split, not a flat integer, needs an explicit carry step to
        # compute "one past" safely -- pymoso.prng.base.one_past).
        # `None` means untouched. Monotonic for the Oracle's lifetime
        # (reset only in set_crnflag(), matching `_iteration`'s own
        # reset there) -- never reset by _advance_iteration(), since every
        # branch's own `stream` value only ever increases as
        # `_iteration` advances.
        self._high_water_mark = None
        super().__init__()

    @property
    def _backend(self):
        """
        The selected generator's own module (registry.GENERATORS
        lookup from `_backend_name`) -- a property, not a plain
        attribute, specifically so the stored state (`_backend_name`,
        a string) stays picklable. `testsolve`'s own `--proc` path
        ships fully-constructed Oracle instances across a process
        boundary (KNOWN_ISSUES.md issue 7's own pre-existing fragility)
        -- storing the module object directly here broke that pickling
        outright (`TypeError: cannot pickle 'module' object`, confirmed
        directly when this was first tried), not a hypothetical
        concern.
        """
        return registry.GENERATORS[self._backend_name]

    def set_simpar(self, simpar):
        """
        Choose how many processes run this Oracle's replications.

        With `simpar` of 1, replications run in this process. Above 1,
        they run on that many worker processes
        (`executor.PoolExecutor`): the workers are started on the
        first hit(), are sent this Oracle's *class*, and construct a
        fresh instance per replication -- so a problem whose `g()`
        depends on per-instance state set after construction cannot
        use it.

        Parameters
        ----------
        simpar : int
            Number of processes to use when performing simulation replications.

        Returns
        -------
        Oracle
            self, so this doubles as a context manager: `with
            orc.set_simpar(n):` guarantees mp_cleanup() runs via
            __exit__ on every exit path (normal return, exception, or
            KeyboardInterrupt), not only when the caller's own code
            happens to reach an explicit mp_cleanup() call.

        Raises
        ------
        ValueError
            `simpar` is above 1 and this Oracle's class cannot be sent
            to a worker process (executor.ClassRef). Raised here,
            before any worker exists.
        """
        self._close_executor()
        self._class_handle = ClassHandle(type(self)) if simpar > 1 else None
        self.simpar = simpar
        return self

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._close_executor(abandon=exc_type is not None)
        return False


    def mp_cleanup(self):
        """
        Stop whatever is running this Oracle's replications, worker
        processes included. Call this after simulation is complete, or
        use `with orc.set_simpar(n):`. A later hit() starts again.
        """
        self._close_executor()


    def set_crnflag(self, crnflag):
        """
        Set the common random number (crn) flag and initialize the
        iteration baseline.

        Also resolves `self._backend` (the selected generator's own
        module, from `type(self.rng)`, §12 step 6b) -- set_crnflag() is
        this class's own authoritative initialization point (see
        `_orc_root`'s own comment below). Every registered generator
        supports both crnflag values (§12 step 9).

        Parameters
        ----------
        crnflag: bool
        """
        self.crnflag = crnflag
        backend = registry.backend_for_stream(self.rng)
        self._backend_name = registry.GENERATOR_NAMES[backend]
        self._iteration = 0
        self._close_executor()
        # Fixed for the Oracle's lifetime, unlike `_iteration` above:
        # the reference point every coordinate -- default, CRN, visit=
        # and sync= alike -- is computed from (docs/rng-interface-
        # design.md §4.1/§4.3, §12 step 9). Captured here rather than in
        # __init__ because set_crnflag() is the authoritative
        # initialization point in every real solve()/testsolve()/
        # mp_replicate() call path (see __init__).
        #
        # root_seed(), not get_seed(): the value _hit_via_coordinate
        # passes as stream_at's own base_seed (§12 step 6b) -- for the
        # MRG family these are identical (a raw seed already is a valid
        # stream_at base), but not for Philox, whose get_seed() returns
        # its own full (key, counter, buffer) state, not the 2-tuple
        # base key stream_at expects. See root_seed()'s own docstring
        # on each backend's Stream class.
        self._orc_root = self.rng.root_seed()
        self._replications_drawn = {}
        self._point_codes = {}
        self._high_water_mark = None

    def _touch_coordinate(self, stream, offset):
        """
        Record that the oracle-role coordinate `(stream, offset)` --
        relative to `_orc_root` -- has now been touched: the *last* raw
        position a replication's own reserve could actually have
        reached, not "one past" it. Called once per hit() replication
        block, from every branch that computes a coordinate (§12 step 8).

        §12 step 6b: takes `(stream, offset)` directly now, computed by
        the caller against the selected backend's own `OFFSET_CAPACITY`
        -- not a flat integer this method itself divmods by a hardcoded
        `ITER_STRIDE`, which only the MRG family has at all (§3.9:
        Philox's own coordinate is two-dimensional natively, no
        flattening step to invert). Every caller already computes
        `(stream, offset)` this way now (`_hit_via_coordinate`'s own
        `divmod(offset + m*stride - 1, backend.OFFSET_CAPACITY)`, for
        every branch -- the CRN branch's `(self._iteration,
        m*REPL_STRIDE - 1)` is that same expression at `offset = 0`,
        §12 step 9) -- this method
        only ever compares and stores the pair.

        Storing the last position touched, rather than "one past" it
        directly, is deliberate (a change from this method's own
        earlier, flat-integer form): computing "one past" is now a
        carry operation (`pymoso.prng.base.one_past`), done once at
        `get_endseed()` time, where the carry's own safety can be
        checked explicitly -- see that method's own docstring for why.

        The sync branch's own `stream` (at or above
        `backend.SYNC_ZONE_STREAM_START`) sorts correctly, automatically,
        above any default/CRN-branch touch by plain tuple comparison,
        without this method needing to know which branch called it.

        Parameters
        ----------
        stream : int
            Non-negative.
        offset : int
            Non-negative.
        """
        candidate = (stream, offset)
        if self._high_water_mark is None or candidate > self._high_water_mark:
            self._high_water_mark = candidate

    def get_endseed(self):
        """
        A stream guaranteed not to overlap anything this Oracle has
        actually handed to `g()` so far -- §8.2's high-water-mark
        `endseed` (docs/rng-interface-design.md), replacing
        `crn_advance()`'s own call-count-only reporting (`_iteration *
        ITER_STRIDE`), which lost real information (confirmed
        empirically: MOCOMPASS and MOPBnB used to report identical
        `endseed`s for verified-different consumption).

        **Oracle-role only** (§8.2's own explicit scoping, not "every
        role" a run touches): a solver's own draws -- `RASolver`'s
        `sprn`/`solvprn`/`xprn`, `RLESolver`'s equivalents -- are not
        coordinate-based yet (no onboarded generator's `stream_at`
        covers solver-role today), and are a structurally separate
        concern from what this method can see: `solvprn` is an ordinary
        `MRG32k3a` stream, advanced one raw draw at a time the way
        `random.Random` always has been, so reaching the coordinate
        region oracle-role coordinates occupy (`ITER_STRIDE = 2**127`
        and up, per iteration) would take on the order of 2**127
        ordinary draws -- not reachable in practice, but a real
        limitation of this method's guarantee, not covered tracking
        described as "every role." A caller relying on `get_endseed()`
        to also bound solver-role consumption would be relying on
        something this method does not actually provide.

        **The carry, proven safe before use, not assumed** (§12 step
        6c): `_high_water_mark` stores the last coordinate genuinely
        touched, as `(stream, offset)`; the seed returned must be one
        past it -- `pymoso.prng.base.one_past(stream, offset,
        offset_capacity, stream_family_capacity)`, which raises
        `StreamFamilyExceeded` rather than silently landing in a
        different, already-allocated family's own territory (the same
        class of defect `MAX_RI`'s unenforced silent overlap was). The
        family capacity depends on which zone the touch's own `stream`
        falls in, both inside this isp path's own slot: below
        `SYNC_ZONE_STREAM_START`, it's the default/CRN zone, bounded by
        `ISP_ITER_MARGIN` (carrying past it would land in this path's
        own sync zone); at or above it, it's the sync zone, bounded by
        `ISP_STREAM_SPAN` (carrying past it would land in the *next*
        isp path's slot). The sync zone used to be left unbounded
        (`None`), which was only defensible while it lay outside every
        slot -- the defect described at `SYNC_ZONE_STREAM_START`'s own
        definition (mrg32k3a.py). An untouched
        Oracle (`_high_water_mark is None`) returns `_orc_root` itself,
        with no carry computed at all -- there is nothing to be "one
        past" yet.

        Returns
        -------
        tuple of int
            A seed safely past everything this run's own oracle-role
            coordinates touched -- safe to hand to independent,
            unrelated work (e.g. a fresh `MOSOSolver` run).

        Raises
        ------
        StreamFamilyExceeded
            The carry would land in a different family's own reserved
            territory (see above) -- pathological, not reachable by
            any realistic run under MRG32k3a's own margins, but checked
            rather than assumed.
        """
        if self._high_water_mark is None:
            return self._orc_root
        stream, offset = self._high_water_mark
        backend = self._backend
        family_capacity = backend.ISP_ITER_MARGIN if stream < backend.SYNC_ZONE_STREAM_START else backend.ISP_STREAM_SPAN
        next_stream, next_offset = one_past(
            stream, offset, offset_capacity=backend.OFFSET_CAPACITY, stream_family_capacity=family_capacity
        )
        return backend.stream_at(self._orc_root, next_stream, next_offset).get_seed()

    def get_high_water_mark(self):
        """
        The `(stream, offset)` pair `get_endseed()` derives its seed
        from -- `_high_water_mark`, relative to `_orc_root`, or `None`
        if this Oracle has never touched a coordinate. Exists for
        `testsolve()`'s own cross-path aggregation (docs/rng-interface-
        design.md §12 step 8 stage 2): each `isp` path's `Oracle` runs
        in its own process under `--proc`/`--simpar`, so only picklable
        result-dict values -- not the live `Oracle` object `get_endseed()`
        itself needs -- survive back to the caller. `RASolver.solve`
        (and MOCOMPASS/MOPBnB's own `solve()`) return this value in
        their result dict for exactly that reason. Not part of any
        per-path public seed contract on its own -- `get_endseed()`
        remains the one meaningful seed for a single path; this is
        raw material for combining several.

        Returns
        -------
        tuple of (int, int), or None
        """
        return self._high_water_mark

    def _advance_iteration(self):
        """
        Advance to the next RA iteration. Every default- and CRN-branch
        coordinate carries `_iteration` as its `stream`, so this one
        increment moves both branches to a stream disjoint from every
        earlier iteration's: iteration k's CRN baseline is
        `stream_at(_orc_root, k, 0)`, i.e. `orc_root + k*2**127` for the
        MRG family (docs/rng-interface-design.md §2).

        Also resets `_replications_drawn` (hit()'s crnflag=False
        continuation tracking, §4.1): a new iteration's coordinate space
        is disjoint from the last one's, so no continuation state from
        the previous iteration could be meaningful here even if kept.
        The executor's base-stream cache is keyed on `(root, stream)`,
        and `stream` is `_iteration`, so it needs no reset here -- the
        next hit() simply asks for a different stream.

        §12 step 9: this used to jump `rng` itself one ITER_STRIDE
        forward and re-read `_iteration_baseline_seed`/`_next_seed` from
        it, a second, stateful implementation of the position
        `stream_at` computes directly. That model is gone; nothing here
        touches `rng`, for either crnflag value or any generator.

        Framework bookkeeping, not solver API: RASolver.rasolve()
        calls this once per RA iteration, and nothing else should. It
        was public as `crn_advance()` until docs/rng-interface-
        design.md §11 open question 7 was carried out -- removed
        outright, no deprecated alias, because the one way real solvers
        used it (MOCOMPASS and MOPBnB, once, at the end of solve()) did
        nothing useful and looked like CRN support it did not provide
        (§4.2). A custom MOSOSolver that called `orc.crn_advance()`
        should delete that line; nothing replaces it.
        """
        self._iteration += 1
        self._replications_drawn = {}
        self._point_codes = {}

    def _record_point_code(self, code, x):
        """
        Collision detection for the default branch's point codes: note
        that `x` was coded as `code` in the current iteration, and raise
        if a *different* point already holds that code.

        Needed because `encode_point` is no longer injective: a point
        too large for the exact positional code is hashed into the same
        field (pymoso/prng/base.py). Exact codes cannot collide with
        each other, but a hashed code can coincide with another hashed
        code or with an exact one, so every code is recorded, not only
        hashed ones. With this check a run is still "correct or
        raises": two points are never silently handed the same
        replication streams.

        `_point_codes` maps code -> point for the current iteration
        only. It is reset in `_advance_iteration()`, because the next
        iteration draws from a different stream, where the same code is
        a different position. Its size is the number of distinct points
        hit on the default branch this iteration -- the same order as
        `_replications_drawn`, which already holds one entry per point.

        **Where the check is exhaustive.** Point codes are computed in
        exactly one place, `_hit_via_coordinate`'s default branch, in
        the process that owns this Oracle, and every one passes through
        here first. `visit != 0` uses the same code and is covered. The
        CRN and sync branches put no point in the coordinate and have
        nothing to collide. Under `--simpar`, workers never compute
        coordinates -- this process computes every seed and queues
        `(x, seed)` -- so this one record sees every point. Under
        `--proc`, each isp path has its own Oracle and its own record,
        and also its own slot of streams: the same code on two paths is
        two different positions, so there is no cross-path collision to
        miss.

        **Three ways around it, none new, written down so they are not
        rediscovered:**

        1. Code that calls a backend's `stream_at`,
           `offset_within_iteration` or `offset_from_point_code`
           directly, instead of `hit()`. Nothing here sees those
           coordinates.
        2. A subclass that overrides `hit()` or `_hit_via_coordinate`
           and computes coordinates itself.
        3. Two Oracles constructed over the same root in one process.
           Each keeps its own record; they draw from the same streams.

        The first and third were equally unguarded when the code was
        exact: an exact code only ever promised distinct points
        distinct positions *within one Oracle's own hit() calls*. This
        check is no weaker than `PointCodeOverflow`'s guard was; it has
        the same scope.

        Parameters
        ----------
        code : int
        x : tuple of int

        Raises
        ------
        PointCodeCollision
        """
        seen = self._point_codes.get(code)
        if seen is None:
            self._point_codes[code] = tuple(x)
        elif seen != tuple(x):
            raise PointCodeCollision(
                'points {0} and {1} both map to point code {2} in RA '
                'iteration {3} and would share replication streams. At '
                'least one is too large for the exact positional code '
                '(dim={4}) and was hashed. Use crn=True, or reduce the '
                'dimension or magnitude of the points. See docs/rng-'
                'interface-design.md §3.4.'.format(seen, tuple(x), code, self._iteration, len(x))
            )

    def _get_executor(self):
        """
        The executor that runs this Oracle's replications, opened on
        first use: a `SerialExecutor` over this very instance
        (`InProcessHandle(self)`), or -- after `set_simpar(n)` with n
        above 1 -- a `PoolExecutor` of n workers over this Oracle's
        class.

        Lazy because `set_crnflag()` is what fixes the generator, and
        it runs after construction. It is dropped (`_close_executor`)
        by `set_crnflag()`, `set_simpar()` and `mp_cleanup()`, and
        reopened on the next hit() if there is one.

        Returns
        -------
        executor.Executor
        """
        if self._executor is None:
            handle = getattr(self, '_class_handle', None)
            if handle is not None:
                self._executor = PoolExecutor(self.simpar).open(handle, self._backend_name)
            else:
                self._executor = SerialExecutor().open(InProcessHandle(self), self._backend_name)
        return self._executor

    def _close_executor(self, abandon=False):
        """`abandon`: do not wait for work in progress (an exception is
        propagating)."""
        executor = getattr(self, '_executor', None)
        self._executor = None
        if executor is not None:
            if abandon:
                executor.__exit__(Exception, None, None)
            else:
                executor.close()

    def __getstate__(self):
        # An Oracle is plain data plus, possibly, live worker
        # processes. A copy does not get the processes; it opens its
        # own executor on its first hit().
        state = self.__dict__.copy()
        if isinstance(state.get('_executor'), PoolExecutor):
            state['_executor'] = None
        return state

    def _hit_via_coordinate(self, x, m, visit, sync, start_replication=0, crn=False):
        """
        The explicit-coordinate replication path (docs/rng-interface-
        design.md §4.1/§4.3), computed fresh from the Oracle's fixed
        `_orc_root` -- the one path every hit() call runs through, for
        every branch (§12 step 9). Never touches `rng`.

        This method computes *where* the block is and checks that it is
        allowed to be there; it does not run anything. It builds a
        `ReplicationBlock` -- point, root, `(stream, offset)`, stride,
        count -- and hands it to the executor (pymoso/executor.py),
        which turns the coordinate into streams and calls `g()`.
        Aggregating the results into a mean and standard error happens
        back here.

        Three coordinate shapes, one loop:

        - default (`sync is None`, `crn` False): `stream = _iteration`,
          `offset = offset_within_iteration(x, visit, replication, W)`,
          replications `REPL_RESERVE_STRIDE` apart.
        - CRN (`crn` True): `stream = _iteration`, `offset =
          replication*REPL_STRIDE` -- the default branch's stream with
          the point and visit terms dropped (CRN is point-independent by
          construction, §2) and the sync branch's wide stride. The
          block starts at offset 0 of the iteration's stream, which
          the executor has cached -- that, not a fresh jump from the
          root per call, is why a CRN hit() is cheap.
        - sync (`sync` an int): the caller-chosen axis, below.

        §12 step 6b: generalized off the MRG-only mechanism step 6c left
        in place (raw jump_seed_n chaining on a bare seed tuple, then
        constructing `MRG32k3a(s)` directly per replication -- both
        MRG-shaped, neither expressible for Philox, which has no
        jump-ahead and builds its stream from `(key, counter)`, not a
        flat seed). The offset/default branch (`sync is None` --
        every ordinary `hit()` call, visit!=0 included: `visit` is just
        a parameter of `offset_within_iteration`, not a separate
        formula) now computes `stream = self._iteration`, `offset =
        self._backend.offset_within_iteration(...)` directly -- no
        flattening through an `ITER_STRIDE`-sized `base` integer at all,
        since `stream`/`offset` were always the two dimensions §3.9
        already named; the flattening was legacy structure from before
        that split existed, not something intrinsic to the computation.
        The sync branch is two-dimensional too: `stream =
        SYNC_ZONE_STREAM_START + sync // SYNC_PER_STREAM`, inside this
        isp path's own slot, with `SYNC_PER_STREAM` sync values sharing
        a stream -- see the selected backend's own constants for the
        sizing, and mrg32k3a.py for the defect the nesting fixes.

        Three callers, unified here on purpose (docs/rng-interface-
        design.md §12 step 4a's own convergence note, completed by step
        9): hit()'s own `crnflag=True` path (`crn=True`,
        `start_replication` always 0 -- every CRN hit() restarts at the
        iteration baseline, which is what makes the streams common
        across points); hit()'s explicit
        `visit!=0`/`sync=<int>` arguments (`start_replication` always 0
        there -- no continuation concept for an explicitly independent
        block, or for a solver-controlled sync axis whose own caller,
        e.g. MOCOMPASS's `nx[x]`, already encodes "which block"), and
        hit()'s own default `crnflag=False` path (step 4b's cutover --
        `start_replication` tracked automatically by hit() itself, per
        `(x, visit)`, across calls within one iteration, §4.1).

        Advances via a real per-replication `Stream.advance(stride)`
        call on both branches, not a fresh `stream_at` call per
        replication (the expensive, ~127-round binary exponentiation
        step 2's own commit found and fixed as a regression for MRG,
        and would be for any backend -- `advance`'s own contract exists
        specifically so this stays O(1) per replication generically,
        not just for MRG's own cached jump_seed_n fast path; timed
        directly against this step's own before/after, not assumed --
        see docs/rng-interface-design.md §12 step 6b). The sync
        branch's replication term is `replication*REPL_STRIDE` (§4.3's
        own formula -- the same spacing the CRN branch uses); the
        offset/default branch's is `replication*2**REPL_RESERVE_BITS`
        (base.py's offset_within_iteration) -- this branch used to
        advance via a single raw mrg32k3a() step instead (no reserve at
        all), a defect found ahead of §12 step 8 (docs/rng-interface-
        design.md's step 8 prerequisite writeup): a g() call drawing
        more than one raw value (every built-in problem) ran its own
        consumption into the position reserved for the next
        replication, so replications were not actually independent.
        The executor still enforces the reserve at runtime
        -- raising ReplicationDrawOverflow if a single replication
        draws more than 2**REPL_RESERVE_BITS raw values (this
        generator's own REPL_RESERVE_BITS, per §12 step 6c-completion's
        own finding that this check was comparing against a hardcoded,
        MRG-shaped budget regardless of which backend was selected) --
        via `Stream.raw_consumed()` now (§12 step 6b), replacing the
        removed set_class_cache()/.generate monkeypatch, which reached
        into an MRG-only attribute no other backend has. Enforced
        under simpar>1 too: the check runs wherever the replication
        does, in the worker, and the exception comes back.

        Parameters
        ----------
        x : tuple of int
        m : int
        visit : int
        sync : int or None
        start_replication : int
            Non-negative. Which replication index this call's block
            starts at.
        crn : bool
            True for hit()'s own `crnflag=True` path. Requires `sync is
            None` and `visit == 0`; `x` is not part of the coordinate.

        Returns
        -------
        isfeas, obmean, obse : as hit()

        Raises
        ------
        ReplicationDrawOverflow
            A single replication drew more raw values than its
            reserved block holds.
        ReplicationOverflow
            The block's last replication index is past the selected
            backend's `REPL_COUNT_LIMIT`.
        IterationOverflow
            `_iteration` has reached the backend's `ISP_ITER_MARGIN`
            (default and CRN branches).
        SyncOverflow
            `sync` is at or past the backend's `SYNC_CAPACITY`.
        """
        block = self._block_for(x, m, visit, sync, start_replication, crn)
        return self._aggregate(self._get_executor().run([block])[0])

    def _block_for(self, x, m, visit, sync, start_replication=0, crn=False):
        """
        The "where" half of `_hit_via_coordinate` (see its docstring):
        check that the block may be where it is, record it in the
        high-water mark and the point-code table, and return it as a
        `ReplicationBlock`. Nothing is run.
        """
        backend = self._backend
        # Every axis raises at its own boundary, before anything is
        # drawn -- nothing below wraps or spills into a neighbouring
        # zone (docs/rng-interface-design.md, the SYNC_ROLE_OFFSET/
        # ISP_STRIDE entry). offset_within_iteration checks the default
        # branch's *first* replication index itself; this covers the
        # block's last one, and the CRN and sync branches, which have
        # no other check.
        if start_replication + m > backend.REPL_COUNT_LIMIT:
            raise ReplicationOverflow(
                'replications {0}..{1} of x={2} do not fit under this '
                'generator\'s limit of {3} replications per block. See '
                'docs/rng-interface-design.md §3.4.'.format(
                    start_replication, start_replication + m - 1, x, backend.REPL_COUNT_LIMIT
                )
            )
        if sync is None and self._iteration >= backend.ISP_ITER_MARGIN:
            raise IterationOverflow(
                'RA iteration {0} is past the {1} iterations one '
                'independent sample path reserves under {2}; the next '
                'stream belongs to the sync zone. A run that terminates '
                'normally cannot get here -- check that every iteration '
                'of the solver consumes simulation budget '
                '(KNOWN_ISSUES.md issue 13).'.format(
                    self._iteration, backend.ISP_ITER_MARGIN, self._backend_name
                )
            )
        if sync is not None:
            if sync >= backend.SYNC_CAPACITY:
                raise SyncOverflow(
                    'sync={0} does not fit in the {1} sync values one '
                    'independent sample path reserves under {2}. See '
                    'docs/rng-interface-design.md §4.3.'.format(
                        sync, backend.SYNC_CAPACITY, self._backend_name
                    )
                )
            # Two-dimensional like every other coordinate (§3.9):
            # SYNC_PER_STREAM sync values share a stream, inside this
            # path's own sync zone. For the MRG family this flattens to
            # exactly §4.3's `SYNC_ROLE_OFFSET + sync*SYNC_STRIDE +
            # replication*REPL_STRIDE`.
            stride = backend.REPL_STRIDE
            stream = backend.SYNC_ZONE_STREAM_START + sync // backend.SYNC_PER_STREAM
            offset = (sync % backend.SYNC_PER_STREAM) * backend.SYNC_STRIDE + start_replication * stride
        elif crn:
            stride = backend.REPL_STRIDE
            stream = self._iteration
            offset = start_replication * stride
        else:
            # encode_point: the exact positional code when x fits, a
            # hash when it does not (a high-dimensional problem). Either
            # way the code is checked against every other point this
            # iteration has used before anything is drawn.
            code, _hashed = backend.encode_point(x)
            self._record_point_code(code, x)
            stream = self._iteration
            offset = backend.offset_from_point_code(code, visit, start_replication)
            stride = backend.REPL_RESERVE_STRIDE
        # Work as data. `stride` is also each replication's reserve:
        # how many raw values its g() may draw before running into the
        # next replication's start -- the executor checks it on every
        # branch; only the default branch's is small enough to reach.
        block = ReplicationBlock(x=x, root=self._orc_root, stream=stream, offset=offset, stride=stride, count=m)
        # §12 step 8: this block's own replications span
        # [offset, offset + m*stride) relative to `stream` -- see
        # _touch_coordinate's own docstring for why the last position
        # actually touched is offset + m*stride - 1, not offset +
        # m*stride. Carried into `stream + extra_stream` generically via
        # this backend's own OFFSET_CAPACITY (ITER_STRIDE for the MRG
        # family; Philox's own, smaller, real capacity), not a
        # hardcoded ITER_STRIDE -- the same per-generator-budget fix
        # §12 step 6c-completion made for offset_within_iteration
        # itself.
        extra_stream, last_offset = divmod(offset + m * stride - 1, backend.OFFSET_CAPACITY)
        self._touch_coordinate(stream + extra_stream, last_offset)
        return block

    def _aggregate(self, replications):
        """
        One block's replications as hit() reports them.

        Parameters
        ----------
        replications : list of executor.Replication

        Returns
        -------
        isfeas, obmean, obse : as hit()
        """
        m = len(replications)
        dr = range(self.num_obj)
        mr = range(m)
        feas = [replication.isfeas for replication in replications]
        objm = [replication.objectives for replication in replications]
        isfeas = False
        obmean = []
        obse = []
        if all(feas):
            isfeas = True
            if m == 1:
                # matches the default path's own m==1 special case:
                # statistics.variance() requires at least two points.
                obmean = objm[0]
                obse = [0 for o in objm[0]]
            else:
                obmean = tuple([mean([objm[i][k] for i in mr]) for k in dr])
                obvar = [variance([objm[i][k] for i in mr], obmean[k]) for k in dr]
                obse = tuple([sqrt(obvar[i]/m) for i in dr])
        return isfeas, obmean, obse

    def hit(self, x, m, visit=0, sync=None):
        """
        Generate the means and standard errors of 'm' simulation
        replications at point 'x'.

        Parameters
        ----------
        x : tuple of int
    point at which to simulate
    m : int
    number of replications to simulate 'x'
    visit : int
    Optional, default 0. Nonzero requests an independent resample
    block for this (x, visit) pair, bypassing the default per-point
    continuation (docs/rng-interface-design.md §4.1). Additive: at
    the default 0, hit()'s behavior is exactly as before this
    parameter existed.
    sync : int or None
    Optional, default None. A non-negative int hands the coordinate's
    synchronization axis to the caller entirely, excluding `x`/`visit`
    (§4.3) -- for a solver implementing its own cross-point CRN
    policy. Additive: at the default None, hit()'s behavior is
    exactly as before this parameter existed. Passing both `sync` and
    a non-default `visit` raises ValueError.

        Returns
        -------
        isfeas : bool
    indicates the feasibility of 'x'
        obmean : tuple of float
    mean of each objective of 'm' simulations
        obse : tuple of float
    mean of standard errors of each objective of 'm' simulations

        Notes
        -----
        Every branch routes through `_hit_via_coordinate` (docs/rng-
        interface-design.md §12 step 9). crnflag=True: every call
        restarts at the iteration's baseline, replications REPL_STRIDE
        apart, the same streams for every point (§2's formula,
        bit-identical to the mutable-`rng` mechanism it replaced --
        tests/test_oracle_coordinate_migration.py). crnflag=False
        (docs/rng-interface-design.md §12 step
        4b): coordinate-derived, order-independent by construction --
        different points visited in any order within one iteration no
        longer share a mutable walk position at all. Continuation
        across repeated calls to the same (x, visit) within one
        iteration (§4.1, needed by MOPBnB) is tracked here, in
        `_replications_drawn`, reset whenever `_iteration` advances
        (_advance_iteration()) -- not inside `_hit_via_coordinate` itself,
        since a genuinely opt-in `visit!=0`/`sync=<int>` call never
        continues automatically (a fresh independent block, or a
        solver-controlled axis that already encodes "which block"
        itself).
        """

        block = self._plan_hit(x, m, visit, sync)
        return self._aggregate(self._get_executor().run([block])[0])

    def hit_many(self, requests):
        """
        The same results as `[self.hit(x, m) for x, m in requests]`,
        with every replication of every request handed to the executor
        together.

        Under `set_simpar(n)` that is the difference between n workers
        sharing one point's `m` replications and sharing all of them
        (docs/simpar-ceiling.md). Serially there is no difference at
        all. It is safe because a replication's stream is a function
        of its coordinate, not of the order replications run in.

        A point that appears twice gets two consecutive blocks, as two
        hit() calls would give it (crnflag=False), or the same block
        twice (crnflag=True).

        Parameters
        ----------
        requests : iterable of (tuple of int, int)
            `(x, m)` pairs.

        Returns
        -------
        list of (isfeas, obmean, obse)
            One per request, in order, each as hit() returns it.
        """
        blocks = [self._plan_hit(x, m) for x, m in requests]
        if not blocks:
            return []
        return [self._aggregate(replications) for replications in self._get_executor().run(blocks)]

    def _plan_hit(self, x, m, visit=0, sync=None):
        """hit()'s argument checks and coordinate bookkeeping, without
        running anything: the block a hit(x, m, visit, sync) call made
        now would run. Advances the per-point continuation."""
        assert(m >= 1)
        if sync is not None:
            if visit != 0:
                raise ValueError(
                    'hit() cannot take both sync and a non-default visit -- '
                    'sync already selects the coordinate axis; there is no '
                    'sensible way to also apply visit\'s per-point escape '
                    'hatch on top of it. See docs/rng-interface-design.md §4.3.'
                )
            if sync < 0:
                raise ValueError('sync must be non-negative, got {0}'.format(sync))
        if visit < 0:
            raise ValueError('visit must be non-negative, got {0}'.format(visit))
        if sync is not None or visit != 0:
            return self._block_for(x, m, visit, sync)

        if not self.crnflag:
            key = (x, visit)  # visit == 0 here, always
            start = self._replications_drawn.get(key, 0)
            block = self._block_for(x, m, visit, None, start_replication=start)
            self._replications_drawn[key] = start + m
            return block

        return self._block_for(x, m, 0, None, crn=True)

    def g(self, x, rng):
        """
        Generate a single replication at point `x`.

        Parameters
        ----------
        x : tuple
        rng : random.Random object

        Returns
        -------
        bool
            Indicates feasibility of `x`
        tuple of float
            The simulated values for each objective
        """
        raise NotImplementedError
