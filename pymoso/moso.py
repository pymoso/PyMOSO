#!/usr/bin/env python
"""
The primitives of multi-objective simulation optimization on integer
points: dominance between objective vectors, local efficiency,
non-dominated sets, neighbourhoods, and distances between points and
sets.

Nothing here depends on the rest of pymoso. Solvers, testers and user
code all use these; `pymoso.chnutils` offers every one of them under
its own name, which is the documented import path.

Listing
--------------
does_weak_dominate
does_dominate
does_strict_dominate
is_lep
is_lwep
get_biparetos
front
get_nondom
get_nbors
argsort
get_setnbors
enorm
perturb
edist
dxB
dAB
dh
"""

from math import ceil, floor, sqrt


def does_weak_dominate(g1, g2, delta1, delta2):
    """
    Returns true if 'g1' weakly dominates 'g2' with the given relaxation

    Parameters
    ----------
    g1 : tuple of float
        Objective values of a point
    g2 : tuple of float
        Objective values of a point
    delta1 : tuple of float
        Relaxation of 'g1'
    delta2 : tuple of float
        Relaxation of 'g2'

    Returns
    -------
    is_dom : bool

    Examples
    --------
    >>> does_weak_dominate((1, 2), (2, 3), (0, 0), (0, 0))
    True
    >>> does_weak_dominate((2, 3), (1, 2), (0, 0), (0, 0))
    False
    """
    dim = len(g1)
    is_dom = True
    i = 0
    while i < dim and is_dom:
        if g2[i] + delta2[i] < g1[i] - delta1[i]:
            is_dom = False
        i = i + 1
    return is_dom


def does_dominate(g1, g2, delta1, delta2):
    """
    Returns true if g1 dominates g2 with the given relaxation.

    Parameters
    ----------
    g1 : tuple of float
        Objective values of a point
    g2 : tuple of float
        Objective values of a point
    delta1 : tuple of float
        Relaxation of 'g1'
    delta2 : tuple of float
        Relaxation of 'g2'

    Returns
    -------
    is_dom : bool

    Examples
    --------
    >>> does_dominate((1, 2), (2, 3), (0, 0), (0, 0))
    True
    >>> does_dominate((1, 2), (1, 2), (0, 0), (0, 0))
    False
    """
    dim = len(g1)
    is_dom = True
    i = 0
    while i < dim and is_dom:
        if g2[i] + delta2[i] < g1[i] - delta1[i]:
            is_dom = False
        i = i + 1
    if is_dom:
        is_equal = True
        for i in range(dim):
            if not g1[i] - delta1[i] == g2[i] + delta2[i]:
                is_equal = False
        if is_equal:
            is_dom = False
    return is_dom


def does_strict_dominate(g1, g2, delta1, delta2):
    """
    Returns true if g1 strictly dominates g2 with the given relaxation.

    Parameters
    ----------
    g1 : tuple of float
        Objective values of a point
    g2 : tuple of float
        Objective values of a point
    delta1 : tuple of float
        Relaxation of 'g1'
    delta2 : tuple of float
        Relaxation of 'g2'

    Returns
    -------
    bool

    Examples
    --------
    >>> does_strict_dominate((1, 1), (2, 2), (0, 0), (0, 0))
    True
    >>> does_strict_dominate((1, 2), (2, 2), (0, 0), (0, 0))
    False
    """
    dim = len(g1)
    is_sdom = True
    for i in range(dim):
        if g2[i] + delta2[i] <= g1[i] - delta1[i]:
            is_sdom = False
    return is_sdom


def is_lep(x, r, gdict):
    """
    Return true if x is a LEP

    Parameters
    ----------
    x : tuple of int
        Feasible point
    r : float
        Radius for which to consider neighbors
    gdict : dict
        Objective values for every neighbor of 'x'

    Returns
    -------
    bool
    """
    dim = len(x)
    nbors = get_nbors(x, r)
    dominated = False
    delz = [0]*dim
    fx = gdict[x]
    for n in nbors:
        if n in gdict:
            fn = gdict[n]
            if does_dominate(fn, fx, delz, delz):
                dominated = True
    return not dominated


