"""The solve and testsolve command"""

from .basecomm import *
from inspect import getmembers, isclass


class Solve(BaseComm):
    """Solve a bi-objective simulation optimization problem using cli params"""
    def run(self):
        trials = int(self.options['--trials'])
        name = self.options['--name']
        budgarg = self.options['--budget']
        budget = int(budgarg)
        prntype = prng.mrg32k3a.MRG32k3a
        probarg = self.options['<problem>']
        probclasses = getmembers(problems, isclass)
        probclass = [prob[1] for prob in probclasses if prob[0] == probarg][0]
        solvarg = self.options['<solver>']
        solvclasses = getmembers(solvers, isclass)
        solvclass = [solvc[1] for solvc in solvclasses if solvc[0] == solvarg][0]
        params = self.options['<param>']
        vals = self.options['<val>']
        paramtups = []
        for i, p in enumerate(params):
            ptup = (p, float(vals[i]))
            paramtups.append(ptup)
        orcseeds, solvseeds, xorseeds = get_seeds()
        xprn = prng.mrg32k3a.MRG32k3a(xorseeds[0])
        print('*********** Beginning Optimization ***********')
        start_opt_time = time.time()
        joblst = []
        for t in range(trials):
            print('-- Starting Trial ', t + 1, ' of ', trials)
            orcseed = orcseeds[t]
            solvseed = solvseeds[t]
            solvseedtup = ('solvseed', solvseed)
            solvprntup = ('solvprn', prntype)
            x0 = get_x0(probclass, xprn)
            x0tup = ('x0', x0)
            paramlst = [solvseedtup, solvprntup, x0tup]
            if paramtups:
                paramlst.extend(paramtups)
            paramargs = dict(paramlst)
            tup = (solvclass, budget, probclass, prntype, orcseed)
            joblst.append((tup, paramargs))
        res = mprun.par_runs(joblst)
        end_opt_time = time.time()
        opt_durr = end_opt_time - start_opt_time
        humtxt = gen_humanfile(name, probarg, solvarg, budget, opt_durr, trials, params, vals)
        print('-- Run time: {0:.2f} seconds'.format(opt_durr))
        print('-- Saving data and details in folder ', name, ' ...')
        save_files(name, humtxt, res)
        print('-- Done!')
