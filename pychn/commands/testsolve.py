"""The solve and testsolve command"""

from .basecomm import *
from inspect import getmembers, isclass
import sys
from ..chnutils import testsolve, par_diff, gen_qdata, par_runs


class TestSolve(BaseComm):
    """Test a MOSO algorithm against a problem with a known solution."""
    def run(self):
        ## get the options with default values
        budget = int(self.options['--budget'])
        name = self.options['--odir']
        hasseed = self.options['--seed']
        incr = int(self.options['--gran'])
        haus = self.options['--haus']
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
        solvclass = [solvc[1] for solvc in solvclasses if solvc[0] == solvarg][0]
        testarg = self.options['<tester>']
        if testarg.endswith('.py'):
            from importlib import import_module
            mod_name = testarg.replace('.py', '')
            module = import_module(mod_name)
            testclasses = getmembers(module, isclass)
            testclass = [prob[1] for prob in testclasses if prob[0].lower() == mod_name][0]
        else:
            testclasses = getmembers(problems, isclass)
            testclass = [prob[1] for prob in probclasses if prob[0] == probarg][0]
        ## get the optional parameter names and values if specified
        params = self.options['<param>']
        vals = self.options['<val>']
        solve_kwargs = dict()
        solve_kwargs['budget'] = budget
        solve_kwargs['seed'] = seed
        solve_kwargs['radius'] = radius
        solve_kwargs['gran'] = incr
        solve_kwargs['isp'] = isp
        solve_kwargs['proc'] = proc
        for i, p in enumerate(params):
            solve_kwargs[p] = float(vals[i])
        start_opt_time = time.time()
        print('** Testing ', testarg, ' using ', solvarg, ' **')
        stsstr = '-- using starting seed:'
        print(f'{stsstr:26} {seed[0]:12} {seed[1]:12} {seed[2]:12} {seed[3]:12} {seed[4]:12} {seed[5]:12}')
        res = testsolve(testclass, solvclass, x0, **solve_kwargs)
        end_opt_time = time.time()
        opt_durr = end_opt_time - start_opt_time
        end_seed = res['endseed']
        humtxt = gen_humanfile(name, testarg, solvarg, budget, opt_durr, params, vals, seed, end_seed)
        seed = tuple([int(i) for i in end_seed])
        endstr = '-- ending seed:'
        print(f'{endstr:26} {seed[0]:12} {seed[1]:12} {seed[2]:12} {seed[3]:12} {seed[4]:12} {seed[5]:12}')
        print('-- Optimization run time: {0:.2f} seconds'.format(opt_durr))
        if not haus:
            hdlist = []
            print('-- Generating quantiles of Hausdorf distance to known solution...')
            start_time = time.time()
            for i in range(isp):
                hdlist.append((res[i], incr, budget, testclass()))
            hddict = par_diff(hdlist, proc)
            qdat = gen_qdata(len(hddict), incr, budget, hddict)
            end_time = time.time()
            met_durr = end_time - start_time
            print('-- Metric computation run time: {0:.2f} seconds'.format(met_durr))
            print('-- Saving data in folder ', name, ' ...')
            save_files(name, humtxt, res, qdat)
        else:
            save_files(name, humtxt, res)
        print('-- Done!')
