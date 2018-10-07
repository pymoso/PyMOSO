#!/usr/bin/env python
from ..problems import probsimpleso
from ..chnutils import edist


def true_g(x):
    obj1 = x[0]**2
    return (obj1,)


def get_ranx0(rng):
    xr = range(-100, 101)
    x1 = rng.choice(xr)
    x0 = (x1,)
    return x0


soln = (0,)


class SimpleSOTester(object):
    def __init__(self):
        self.ranorc = probsimpleso.ProbSimpleSO
        self.true_g = true_g
        self.soln = soln
        self.get_ranx0 = get_ranx0

    def metric(self, eles):
        '''Metric to be computed per retrospective iteration.'''
        point = eles.pop()
        dist = edist(point, self.soln)
        return dist
