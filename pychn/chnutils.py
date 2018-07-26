#!/usr/bin/env python

import numpy as np
from scipy.spatial.distance import directed_hausdorff, cdist
from itertools import product, filterfalse
from functools import reduce
from math import ceil, floor


def feas2set(feasdict):
    dimlstdict = dict()
    for d in feasdict:
        tuplst = feasdict[d]
        dimlstdict[d] = []
        for interval in feasdict[d]:
            dimlstdict[d].extend(list(range(interval[0], interval[1])))
    dimlst = [dimlstdict[d] for d in feasdict]
    mcX = product(*dimlst)
    return mcX


def does_weak_dominate(g1, g2, delta1, delta2):
    """returns true if g1 weakly dominates g2 with the given relaxation"""
    dim = len(g1)
    is_dom = True
    i = 0
    while i < dim and is_dom:
        if g2[i] + delta2[i] < g1[i] - delta1[i]:
            is_dom = False
        i = i + 1
    return is_dom


def does_dominate(g1, g2, delta1, delta2):
    """returns true if g1 dominates g2 with the given relaxation"""
    dim = len(g1)
    is_dom = True
    i = 0
    while i < dim and is_dom:
        if g2[i] + delta2[i] < g1[i] - delta1[i]:
            is_dom = False
        i = i + 1
    if g2[0] == g1[0] and g2[1] == g1[1]:
        is_dom = False
    return is_dom


def does_strict_dominate(g1, g2, delta1, delta2):
    """returns true if g1 strictly dominates g2 with the given relaxation"""
    dim = len(g1)
    is_sdom = True
    for i in range(dim):
        if g2[i] + delta2[i] <= g1[i] - delta1[i]:
            is_sdom = False
    return is_sdom


def get_les(edict):
    """returns a collection of les"""
    lessets = set()
    lepset = set()
    feasset = set(edict.keys())
    # first get all leps
    print('..... finding LEPs .....')
    for x in edict:
        if is_lep(x, edict):
            lepset |= {x}
    print('..... found ', len(lepset), ' LEPs! .....')
    # crawl from each to form the les
    pts_vis = set()
    print('..... constructing LESs .....')
    while lepset - pts_vis:
        leplst = list(lepset - pts_vis)
        #print('remaining LEPs: ', len(leplst))
        x = leplst[0]
        les = {x}
        pts_vis |= {x}
        nbors = get_setnbors(les) & feasset
        tmp = {x: edict[x] for x in nbors | les}
        ncn = get_biparetos(tmp) & nbors
        no_repeats = True
        while ncn:
            pts_vis |= ncn & lepset
            les |= ncn
            #tmp = {x: edict[x] for x in les}
            #les = get_biparetos(tmp)
            nbors = get_setnbors(les) & feasset
            if nbors & pts_vis:
                no_repeats = False
            pts_vis |= nbors & lepset
            tmp = {x: edict[x] for x in nbors | les}
            nond = get_biparetos(tmp)
            ncn = nond & nbors
        tmp = {x: edict[x] for x in les}
        les = get_biparetos(tmp)
        lessets.add(frozenset(les))
    print('..... found ', len(lessets), ' disjoint LESs! .....')
    return lessets


def get_lwes(edict):
    """returns a collection of lwes"""
    lessets = set()
    lepset = set()
    feasset = set(edict.keys())
    # first get all leps
    print('.....finding LWEPs.....')
    for x in edict:
        if is_lwep(x, edict):
            lepset |= {x}
    print('.....found ', len(lepset), ' LWEPs!.....')
    # crawl from each to form the les
    pts_vis = set()
    print('.....constructing LWESs.....')
    while lepset - pts_vis:
        leplst = list(lepset - pts_vis)
        #print('remaining LEPs: ', len(leplst))
        x = leplst[0]
        les = {x}
        pts_vis |= {x}
        nbors = get_setnbors(les) & feasset
        tmp = {x: edict[x] for x in nbors | les}
        ncn = remove_strict_dom(tmp) & nbors
        no_repeats = True
        while ncn:
            pts_vis |= ncn & lepset
            les |= ncn
            #tmp = {x: edict[x] for x in les}
            #les = get_biparetos(tmp)
            nbors = get_setnbors(les) & feasset - les
            if nbors & pts_vis:
                no_repeats = False
            pts_vis |= nbors & lepset
            tmp = {x: edict[x] for x in nbors | les}
            nond = remove_strict_dom(tmp)
            ncn = nond & nbors - les
        tmp = {x: edict[x] for x in les}
        les = remove_strict_dom(tmp)
        lessets.add(frozenset(les))
    print('.....found ', len(lessets), ' disjoint LWESs!.....')
    print('.....Done!.....')
    return lessets


