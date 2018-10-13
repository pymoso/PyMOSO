"""The solve and testsolve command"""

from .basecomm import *
from inspect import getmembers, isclass
import sys
import os
from random import Random
import traceback
import importlib.util
import importlib
from ..chnutils import testsolve, par_diff, par_runs


class TestSolve(BaseComm):
    """Test a MOSO algorithm against a problem with a known solution."""
    def run(self):
        ## get the options with default values
        budget = int(self.options['--budget'])
        name = self.options['--odir']
        hasseed = self.options['--seed']
        metric = self.options['--metric']
        if hasseed:
            seed = tuple(int(i) for i in self.options['<s>'])
        else:
            seed = (12345, 12345, 12345, 12345, 12345, 12345)
        isp = int(self.options['--isp'])
        proc = int(self.options['--proc'])
        crn = self.options['--crn']
        ## determine the solver and problem
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
            print('--* Aborting.')
            sys.exit()
        except:
            print('Unknown error loading ', solvclass.__name__, '.')
            tstr = ''.join(traceback.format_exc())
            save_errortb(name, tstr)
            print('--* Aborting.')
            sys.exit()
        testarg = self.options['<tester>']
        base_mod_name = testarg
        if testarg.endswith('.py'):
            base_mod_name = os.path.basename(testarg).replace('.py', '')
            mod_name = '.'.join(['pymoso', 'solvers', base_mod_name])
            spec = importlib.util.spec_from_file_location(mod_name, testarg)
            tmodule = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(tmodule)
            sys.modules[mod_name] = tmodule
            tmodule = importlib.import_module(mod_name)
            testclasses = getmembers(tmodule, isclass)
            #testclass = [tc[1] for tc in testclasses if tc[0].lower() == mod_name][0]
        else:
            testclasses = getmembers(testers, isclass)
            #testclass = [tc[1] for tc in testclasses if tc[0] == testarg][0]
        ranx0 = False
        if self.options['<x>']:
            x0 = tuple(int(i) for i in self.options['<x>'])
        else:
            ranx0 = True
            x0 = (0,)
        try:
            fakeprn = Random()
            testclass = [tc[1] for tc in testclasses if tc[0].lower() == base_mod_name.lower()][0]
            if ranx0:
                testclass().get_ranx0(fakeprn)
            else:
                dim = testclass().ranorc(fakeprn).dim
                if not len(x0) == dim:
                    print('--* Error: x0 must have ', dim, ' components. ')
                    tstr = ''.join(traceback.format_exc())
                    save_errortb(name, tstr)
                    print('--* Aborting.')
                    sys.exit()
        except IndexError:
            print('--* Error: Tester not found or invalid. ')
            tstr = ''.join(traceback.format_exc())
            save_errortb(name, tstr)
            print('--* Aborting.')
            sys.exit()
        except AttributeError:
            print('--* Error: Please specify x0 or implement tester.get_ranx0, your tester cannot generate them randomly. ')
            tstr = ''.join(traceback.format_exc())
            save_errortb(name, tstr)
            print('--* Aborting.')
            sys.exit()
        except NameError:
            print('--* Error: Invalid tester or get_ranx0. Missing an import?')
            tstr = ''.join(traceback.format_exc())
            save_errortb(name, tstr)
            print('--* Aborting.')
            sys.exit()
        except:
            print('Unknown error loading ', testclass.__name__, '.')
            tstr = ''.join(traceback.format_exc())
            save_errortb(name, tstr)
            print('--* Aborting.')
            sys.exit()
        params = self.options['<param>']
        vals = self.options['<val>']
        solve_kwargs = dict()
        solve_kwargs['budget'] = budget
        solve_kwargs['seed'] = seed
        solve_kwargs['isp'] = isp
        solve_kwargs['proc'] = proc
        solve_kwargs['ranx0'] = ranx0
        solve_kwargs['crn'] = crn
        for i, p in enumerate(params):
            solve_kwargs[p] = float(vals[i])
        start_opt_time = time.time()
        print('** Testing ', solvarg, ' using ', testarg, ' **')
        stsstr = '-- using starting seed:'
        print(f'{stsstr:26} {seed[0]:12} {seed[1]:12} {seed[2]:12} {seed[3]:12} {seed[4]:12} {seed[5]:12}')
        res, end_seed = testsolve(testclass, solvclass, x0, **solve_kwargs)
        end_opt_time = time.time()
        opt_durr = end_opt_time - start_opt_time
        humtxt = gen_humanfile(name, testarg, solvarg, budget, opt_durr, params, vals, seed, end_seed)
        seed = tuple([int(i) for i in end_seed])
        print('-- Optimization run time: {0:.2f} seconds'.format(opt_durr))
        endstr = '-- ending seed:'
        print(f'{endstr:26} {seed[0]:12} {seed[1]:12} {seed[2]:12} {seed[3]:12} {seed[4]:12} {seed[5]:12}')
        save_metadata(name, humtxt)
        do_metrics = True
        mytester = testclass()
        if metric:
            try:
                mymet = mytester.metric
            except AttributeError:
                do_metrics = False
                print('--* Error: tester metric is not implemented! Skipping metric computation. ')
        try:
            if metric and do_metrics:
                print('-- Computing metric data')
                haus_start_time = time.time()
                hdd = par_diff(res, mytester, proc)
                haus_end_time = time.time()
                haus_durr = haus_end_time - haus_start_time
                print('-- Metric run time: {0:.2f} seconds'.format(haus_durr))
                for i in range(isp):
                    save_metrics(name, i, hdd[i])
        except TypeError as te:
            print('--* Error: ', sys.exc_info()[1])
            print('--* Check the implementation of', testclass.__name__, '.metric for bugs.')
            print('--* Saving error traceback.')
            tstr = ''.join(traceback.format_exc())
            save_errortb(name, tstr)
            print('--* Skipping metrics.')
        except NameError:
            print('--* Error: ', sys.exc_info()[1])
            print('--* Are you missing an import in', testclass.__name__, '?')
            print('--* Saving error traceback.')
            tstr = ''.join(traceback.format_exc())
            save_errortb(name, tstr)
            print('--* Skipping metrics.')
        except ValueError:
            print('--* Error: ', sys.exc_info()[1])
            print('--* Saving error traceback.')
            tstr = ''.join(traceback.format_exc())
            save_errortb(name, tstr)
            print('--* Skipping metrics.')
        except FileNotFoundError:
            print('--* Error: ', sys.exc_info()[1])
            print('--* Saving error traceback.')
            print('--* This shouldn\'t happen. Create a folder named ', name, '.')
            tstr = ''.join(traceback.format_exc())
            save_errortb(name, tstr)
            print('--* Skipping metrics.')
        except:
            print("--* Unexpected error: Skipping metrics. Error noted below. ")
            print('--* ', sys.exc_info()[0])
            print('--* ', sys.exc_info()[1])
            print('--* Saving error traceback.')
            tstr = ''.join(traceback.format_exc())
            save_errortb(name, tstr)
        for i in range(isp):
            save_isp(name, i, res[i]['itersoln'])
        print('-- Done!')
