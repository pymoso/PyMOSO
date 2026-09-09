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
import os
import sys
import types
import inspect
from statistics import mean, variance
from math import sqrt, ceil, floor
from .prng.mrg32k3a import get_next_prnstream, jump_substream, mrg32k3a, bsm
from multiprocessing import Queue, Process
from .chnutils import perturb, argsort, enorm, get_setnbors, get_nbors, is_lwep, get_nondom, does_strict_dominate, does_weak_dominate, does_dominate, get_biparetos, MAX_RI


def build_transport_descriptor(cls):
    """
    Build whatever a --simpar worker process needs to reconstruct cls,
    once per worker rather than once per replication -- see
    Oracle.set_simpar, the broadcast point this is built at.

    A class loaded normally (built-in problems/testers, or anything
    else genuinely importable) is returned as-is: it already pickles
    by reference correctly regardless of multiprocessing start method,
    since a fresh worker can just `import` it like any other
    dependency.

    A class loaded from a user-supplied file
    (commands/basecomm.load_user_module marks its module
    __pymoso_dynamic__ = True) has no real module backing it -- nothing
    a worker can `import` by name, since the name only exists because
    the CLI process put it in sys.modules. For that case, this returns
    a source-bundle descriptor instead: every .py file's source text in
    cls's directory, shipped as plain strings -- always picklable
    regardless of start method, since no code or class objects are
    involved -- reconstructed fresh in the worker
    (reconstruct_transport_descriptor).

    Ships the whole directory rather than analyzing cls's file for
    which siblings it actually imports -- a real constraint, not an
    oversight: a custom problem/tester's sibling imports must live flat
    in one directory (matching commands/basecomm.load_user_module,
    which only puts that one directory on sys.path -- a package-style
    layout with subdirectories, or `from .sibling import x`, isn't
    supported by either).

    Parameters
    ----------
    cls : Oracle class

    Returns
    -------
    cls, unchanged, or a dict source-bundle descriptor

    Raises
    ------
    ValueError
        cls has no locatable source at all (defined interactively, not
        loaded from a .py file) -- --simpar cannot transport it to a
        worker process. Raised here, at worker-creation time, rather
        than left to surface as a hang once a job is dispatched.
    """
    module = sys.modules.get(cls.__module__)
    if module is not None and getattr(module, '__pymoso_dynamic__', False):
        return _build_source_bundle(cls, module)
    try:
        inspect.getfile(cls)
    except (TypeError, OSError) as e:
        raise ValueError(
            f"{cls.__name__} has no locatable source file, so it cannot be "
            "sent to a --simpar worker process. This happens for a class "
            "defined interactively (a REPL or notebook), not loaded from a "
            ".py file. Define it in a .py file and try again, or run "
            "without --simpar."
        ) from e
    return cls


def _build_source_bundle(cls, module):
    filepath = module.__file__
    directory = os.path.dirname(os.path.abspath(filepath))
    entry_name = os.path.splitext(os.path.basename(filepath))[0]
    files = {}
    for fname in sorted(os.listdir(directory)):
        if fname.endswith('.py'):
            with open(os.path.join(directory, fname)) as f:
                files[fname[:-3]] = f.read()
    return {'files': files, 'entry': entry_name, 'class_name': cls.__name__}


def reconstruct_transport_descriptor(descriptor):
    """
    The worker side of build_transport_descriptor: turns a
    source-bundle dict back into a class, or passes an already-real
    class through unchanged. Pure data in (for the bundle case) -- no
    pickled code or class objects -- so this works identically
    regardless of multiprocessing start method.

    Execution order isn't assumed (e.g. "entry last"): the bundled
    directory can contain files unrelated to the entry point that have
    their own cross-imports (confirmed directly -- pymoso/examples/
    ships both myproblem.py and mytester.py, and mytester.py imports
    myproblem.py; a real --simpar run on a fixture built from that
    directory bundles both even though only one is the entry point).
    Instead, this retries whichever files raise ImportError against
    modules not populated yet, until a full pass makes no further
    progress -- a simple fixed-point resolution that works for any
    acyclic dependency order among the bundled files without having to
    guess it upfront.

    Parameters
    ----------
    descriptor : Oracle class, or dict as built by
        build_transport_descriptor

    Returns
    -------
    Oracle class

    Raises
    ------
    ImportError
        The bundled files' cross-imports can't be resolved in any
        order (a genuine circular import among them, or one of them
        imports something this bundle doesn't include).
    """
    if not isinstance(descriptor, dict):
        return descriptor
    files = descriptor['files']
    entry = descriptor['entry']
    modules = {}
    for name in files:
        mod = types.ModuleType(name)
        mod.__file__ = f'<transported:{name}.py>'
        modules[name] = mod
        sys.modules[name] = mod
    pending = dict(files)
    last_errors = {}
    while pending:
        progressed = False
        for name in sorted(pending):
            try:
                code = compile(pending[name], f'<transported:{name}.py>', 'exec')
                exec(code, modules[name].__dict__)
            except ImportError as e:
                last_errors[name] = e
                continue
            del pending[name]
            progressed = True
        if not progressed:
            raise ImportError(
                f"Could not resolve import order for bundled file(s) "
                f"{sorted(pending)} while reconstructing a --simpar transport "
                f"descriptor -- a circular import among the bundled files, or "
                f"one of them imports something outside the bundle. Last "
                f"error(s) seen: {last_errors}"
            )
    return getattr(modules[entry], descriptor['class_name'])


