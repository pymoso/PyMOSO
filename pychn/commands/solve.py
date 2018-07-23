"""The solve and testsolve command"""

from .basecomm import *
from inspect import getmembers, isclass


class Solve(BaseComm):
    """Solve a bi-objective simulation optimization problem using cli params"""
    def run(self):
        ## get the options with default values
        trials = int(self.options['--trials'])
        budget = int(self.options['--budget'])
        name = self.options['--name']
        ## determine the solver and problem
        probarg = self.options['<problem>']
        probclasses = getmembers(problems, isclass)
        probclass = [prob[1] for prob in probclasses if prob[0] == probarg][0]
        solvarg = self.options['<solver>']
        solvclasses = getmembers(solvers, isclass)
        solvclass = [solvc[1] for solvc in solvclasses if solvc[0] == solvarg][0]
        ## get the optional parameter names and values if specified
        params = self.options['<param>']
        vals = self.options['<val>']
        paramtups = []
        for i, p in enumerate(params):
            ptup = (p, float(vals[i]))
            paramtups.append(ptup)
        ## generate all prn streams
        orcstreams, solvstreams, xprn = get_prnstreams(trials)
        ## generate the experiment list
        print('*********** Beginning Optimization ***********')
        start_opt_time = time.time()
        joblst = []
        for t in range(trials):
            print('-- Starting Trial ', t + 1, ' of ', trials)
            orcprn = orcstreams[t]
            solprn = solvstreams[t]
            x0 = get_x0(probclass, xprn)
            paramlst = [('x0', x0), ('solvprn', solprn)]
            orc = probclass(orcprn)
            ## create arguments for (unknown) optional named parameters
            if paramtups:
                paramlst.extend(paramtups)
            paramargs = dict(paramlst)
            tup = (solvclass, budget, orc)
            joblst.append((tup, paramargs))
        res = mprun.par_runs(joblst)
        end_opt_time = time.time()
        opt_durr = end_opt_time - start_opt_time
        humtxt = gen_humanfile(name, probarg, solvarg, budget, opt_durr, trials, params, vals)
        print('-- Run time: {0:.2f} seconds'.format(opt_durr))
        print('-- Saving data and details in folder ', name, ' ...')
        save_files(name, humtxt, res)
        print('-- Done!')
