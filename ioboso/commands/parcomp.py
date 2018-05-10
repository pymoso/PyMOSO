"""The compare command"""

from .basecomm import *
import multiprocessing as mp
from inspect import getmembers, isclass


class ParComp(BaseComm):
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
        solvargs = self.options['<solver>'][0]
        solvclasses = getmembers(solvers, isclass)
        solvclass = [solvc[1] for solvc in solvclasses if solvc[0] == solvargs][0]
        param = self.options['<param>'][0]
        vals = self.options['<val>']
        orcseeds, solvseeds, xorseeds = get_seeds()
        print('*********** Beginning Optimization Trials ***********')
        start_opt_time = time.time()
        CPUPROC = mp.cpu_count()
        cpusplit = int(ceil(CPUPROC/len(vals)))
        res = dict()
        for v in vals:
            joblst = []
            xprn = mrg.MRG32k3a(xorseeds[0])
            for t in range(trials):
                orcseed = orcseeds[t]
                solvseed = solvseeds[t]
                x0 = get_x0(probmod, xprn)
                tup = (solvclass, budget, probmod, prntype, orcseed, prntype, solvseed, x0, [(param, float(v))])
                joblst.append(tup)
            res[v] = mprun.par_runs(joblst, cpusplit)
        end_opt_time = time.time()
        opt_durr = end_opt_time - start_opt_time
        print('-- Run time: {0:.2f} seconds'.format(opt_durr))
        print('-- Generating Hausdorf and plot data...')
        humtxt = gen_humanfile(name, probarg, solvargs, budget, opt_durr, trials, param, vals)
        pltdat = dict()
        for v in vals:
            pltdat[v] = gen_pltdat(res[v], trials, incr, budget, tp)
        print('-- Saving data and details in folder ', name, ' ...')
        for v in vals:
            save_files(name, humtxt, res[v], pltdat[v], v.replace('.', ''))
        print('-- Done!')