def is_lep(x, gdict):
    """return true if x is a LEP"""
    dim = len(x)
    nbors = get_nbors(x)
    dominated = False
    delz = [0]*dim
    fx = gdict[x]
    for n in nbors:
        if n in gdict:
            fn = gdict[n]
            if does_dominate(fn, fx, delz, delz):
                dominated = True
    return not dominated


def is_lwep(x, gdict):
    """return true if x is an LWEP"""
    dim = len(gdict[x])
    nbors = get_nbors(x)
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
    """returns the non-dominated keys of a dictionary {x: (g1, g2)}"""
    pts = list(edict.keys())
    vals = np.array([i for i in edict.values()])
    sind = np.argsort(vals, axis=0)[:,0]
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


def remove_strict_dom(edict):
    """returns the non-strictly-dominated keys of a dictionary {x: (g1, g2)}"""
    g1 = 0
    g2 = 1
    pars = get_biparetos(edict)
    pts = set(edict.keys())
    g1parmax = min(pars, key=lambda x: edict[x][g1])
    g2parmax = min(pars, key=lambda x: edict[x][g2])
    g1parval = edict[g1parmax][g1]
    g2parval = edict[g2parmax][g2]
    g1weak = [x for x in pts if edict[x][g1] == g1parval]
    g2weak = [x for x in pts if edict[x][g2] == g2parval]
    weaklies = pars | set(g1weak) | set(g2weak)
    return weaklies


def get_nbors(x, r=1):
    """Find all neighbors of point x within radius r."""
    # define a filter function for points too far away
    def edist_filter(x1):
        # also filter the input point
        if edist(x, x1) > r or x == x1:
            return True
    q = len(x)
    # generate all points in a box with sides length 2r around x
    bounds = []
    for i in range(q):
        a = int(ceil(x[i] - r))
        b = int(floor(x[i] + r))
        bounds.append(range(a, b+1))
    boxpts = product(*bounds)
    # remove those farther than r from x and return the list of neighbors
    nbors = filterfalse(edist_filter, boxpts)
    return set(nbors)


def get_setnbors(mcs, r=1):
    """Generate the exclusive neighborhood of a set within radius r."""
    set_nbors = set()
    for x in mcs:
        set_nbors |= get_nbors(x, r)
    return set_nbors


def enorm(x):
    """Compute the norm of a vector x."""
    return np.linalg.norm(x)


def perturb(x, prn):
    """Perturb x randomly."""
    q = len(x)
    u = np.array([prn.random() for i in range(q)])
    um = np.multiply(np.add(u, -0.5), 0.3)
    pert_x = np.add(x, um)
    return pert_x


def edist(x1, x2):
    """Compute Euclidean distance between 2 vectors."""
    return np.linalg.norm(np.subtract(x1, x2), axis=0)


def dxB(x, B):
    """Compute distance from a point to a set."""
    return min(cdist([x], np.array(B))[0])


def dh(A, B):
    """return the Hausdorf distance between sets A and B"""
    return max(directed_hausdorff(A, B)[0], directed_hausdorff(B, A)[0])


def main():
    A = [(1, 2, 3), (2, 4, 1), (6, 7, 2), (6, 6, 9), (2, 3, 4)]
    B = [(1, 0, -4), (5, -1, 3), (4, 4, 4), (2, -3, 9), (11, 3, 5), (1, 2, 3)]
    x0 = (2, 11, 13)
    r = 1
    print(get_setnbors(set(A), r))

if __name__ == '__main__':
    main()
