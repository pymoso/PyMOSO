#!/usr/bin/env python
"""
Provide base classes and supporting functions for problem  and solver
implementations.

The solver bases are defined here, with the functions behind a
solver's `PARAMS`. `Oracle` is defined in pymoso.oracle and imported
here, so that `from pymoso.chnbase import Oracle` remains the
documented path.

Listing
--------------
accepted_params, function
reject_unknown_params, function
WarmStartInfeasible(RuntimeError), class
MOSOSolver(object), class
RASolver(MOSOSolver), class
RLESolver(RASolver), class
Oracle(object), class (from pymoso.oracle)
"""
from math import ceil, floor
from .oracle import Oracle
from .moso import perturb, argsort, enorm, get_setnbors, get_nbors, is_lwep, get_nondom, does_strict_dominate, does_weak_dominate, does_dominate


def accepted_params(solver):
    """
    The parameter names a solver class says it takes: the `PARAMS` of
    the class and of every class it inherits from.

    Parameters
    ----------
    solver : MOSOSolver class

    Returns
    -------
    list of str
        Sorted.
    """
    names = set()
    for cls in solver.__mro__:
        names.update(vars(cls).get('PARAMS', ()))
    return sorted(names)


def reject_unknown_params(solver, leftover):
    """
    Raise if a solver was given parameters nobody took.

    Call it from a solver's `__init__` after every parameter the
    solver understands has been popped from its keyword arguments. A
    parameter left over is one no class in the solver's hierarchy
    knows: a misspelling, or a parameter of some other solver. It used
    to be dropped without a word, so a run with `betaesp=0.4` ran with
    the default `betaeps` and said nothing.

    Parameters
    ----------
    solver : MOSOSolver object
    leftover : dict
        What remains of the keyword arguments.

    Raises
    ------
    TypeError
    """
    if not leftover:
        return
    accepted = accepted_params(type(solver))
    raise TypeError(
        '{0} was given {1} it does not have: {2}. It takes: {3}.'.format(
            type(solver).__name__,
            'a parameter' if len(leftover) == 1 else 'parameters',
            ', '.join(sorted(leftover)),
            ', '.join(accepted) if accepted else 'none',
        )
    )


def _toggle(name, value):
    """
    A solver parameter that is on or off: 0 or 1, as `solve()` and the
    CLI's `--param` pass every parameter, as a float.

    Raises
    ------
    ValueError
        `value` is anything other than 0 or 1.
    """
    if value not in (0, 1):
        raise ValueError('{0} is a toggle: 0 (off) or 1 (on), not {1!r}.'.format(name, value))
    return bool(value)


_INT32_MIN = -2 ** 31
_INT32_MAX = 2 ** 31 - 1


def _matlab_int32(v):
    """
    MATLAB's int32() of a double: rounded half away from zero (Python's
    round() rounds half to even), saturated at the int32 limits, and 0
    for NaN. NE's quadratic candidate casts its vertex with it.
    """
    if v != v:          # NaN
        return 0
    if v >= _INT32_MAX:
        return _INT32_MAX
    if v <= _INT32_MIN:
        return _INT32_MIN
    av = abs(v)
    r = floor(av)
    # av - r is exact, so this rounds 0.49999999999999994 down, where
    # floor(av + 0.5) would not
    if av - r >= 0.5:
        r += 1
    r = int(r) if v >= 0 else -int(r)
    return min(_INT32_MAX, max(_INT32_MIN, r))


def _quadratic_coordinate(xi, y1, y2, y3):
    """
    One coordinate of NE's quadratic candidate (docs/RSPLINE.m, lines
    275-289): the vertex of the parabola through x_i - 1, x_i, x_i + 1,
    where it is convex.

    Parameters
    ----------
    xi : int
        The centre's coordinate.
    y1, y3 : float or None
        The objective at x + e_i and at x - e_i; None if infeasible,
        and then there is no fit.
    y2 : float
        The objective at the centre.

    Returns
    -------
    int
    """
    xq = xi
    if y1 is not None and y3 is not None:
        a = (y1 + y3) / 2.0 - y2
        b = (y1 - y3) / 2.0
        if a - 0.00005 > 0:
            xq = _matlab_int32(xi - (b / (a + a)))
    # Deliberately the MATLAB's behaviour, not an oversight: a
    # coordinate that fails this guard is 0, not the centre's value.
    # ixquad starts as zeros (line 230) and is written only when the
    # guard passes (lines 287-288), so falling back to the centre covers
    # only the non-convex and infeasible cases.
    if abs(xq) < 2147483646.0:
        return xq
    return 0


