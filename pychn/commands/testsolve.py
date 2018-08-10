"""The solve and testsolve command"""

from .basecomm import *
from inspect import getmembers, isclass
import sys


class TestSolve(BaseComm):
    """Solve a bi-objective simulation optimization problem using cli params."""
    def run(self):
        ## get the options with default values
        budget = int(self.options['--budget'])
        name = self.options['--odir']
        hasseed = self.options['--seed']
        incr = int(self.options['--gran'])
        if hasseed:
            seed = tuple(int(i) for i in self.options['<s>'])
        else:
            seed = (12345, 12345, 12345, 12345, 12345, 12345)
        isp = int(self.options['--isp'])
        proc = int(self.options['--proc'])
        radius = float(self.options['--radius'])
        x0 = tuple(int(i) for i in self.options['<x>'])
        ## determine the solver and problem
        solvarg = self.options['<solver>']
        solvclasses = getmembers(solvers, isclass)
        testarg = self.options['<tester>']
        testclasses = getmembers(testproblems, isclass)
        try:
            testclass = [tc[1] for tc in testclasses if tc[0] == testarg][0]
            solvclass = [solvc[1] for solvc in solvclasses if solvc[0] == solvarg][0]
        except:
            print('-- Error: Tester or Solver is not valid.')
            print('-- Use pychn listitems to see a valid list. ')
            print('-- Exiting... ')
            sys.exit()

        ## get the optional parameter names and values if specified
        params = self.options['<param>']
        vals = self.options['<val>']
        paramtups = []
        for i, p in enumerate(params):
            ptup = (p, float(vals[i]))
            paramtups.append(ptup)
        ## generate all prn streams
        orcstreams, solvstreams, x0stream = get_prnstreams(isp, seed)
        ## generate the experiment list
        start_opt_time = time.time()
        print('** Testing ', testarg, ' using ', solvarg, ' **')
        stsstr = '-- using starting seed:'
        print(f'{stsstr:26} {seed[0]:12} {seed[1]:12} {seed[2]:12} {seed[3]:12} {seed[4]:12} {seed[5]:12}')
        for i in range(isp):
            paramlst = [('solvprn', solvstreams[i]), ('x0', x0), ('nbor_rad', radius), ]
            orc = testclass().ranorc(orcstreams[i])
            ## create arguments for (unknown) optional named parameters
            if paramtups:
                paramlst.extend(paramtups)
            paramargs = dict(paramlst)
            res = mprun.run(solvclass, budget, orc, **paramargs)
        end_opt_time = time.time()
        opt_durr = end_opt_time - start_opt_time
        humtxt = gen_humanfile(name, testarg, solvarg, budget, opt_durr, params, vals)
        end_seed = res['endseed']
        seed = tuple([int(i) for i in end_seed])
        endstr = '-- ending seed:'
        print(f'{endstr:26} {seed[0]:12} {seed[1]:12} {seed[2]:12} {seed[3]:12} {seed[4]:12} {seed[5]:12}')
        print('-- Run time: {0:.2f} seconds'.format(opt_durr))
        print('-- Saving data in folder ', name, ' ...')
        save_files(name, humtxt, res)
        print('-- Done!')