def mp_replicate(orccls, x, rngcls, seed):
    """
    Wrap `Oracle.g` in a top-level function for use with multiprocessing.

    Parameters
    ----------
    orccls : Oracle class
    x : tuple of int
    rngcls : random.Random class
    seed : tuple of int

    Returns
    -------
    isfeas : bool
    objvals : tuple of float

    See also
    --------
    Oracle.replicate
    """

    rng = rngcls(seed)
    orc = orccls(rng)
    orc.set_crnflag(False)
    isfeas, objvals = orc.g(x, rng)
    return isfeas, objvals


def mp_worker(input, output, descriptor, rngcls):
    """
    Worker loop for parallel replication. `descriptor` is reconstructed
    into `orccls` ONCE, at worker start -- the broadcast pattern (see
    Oracle.set_simpar) -- not re-sent per job, so per-job payloads on
    `input` carry only (x, seed), not the problem class.

    Parameters
    ----------
    input : multiprocessing.Queue object
        Yields (x, seed) tuples.
    output : multiprocessing.Queue object
    descriptor : Oracle class or dict
        See build_transport_descriptor/reconstruct_transport_descriptor.
    rngcls : random.Random class
    """
    orccls = reconstruct_transport_descriptor(descriptor)
    for x, seed in iter(input.get, 'STOP'):
        result = mp_replicate(orccls, x, rngcls, seed)
        output.put(result)


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
        seed1 = self.orc.rng.get_seed()
        self.endseed = seed1
        lesnu = dict()
        simcalls = dict()
        lesnu[0] = set() | {self.x0}
        simcalls[0] = 0
        # initialize the iteration counter
        self.nu = 0
        # invoke the Retrospective approximation algorithm
        self.rasolve(lesnu, simcalls, budget)
        # name the data keys and return the results
        resdict = {'itersoln': lesnu, 'simcalls': simcalls, 'endseed': self.endseed}
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
            if self.nu > MAX_RI:
                raise RuntimeError(
                    'RA solver reached iteration {0}, exceeding MAX_RI={1} -- the number '
                    'of iterations of random-stream headroom reserved per independent '
                    'sample path in chnutils.get_testsolve_prnstreams. Continuing would '
                    'silently walk into the next sample path\'s reserved stream (see '
                    'docs/phase2a-verification.md, item 3, for a concrete demonstration). '
                    'To proceed: reduce --budget, increase mconst so fewer RA iterations '
                    'are needed, or raise chnutils.MAX_RI (and regenerate any pre-reserved '
                    'stream windows that assumed the old value).'.format(self.nu, MAX_RI)
                )
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
            self.orc.crn_advance()
            self.endseed = self.orc.rng.get_seed()

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
        for i in range(q + 1):
            isfeas, fx, vx = self.estimate(simp[i])
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
            try:
                isfeas, fx, vx = self.orc.hit(x, m)
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
        for s in mcS:
            isfeas, fs, ses = self.estimate(s)
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
        for s in mcS:
            fs = self.gbar[s]
            ses = self.sehat[s]
            #dels = tuple(self.calc_delta(ses[i]) for i in dr)
            snb = get_nbors(s, r) - mcS
            for x in snb:
                isfeas, fx, sex = self.estimate(x)
                if isfeas:
                    #delx = tuple(self.calc_delta(sex[i]) for i in dr)
                    if does_strict_dominate(fx, fs, delzero, delzero):
                        ncn |= {x}
                    # if does_strict_dominate(fs, fx, delzero, delzero):
                    #     nisdom |= {x}
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
    rng : prng.MRG32k3a object
    pseudo-random number generator, handed to `g(x, rng)` for each
    replication. hit()/bump() use it as the *live* draw source but do
    not treat its value between calls as authoritative -- a custom
    MOSOSolver may set it directly before calling hit() (MOCOMPASS, an
    in-tree example, does exactly this, via rng.setstate(), as its own
    cross-point synchronization mechanism -- see docs/mocompass-mopbnb-
    known-issues.md and docs/rng-interface-design.md §4.2/§4.3). What
    actually drives the framework's own stream progression is
    _next_seed, below, not `rng` itself.
    _iteration : int
    Count of completed crn_advance() calls (one per RA iteration).
    Meaningful mainly under crnflag=True, where it determines the
    current iteration's baseline coordinate; tracked unconditionally
    since it costs nothing and later steps (visit=/sync=) need it.
    _iteration_baseline_seed : tuple of int
    The current RA iteration's baseline mrg32k3a seed -- what
    crnold_state used to hold. Under crnflag=True, hit()/bump() rewind
    both `rng` and _next_seed to this seed at the start of every call,
    so different points visited in the same iteration draw from the
    same baseline (this rewind-then-walk-forward *is* what "common
    random numbers" means here -- see §2). Under crnflag=False it is
    tracked but never used to rewind anything.
    _next_seed : tuple of int
    Where the *next* replication's stream starts -- what crn_obsold
    used to hold. Advances by exactly one 2**76 hop per replication,
    computed from its own previous value, never from wherever `rng`
    happened to end up (`g()`'s own draws mutate `rng`, and a solver may
    externally overwrite it -- see `rng` above; both are irrelevant to
    this progression, by design, the same way they were irrelevant to
    crn_obsold's). `rng` is reset to this value immediately before every
    jump, discarding whatever it held, so the two stay equal exactly at
    the boundary between replications -- never assumed equal mid-call.
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
        # Not rng.get_seed() here: commands/solve.py/testsolve.py
        # construct a throwaway Oracle over a plain random.Random() --
        # not MRG32k3a, no get_seed() -- purely to read .dim, and never
        # call set_crnflag() on it. crnflag defaults to False, so
        # _iteration_baseline_seed is never dereferenced unless
        # set_crnflag() runs first and gives it a real value -- every
        # real solve()/testsolve()/mp_replicate() path does exactly
        # that before any hit()/bump()/crn_advance() call.
        self._iteration_baseline_seed = None
        self._next_seed = None
        super().__init__()


    def set_simpar(self, simpar):
        """
        Intialize processes when parallel replications is enabled.

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
        """
        self.simpar = simpar
        if self.simpar > 1:
            descriptor = build_transport_descriptor(type(self))
            rngcls = type(self.rng)
            self.req_q = Queue()
            self.res_q = Queue()
            self.proc = []
            for i in range(self.simpar):
                p = Process(target=mp_worker, args=(self.req_q, self.res_q, descriptor, rngcls))
                p.start()
                self.proc.append(p)
        return self

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.mp_cleanup()
        return False


    def mp_cleanup(self):
        """
        Terminate all multiprocessing processes created in `__init__`. Call
        this after simulation is complete.
        """
        if self.simpar > 1:
            for p in self.proc:
                p.terminate()
                p.join()


    def set_crnflag(self, crnflag):
        """
        Set the common random number (crn) flag and initialize the
        iteration baseline.

        Parameters
        ----------
        crnflag: bool
        """
        self.crnflag = crnflag
        self._iteration = 0
        self._iteration_baseline_seed = self.rng.get_seed()
        self._next_seed = self.rng.get_seed()

    def crn_advance(self):
        """
        Advance to the next RA iteration's baseline stream: under
        crnflag=True, one 2**127 jump ahead of the *current* iteration's
        baseline -- iteration k's baseline is `orc_root + k*2**127` by
        induction, docs/rng-interface-design.md §2. Under crnflag=False,
        the same unconditional 2**127 jump this method has always
        performed, from wherever _next_seed's ongoing forward walk
        currently sits -- part of the deliberately order-dependent
        compatibility encoding this step preserves (§3.4/§12 step 3),
        not a rewind. Jumps from _next_seed, never from `rng`'s live
        value directly: by the time this runs (after every point any
        RA iteration visits has returned from hit()/bump()), the two
        are always equal anyway (see _next_seed's own docstring above),
        but computing from the authoritative tracker rather than
        `rng` keeps that invariant explicit rather than assumed.

        Kept as a public method, unlike the crn_reset/crn_check/
        crn_setobs/crn_nextobs helpers this replaces (removed -- nothing
        outside Oracle called them): MOCOMPASS/MOPBnB, two in-tree,
        crnflag=False-only solvers, call `orc.crn_advance()` directly,
        once, at the end of their own solve() (see docs/mocompass-
        mopbnb-known-issues.md and docs/rng-interface-design.md §4.2) --
        removing the solver-facing surface entirely is a later, separate
        step (§4.3's sync=), not this one.
        """
        if self.crnflag:
            self._next_seed = self._iteration_baseline_seed
        self.rng = get_next_prnstream(self._next_seed, self.crnflag)
        self._iteration += 1
        self._iteration_baseline_seed = self.rng.get_seed()
        self._next_seed = self.rng.get_seed()
        if self.crnflag:
            self.rng.generate.cache_clear()
            self.rng.bsm.cache_clear()

    def _advance_replication(self):
        """
        Jump `rng` one 2**76 hop past the Oracle's own tracked position
        (_next_seed), discarding whatever `rng` currently holds --
        whatever g() itself just drew, or whatever a solver may have
        set it to directly (see `rng`'s own docstring above) -- exactly
        as crn_nextobs() always discarded both by resetting to
        crn_obsold before jumping, regardless of what g() or external
        code did to `rng` in between. _next_seed then advances to
        match.
        """
        self.rng.seed(self._next_seed)
        jump_substream(self.rng)
        self._next_seed = self.rng.get_seed()

    def bump(self, x, m):
        """
        Simulate 'm' replications at 'x' and return the replication
        values as a list

        Parameters
        ----------
        x : tuple of int
    point at which to simulate
    m : int
    number of replications to simulate 'x'

    Returns
    -------
    isfeas : bool
    Indicates if 'x' is feasible
    obs : list of tuple of float
    list of length 'm' of simulated objective values
        """

        d = self.num_obj
        dr = range(d)
        isfeas = False
        obs = []
        mr = range(m)
        if m < 1:
            raise ValueError('Number of replications must be at least 1.')
        else:
            mr = range(m)
            feas = []
            if self.crnflag:
                self.rng.seed(self._iteration_baseline_seed)
                self._next_seed = self._iteration_baseline_seed
            for i in mr:
                oisfeas, objd = self.g(x, self.rng)
                feas.append(oisfeas)
                obs.append(objd)
                self._advance_replication()
            if all(feas):
                isfeas = True
        return isfeas, obs

    def hit(self, x, m):
        """
        Generate the means and standard errors of 'm' simulation
        replications at point 'x'.

        Parameters
        ----------
        x : tuple of int
    point at which to simulate
    m : int
    number of replications to simulate 'x'

        Returns
        -------
        isfeas : bool
    indicates the feasibility of 'x'
        obmean : tuple of float
    mean of each objective of 'm' simulations
        obse : tuple of float
    mean of standard errors of each objective of 'm' simulations
        """

        d = self.num_obj
        dr = range(d)
        isfeas = False
        obmean = []
        obse = []
        mr = range(m)
        assert(m >= 1)
        if self.crnflag:
            self.rng.seed(self._iteration_baseline_seed)
            self._next_seed = self._iteration_baseline_seed
        if m == 1:
            isfeas, objd = self.g(x, self.rng)
            obmean = objd
            obse = [0 for o in objd]
            self._advance_replication()
        else:
            feas = []
            objm = []
            # take replications in parallel
            if self.simpar > 1:
                for i in mr:
                    # orccls/rngcls were already sent once, at worker
                    # start (Oracle.set_simpar) -- each job here carries
                    # only what actually varies per replication.
                    cseed = self.rng.get_seed()
                    self.req_q.put((x, cseed))
                    self._advance_replication()
                for i in mr:
                    # block until parallel results are ready
                    isfeasi, oval = self.res_q.get()
                    feas.append(isfeasi)
                    objm.append(oval)
            # do not take replications in parallel
            else:
                for i in mr:
                    isfeasi, oval = self.g(x, self.rng)
                    feas.append(isfeasi)
                    objm.append(oval)
                    self._advance_replication()
            if all(feas):
                isfeas = True
                obmean = tuple([mean([objm[i][k] for i in mr]) for k in dr])
                obvar = [variance([objm[i][k] for i in mr], obmean[k]) for k in dr]
                obse = tuple([sqrt(obvar[i]/m) for i in dr])
        return isfeas, obmean, obse

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
