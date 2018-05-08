"""The compare command"""

from .basecomm import *
import multiprocessing as mp
from inspect import getmembers, isclass


class Compare(BaseComm):
    """Run experiments with a known solution"""
    def run(self):
        incr = int(self.options['--incr'])
        trials = int(self.options['--trials'])
        name = self.options['--name']
        budgarg = self.options['--budget']
        budget = int(budgarg)
        prntype = mrg.MRG32k3a
        testarg = self.options['<tester>']
        testmod = getattr(testcases, testarg)
        tp = testmod()
        probmod = tp.ranorc
        probarg = tp.tname
        solvargs = self.options['<solver>']
        sclslist = {}
        for s in solvargs:
            solvclasses = getmembers(solvers, isclass)
            solvclass = [solvc[1] for solvc in solvclasses if solvc[0] == s][0]
            sclslist[s] = solvclass
        orcseeds, solvseeds, xorseeds = get_seeds()
        print('*********** Beginning Optimization Trials ***********')
        start_opt_time = time.time()
        CPUPROC = mp.cpu_count()
        cpusplit = int(CPUPROC/len(sclslist))
        res = dict()
        for solvarg in sclslist:
            joblst = []
            xprn = mrg.MRG32k3a(xorseeds[0])
            for t in range(trials):
                orcseed = orcseeds[t]
                solvseed = solvseeds[t]
                x0 = get_x0(probmod, xprn)
                tup = (solvclass, budget, probmod, prntype, orcseed, prntype, solvseed, x0)
                joblst.append(tup)
            res[solvarg] = mprun.par_runs(joblst, cpusplit)
        end_opt_time = time.time()
        opt_durr = end_opt_time - start_opt_time
        humtxt = gen_humanfile(name, probarg, solvargs, budget, opt_durr, trials)
        print('-- Run time: {0:.2f} seconds'.format(opt_durr))
        print('-- Generating Hausdorf and plot data...')
        pltdat = dict()
        for sol in solvargs:
            pltdat[sol] = gen_pltdat(res[sol], trials, incr, budget, tp)
        print('-- Saving data and details in folder ', name, ' ...')
        for sol in solvargs:
            new_name = sol + '_' + name
            save_files(name, humtxt, res[sol], pltdat[sol], sol)
        print('-- Done!')
