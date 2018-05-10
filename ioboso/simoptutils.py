#!/usr/bin/env python
from math import sqrt, pow
from itertools import product
import pickle


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


def txtseeds2pkl(seedfilename):
    """convert .txt file containing mrg32k3a seeds to a pickle file"""
    seedsdict = dict()
    with open(seedfilename, 'r') as txthandle:
        for i, line in enumerate(txthandle):
            #read next line
            strspseed = " ".join(txthandle.readline().split())
            #remove spaces
            strseed = tuple(strspseed.split())
            #convert to tuple(int, int, ...)
            seedi = tuple(int(s) for s in strseed)
            seedsdict[i] = seedi
    pklname = seedfilename + '.pkl'
    with open(pklname, 'wb') as pklhandle:
        pickle.dump(seedsdict, pklhandle)


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
    if g2 == g1:
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


def get_nbors(x):
    """return the neighborhood of a point x"""
    q = len(x)
    qr = range(q)
    mcn = set()
    for i in qr:
        xp1 = tuple(x[j] + 1 if i == j else x[j] for j in qr)
        xm1 = tuple(x[j] - 1 if i == j else x[j] for j in qr)
        mcn = mcn | {xp1, xm1}
    return mcn


def get_setnbors(mcs):
    """return the neighborhood of a set"""
    mcn = set()
    for x in mcs:
        mcn |= get_nbors(x)
    return mcn - mcs


def argsort(seq):
    return sorted(range(len(seq)), key=seq.__getitem__)


def enorm(x):
    """compute the norm of a vector x"""
    q = len(x)
    return sqrt(sum([pow(x[i], 2) for i in range(q)]))


def perturb(x, prn):
    """ randomly perturb x, as in the R-SPLINE paper. See Wang et. al 2013"""
    q = len(x)
    u = prn.random()
    return tuple(x[i] + 0.3*(u - 0.5) for i in range(q))


def edist(x1,x2):
    """return Euclidean distance between 2 vectors"""
    q = len(x1)
    return sqrt(sum([pow(x1[i] - x2[i], 2) for i in range(q)]))


def dxB(x, B):
    """return distance from a point to a set"""
    dmin = float('inf')
    for b in B:
        dxb = edist(x, b)
        if dxb < dmin:
            dmin = dxb
    return dmin


def dAB(A, B):
    """return distance from set A to set B"""
    dmax = float('-inf')
    for a in A:
        daB = dxB(a, B)
        if daB > dmax:
            dmax = daB
    return dmax


def dh(A, B):
    """return the Hausdorf distance between sets A and B"""
    return max(dAB(A, B), dAB(B, A))
