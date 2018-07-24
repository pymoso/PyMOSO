#!/usr/bin/env python
from .. import chnutils as su
from .. import chnbase

class SomeSolver(chnbase.SimOptSolver):
    """A dumb solver. Look at the source to implement your own solver in pychn"""
    def __str__(self):
        return 'some-solver'
    def solve(self, budget):
        # implement this function to solve a problem! Here is a silly example
        # see chnbase.py for defaults, parameters, and initialized objects
        ## feas2set assumes a finite set
        feas_set = su.feas2set(self.orc.get_feasspace())
        # choose the "first" feasible point and sample. Then the second, etc...
        # until the budget runs out
        # self.num_calls is defined and initialized in chnbase.py
        n = 10
        gbar = dict()
        sebar = dict()
        # store the les and number of simulation calls by algorithm iteration
        datanames = ('les', 'simcalls')
        les_d = dict()
        simcalls_d = dict()
        for nu, x in enumerate(feas_set):
            isfeas, fx, sex = self.orc.hit(x, n)
            if isfeas:
                self.num_calls += n
                gbar[x] = fx
                sebar[x] = sex
            if self.num_calls > budget:
                break
            lesnu = su.get_biparetos(gbar)
            les_d[nu] = lesnu
            simcalls_d[nu] = self.num_calls
        result_data = zip(datanames, (les_d, simcalls_d))
        return result_data