def is_lwep(x, r, gdict):
    """
    Return true if x is a LWEP

    Parameters
    ----------
    x : tuple of int
        Feasible point
    r : float
        Radius for which to consider neighbors
    gdict : dict
        Objective values for every neighbor of 'x'

    Returns
    -------
    bool
    domset : set of tuple of int
        Set of points which strictly dominate 'x'
    """
    dim = len(gdict[x])
    nbors = get_nbors(x, r)
    dominated = False
    delz = [0]*dim
    fx = gdict[x]
    domset = set()
    for n in nbors:
        if n in gdict:
            fn = gdict[n]
            if does_strict_dominate(fn, fx, delz, delz):
                dominated = True
                domset |= {n}
    return not dominated, domset


def get_biparetos(edict):
    """
    Generate the non-dominated points of a set with two objectives.

    Parameters
    ----------
    edict : dict
        Keys are feasible points (tuples of int), values are objective
         values (tuples of float) of length 2

    Returns
    -------
    plist : set of tuple of int
        Set of non-dominated points
    """
    pts = list(edict.keys())
    vals = list(edict.values())
    sind = argsort(vals)
    g2 = 1
    dlen = len(pts)
    plist = set()
    if dlen > 1:
        i = 0
        j = 0
        while j < dlen:
            is_pareto = False
            bkey = pts[sind[i]]
            plist |= {bkey}
            j = i + 1
            #print('i: ', i, ' j: ', j, ' bkey: ', bkey, ' len: ', dlen)
            while not is_pareto and j < dlen:
                newp = pts[sind[j]]
                if edict[bkey][g2] > edict[newp][g2]:
                    is_pareto = True
                    i = j
                else:
                    j += 1
    else:
        plist |= set(pts)
    return plist


def front(points, objs):
    """
    Recursively generate the non-dominated set.

    Parameters
    ----------
    points : list of tuple of int
    objs : list of tuple of float
        Objective values of points

    Returns
    -------
    Tpts : list of tuple of int
    Tobjs : list of tuple of float
    """
    cardP = len(points)
    if cardP == 1:
        return points, objs
    elif cardP > 1:
        nondom = set()
        halfind = int(cardP/2)
        Tpts, Tobjs = front(points[0:halfind], objs[0:halfind])
        Bpts, Bobjs = front(points[halfind:cardP], objs[halfind:cardP])
        brange = range(len(Bpts))
        for i in brange:
            pt = Bpts[i]
            gvals = Bobjs[i]
            delz = [0]*len(gvals)
            pt_nondom = True
            j = 0
            while j < len(Tpts) and pt_nondom:
                if does_dominate(Tobjs[j], gvals, delz, delz):
                    pt_nondom = False
                j += 1
            if pt_nondom:
                Tpts.append(pt)
                Tobjs.append(gvals)
        return Tpts, Tobjs


def get_nondom(edict):
    """
    Generate the non-dominated points of a set.

    Parameters
    ----------
    edict : dict
        Keys are feasible points (tuples of int), values are objective
         values (tuples of float)

    Returns
    -------
    set
        Set of non-dominated points

    Examples
    --------
    >>> sorted(get_nondom({(0, 0): (1, 5), (1, 0): (3, 3), (2, 0): (5, 1)}))
    [(0, 0), (1, 0), (2, 0)]
    >>> get_nondom({(0, 0): (1, 1), (1, 0): (2, 2)})
    {(0, 0)}
    """
    pts = list(edict.keys())
    vals = list(edict.values())
    sind = argsort(vals)
    newpts = []
    newvals = []
    for i in range(len(pts)):
        newpts.append(pts[sind[i]])
        newvals.append(vals[sind[i]])
    Mpts, Mobjs = front(newpts, newvals)
    return set(Mpts)


