"""The solve and testsolve command"""

from .basecomm import *
from inspect import getmembers, isclass
import sys
import os
from random import Random
import traceback
import importlib.util
from ..chnutils import solve


class Solve(BaseComm):
    """Solve a bi-objective simulation optimization problem using cli params"""
    def run(self):
        ## get the options with default values
        budget = int(self.options['--budget'])
        name = self.options['--odir']
        hasseed = self.options['--seed']
        simpar = int(self.options['--simpar'])
        crn = self.options['--crn']
        if hasseed:
            seed = tuple(int(i) for i in self.options['<s>'])
        else:
            seed = (12345, 12345, 12345, 12345, 12345, 12345)
        ## determine the solver and problem
        probarg = self.options['<problem>']
        base_mod_name = probarg
        if probarg.endswith('.py'):
            base_mod_name = os.path.basename(probarg).replace('.py', '')
            mod_name = '.'.join(['pymoso', 'problems', base_mod_name])
            spec = importlib.util.spec_from_file_location(mod_name, probarg)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            sys.modules[mod_name] = module
            pmodule = importlib.import_module(mod_name)
            probclasses = getmembers(module, isclass)
            #probclass = [prob[1] for prob in probclasses if prob[0].lower() == mod_name][0]
        else:
            probclasses = getmembers(problems, isclass)
        try:
            probclass = [prob[1] for prob in probclasses if prob[0].lower() == base_mod_name.lower()][0]
        except IndexError:
            print('--* Error: Problem name is not valid.')
            tstr = ''.join(traceback.format_exc())
            save_errortb(name, tstr)
            print('--* Aborting. ')
            sys.exit()
        except:
            print('--* Unknown Error loading ', probclass.__name__, '.')
            tstr = ''.join(traceback.format_exc())
            save_errortb(name, tstr)
            print('--* Aborting. ')
            sys.exit()
        solvarg = self.options['<solver>']
        base_mod_name = solvarg
        if solvarg.endswith('.py'):
            base_mod_name = os.path.basename(solvarg).replace('.py', '')
            mod_name = '.'.join(['pymoso', 'solvers', base_mod_name])
            spec = importlib.util.spec_from_file_location(mod_name, solvarg)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            sys.modules[mod_name] = module
            smodule = importlib.import_module(mod_name)
            solvclasses = getmembers(smodule, isclass)
            #solvclass = [sol[1] for sol in solvclasses if sol[0].lower() == base_mod_name][0]
        else:
            solvclasses = getmembers(solvers, isclass)
            #solvclass = [sol[1] for sol in solvclasses if sol[0] == solvarg][0]
        try:
            solvclass = [sol[1] for sol in solvclasses if sol[0].lower() == base_mod_name.lower()][0]
        except IndexError:
            print('--* Error: Solver not found or invalid. ')
            tstr = ''.join(traceback.format_exc())
            save_errortb(name, tstr)
            print('--* Aborting. ')
            sys.exit()
        except:
            print('--* Unknown Error loading ', solvclass.__name__, '.')
            tstr = ''.join(traceback.format_exc())
            save_errortb(name, tstr)
            print('--* Aborting. ')
            sys.exit()
        x0 = tuple(int(i) for i in self.options['<x>'])
        fakeprn = Random()
        dim = probclass(fakeprn).dim
        if not len(x0) == dim:
            print('Error: x0 must have ', dim, ' component(s). ')
            print('--* Aborting. ')
            sys.exit()
        ## get the optional parameter names and values if specified
        params = self.options['<param>']
        vals = self.options['<val>']
        solve_kwargs = dict()
        solve_kwargs['budget'] = budget
        solve_kwargs['seed'] = seed
        solve_kwargs['simpar'] = simpar
        solve_kwargs['crn'] = crn
        for i, p in enumerate(params):
            solve_kwargs[p] = float(vals[i])
        start_opt_time = time.time()
        print('** Solving ', probarg, ' using ', solvarg, ' **')
        stsstr = '-- using starting seed:'
        print(f'{stsstr:26} {seed[0]:12} {seed[1]:12} {seed[2]:12} {seed[3]:12} {seed[4]:12} {seed[5]:12}')
        res, end_seed = solve(probclass, solvclass, x0, **solve_kwargs)
        end_opt_time = time.time()
        opt_durr = end_opt_time - start_opt_time
        humtxt = gen_humanfile(name, probarg, solvarg, budget, opt_durr, params, vals, seed, end_seed)
        seed = tuple([int(i) for i in end_seed])
        print('-- Run time: {0:.2f} seconds'.format(opt_durr))
        endstr = '-- next seed:'
        print(f'{endstr:26} {seed[0]:12} {seed[1]:12} {seed[2]:12} {seed[3]:12} {seed[4]:12} {seed[5]:12}')
        print('-- Saving data and details in folder ', name, ' ...')
        strlst = [str(lep) for lep in res]
        resstr = '\n'.join(strlst)
        save_metadata(name, humtxt)
        save_les(name, resstr)
        print('-- Done!')