class WarmStartInfeasible(RuntimeError):
    """
    Raised when a point a solver carried into an RA iteration as
    feasible is estimated infeasible there.

    The invariant: a warm start is the previous iteration's solution,
    every point of which that iteration estimated feasible, and the
    starting point x0 was estimated feasible in iteration 1. When the
    oracle decides feasibility from x alone, re-estimating those points
    at a larger sample size cannot find them infeasible. Nothing is
    being estimated about their feasibility; it is inherited.

    It holds for algorithms whose sample-path problems take the
    feasible set as given: R-SPLINE, R-PE, R-PERLE and R-MinRLE raise
    this. `RASolver` itself does not, because an algorithm with random
    constraints could legitimately meet an infeasible warm start and
    have its own way to handle it. A solver of your own may raise it
    if the invariant is one its algorithm relies on.

    In iteration 1 the warm start is x0 itself, the caller's point,
    and an infeasible x0 there is reported as a `ValueError`.

    Attributes
    ----------
    points : tuple of tuple
        The points found infeasible, in sorted order
    iteration : int
        The iteration that found them infeasible
    solver : str
        The solver's class name
    """

    def __init__(self, points, iteration, solver):
        self.points = tuple(points)
        self.iteration = iteration
        self.solver = solver
        first = self.points[0]
        others = len(self.points) - 1
        super().__init__(
            '{0}: the point {1}{2}, carried into iteration {3} as feasible, '
            'was estimated infeasible there. The likeliest cause is a g() whose '
            'feasibility depends on its random numbers rather than on x alone, '
            'which {0} does not support. If your g() decides feasibility from '
            'x alone, this cannot happen and indicates a defect in PyMOSO; '
            'please report it.'.format(
                solver, first,
                ' (and {0} other{1})'.format(others, 's' if others > 1 else '') if others else '',
                iteration))

    def __reduce__(self):
        # so that it reaches the parent intact from a --proc worker
        return (type(self), (self.points, self.iteration, self.solver))