def get_nbors(x, r=1):
    """
    Find all neighbors of a point.

    Parameters
    ----------
    x : tuple of int
        A point
    r : int
        radius of the neighborhood

    Returns
    -------
    set of tuple of int
        The neighborhood of 'x'

    Notes
    -----
    Built directly: the work is proportional to the number of
    neighbours returned, not to the `(2r+1)**dim` box around 'x'.
    Through Phase 3, and in every release, the whole box was generated
    and filtered by distance -- `3**dim` points examined at `r=1` to
    return `2*dim` -- and that, not anything in the algorithms, is what
    held the built-in RA solvers to about nine dimensions
    (docs/spark-backend.md).

    **The order points are inserted in is part of the result.**
    Solvers iterate over the returned set, and a set's iteration order
    follows from its insertion order. This visits coordinates exactly
    as `itertools.product` visited the box -- first coordinate
    slowest, each from low to high -- so the set comes out identical
    to the old one, element for element and position for position.
    Inserting the same points in another order changes solver results
    (tests/test_get_nbors_equivalence.py keeps the old implementation
    and shows both).

    At radius above 1 the neighbourhood is itself large in high
    dimension (87,480 points at `r=2`, `dim=20`), and every one of
    them is a point a solver will simulate.

    Examples
    --------
    >>> sorted(get_nbors((0,), 1))
    [(-1,), (1,)]
    """
    q = len(x)
    lows = [int(ceil(x[i] - r)) for i in range(q)]
    highs = [int(floor(x[i] + r)) for i in range(q)]
    found = []
    point = [0]*q

    def descend(i, partial):
        # partial: squared distance from x over the first i coordinates
        if i == q:
            x1 = tuple(point)
            # the test the box enumeration applied to every box point
            if not (edist(x, x1) > r or x == x1):
                found.append(x1)
            return
        for v in range(lows[i], highs[i] + 1):
            step = partial + pow(x[i] - v, 2)
            # already too far: no choice of the remaining coordinates
            # brings it back
            if sqrt(step) > r:
                continue
            point[i] = v
            descend(i + 1, step)

    descend(0, 0)
    nbors = set(found)
    return set(nbors)


def argsort(seq):
    """
    Generate the sorted arguments of a collection of values

    Parameters
    ----------
    seq : dict

    Returns
    -------
    list
        list of keys sorted by value
    """
    return sorted(range(len(seq)), key=seq.__getitem__)


def get_setnbors(mcs, r):
    """
    Generate the exclusive neighborhood of a set.

    Parameters
    ----------
    mcs : set of tuple of int
        Set of points
    r : float
        Radius of neighborhood

    Returns
    -------
    set of tuple of int
        The exclusive neighborhood

    Examples
    --------
    >>> sorted(get_setnbors({(0,), (1,)}, 1))
    [(-1,), (2,)]
    """
    set_nbors = set()
    for x in mcs:
        set_nbors |= get_nbors(x, r)
    return set_nbors - mcs


def enorm(x):
    """
    Compute the norm of a vector.

    Parameters
    ----------
    x : tuple of numbers

    Returns
    -------
    float
    """
    q = len(x)
    return sqrt(sum([pow(x[i], 2) for i in range(q)]))


def perturb(x, prn):
    """
    Randomly perturb an integer point.

    Parameters
    ----------
    x : tuple of int
        Point to be perturbed
    prn : prng.MRG32k3a object

    Returns
    -------
    tuple of float
        The perturbed point
    """
    q = len(x)
    return tuple(x[i] + 0.3*(prn.random() - 0.5) for i in range(q))


def edist(x1,x2):
    """
    Compute Euclidean distance between two vectors.

    Parameters
    ----------
    x1 : tuple of numbers
    x2 : tuple of numbers

    Returns
    -------
    float

    Examples
    --------
    >>> edist((0, 0), (3, 4))
    5.0
    """
    q = len(x1)
    return sqrt(sum([pow(x1[i] - x2[i], 2) for i in range(q)]))


def dxB(x, B):
    """
    Compute distance from a point to a set.

    Parameters
    ----------
    x : tuple of numbers
    B : set of tuple of numbers

    Returns
    -------
    dmin : float
    """
    dmin = float('inf')
    for b in B:
        dxb = edist(x, b)
        if dxb < dmin:
            dmin = dxb
    return dmin


def dAB(A, B):
    """
    Compute distance from a set to another set.

    Parameters
    ----------
    A : set of tuple of numbers
    B : set of tuple of numbers

    Returns
    -------
    dmax : float
    """
    dmax = float('-inf')
    for a in A:
        daB = dxB(a, B)
        if daB > dmax:
            dmax = daB
    return dmax


def dh(A, B):
    """
    Compute the Hausdorf distance between two sets.

    Parameters
    ----------
    A : set of tuple of numbers
    B : set of tuple of numbers

    Returns
    -------
    float
        The Hausdorf distance

    Examples
    --------
    >>> dh({(0, 0)}, {(3, 4)})
    5.0
    >>> dh({(0, 0)}, {(0, 0)})
    0.0
    """
    return max(dAB(A, B), dAB(B, A))