def _check_warm_start(solver, points):
    """
    Raise WarmStartInfeasible if, after iteration 1, any of `points`
    (a warm start, with x0 where the solver carries it) is not among
    this iteration's feasible estimates. The caller has already
    estimated them at this iteration's sample size; nothing is
    simulated here. In iteration 1 the warm start is the caller's x0,
    and an infeasible x0 is left to the ValueError that reports it.
    """
    if solver.nu <= 1:
        return
    infeasible = [x for x in points if x not in solver.gbar]
    if infeasible:
        raise WarmStartInfeasible(sorted(infeasible), solver.nu, type(solver).__name__)


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
    x0 : tuple, optional
        The starting point. `solve()` and `testsolve()` always pass it.
    sprn : the solver's own stream, optional
        Always passed by `solve()` and `testsolve()`.
    **kwargs
        Anything else is a parameter no class in the solver's hierarchy
        took, and raises `TypeError` naming it.

    Notes
    -----
    The solve attribute must be implemented in sub-classes for use in
    PyMOSO.

    A sub-class need not use `x0` or `sprn`, nor take them itself. One
    that does -- removing them from its keyword arguments and setting
    `self.x0`/`self.sprn` before calling this -- keeps its values, as
    `RASolver` and every solver written for 1.x does. Until 2.0 this
    method took only the oracle, so a sub-class that did not take both
    itself could not be run at all.
    """

    def __init__(self, orc, **kwargs):
        for name in ('x0', 'sprn'):
            if name in kwargs:
                setattr(self, name, kwargs.pop(name))
            elif not hasattr(self, name):
                setattr(self, name, None)
        reject_unknown_params(self, kwargs)
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

    # The parameters this class takes from its keyword arguments. A
    # subclass that takes more lists its own in a PARAMS of its own
    # (accepted_params merges them), and pops them before calling
    # super().__init__(orc, **kwargs): whatever is still there when
    # this __init__ has taken its own is refused.
    PARAMS = ('radius', 'mconst', 'bconst', 'bestimprove', 'quadratic')

    def __init__(self, orc, **kwargs):
        self.nbor_rad = kwargs.pop('radius', 1)
        self.mconst = kwargs.pop('mconst', 2)
        self.bconst = kwargs.pop('bconst', 8)
        self.bestimprove = _toggle('bestimprove', kwargs.pop('bestimprove', 0))
        self.quadratic = _toggle('quadratic', kwargs.pop('quadratic', 0))
        if self.quadratic and self.nbor_rad != 1:
            raise ValueError(
                'quadratic needs radius 1: the candidate is fitted to x - e_i, x, '
                'x + e_i (radius is {0}).'.format(self.nbor_rad)
            )
        try:
            self.sprn = kwargs.pop('sprn')
            self.x0 = kwargs.pop('x0')
        except KeyError as e:
            raise TypeError(
                '{0} requires an x0 and a random number seed (sprn).'.format(type(self).__name__)
            ) from e
        reject_unknown_params(self, kwargs)
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
        that of a given point: the first one found, or, with the
        solver's `bestimprove` on, the best (the first of equal bests).

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
            quadratic = self.quadratic
            if quadratic:
                # NE's quadratic candidate (docs/RSPLINE.m, NE): each
                # coordinate's parabola vertex, from the centre and the
                # two neighbours on its axis, assembled into one point
                # and evaluated after every neighbour. Reached only if
                # the scan completes: under first-improvement, only when
                # no neighbour improved (docs/phase7-plan.md, step 4).
                y2 = fx[nobj]
                xquad = [0] * q
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
                        if not self.bestimprove:
                            return xs, fxs, vxs, n
                isfeas2, fxm1, vxm1 = self.estimate(xm1, e, kcon)
                if isfeas2:
                    n += m
                    if fxm1[nobj] < fxs[nobj]:
                        xs = xm1
                        fxs = fxm1
                        vxs = vxm1
                        if not self.bestimprove:
                            return xs, fxs, vxs, n
                if quadratic:
                    xquad[i] = _quadratic_coordinate(
                        x[i], fxp1[nobj] if isfeas1 else None, y2, fxm1[nobj] if isfeas2 else None
                    )
            if quadratic:
                # Evaluated even when it is the centre or a neighbour
                # already evaluated, as the MATLAB does (lines 293-294).
                # Such a repeat is in gbar here, so it costs no
                # simulation, but it is charged to SPLINE's budget like
                # any feasible neighbour. Skipping it is a candidate
                # improvement, not made.
                xq = tuple(xquad)
                isfeasq, fxq, vxq = self.estimate(xq, e, kcon)
                if isfeasq:
                    n += m
                    if fxq[nobj] < fxs[nobj]:
                        xs = xq
                        fxs = fxq
                        vxs = vxq
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
                        if not self.bestimprove:
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

    PARAMS = ('betadel',)

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
        except (ValueError, WarmStartInfeasible):
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
        # Every predicate below is a pure function of the estimates, so
        # the answer depends only on each condition's final value: each
        # is evaluated only while it can still change the answer
        # (docs/phase7-plan.md, step 2).
        for (s, x), (isfeas, fx, sex) in zip(pairs, estimates):
            # a point already found to dominate a member is not checked again
            if isfeas and x not in ncn:
                if does_strict_dominate(fx, self.gbar[s], delzero, delzero):
                    ncn |= {x}
        # definition 9 (b) initialization
        candidates = list(delN - ncn)
        # each member's relaxation does not depend on the candidate, so
        # it is computed once
        delS = {s: tuple(self.calc_delta(self.sehat[s][i]) for i in dr) for s in mcS}
        for x, (isfeas, fx, sex) in zip(candidates, self.estimate_many(candidates)):
            if isfeas:
                # x is in ncn when no member rules it out by (i) or (ii),
                # and either it weakly dominates a member or (iii) holds
                # for every member
                ruledout = False
                doesweakdom = False
                wouldnotchange = True
                # set the relaxation of the neighbor
                delx = tuple(self.calc_delta(sex[i]) for i in dr)
                for s in mcS:
                    fs = self.gbar[s]
                    # the relaxation of the LES candidate member
                    dels = delS[s]
                    # definition 9 (b) (i)
                    if does_weak_dominate(fs, fx, delzero, delzero):
                        ruledout = True
                        break
                    # definition 9 (b) (ii)
                    if does_dominate(fx, fs, delzero, delzero) and does_weak_dominate(fs, fx, dels, delx):
                        ruledout = True
                        break
                    if not doesweakdom:
                        doesweakdom = does_weak_dominate(fx, fs, delzero, delzero)
                    # definition 9 (b) (iii), which matters only until x
                    # is found to weakly dominate a member
                    if not doesweakdom and wouldnotchange:
                        if does_weak_dominate(fs, fx, dels, delx) or does_weak_dominate(fx, fs, delx, dels):
                            wouldnotchange = False
                # definition 9 (b)
                if not ruledout and (doesweakdom or wouldnotchange):
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
        relax = se*pow(m, 0.5 - self.betadel)
        return relax
