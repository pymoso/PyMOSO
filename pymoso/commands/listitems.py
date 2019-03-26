"""Display all solvers, problems, and test problems"""

from .basecomm import *
from inspect import getmembers, isclass, ismodule


class ListItems(BaseComm):
    """
    Implements the CLI command listitems.

    See also
    --------
    BaseComm
    """
    def run(self):
        """
        Print the list of solvers, problems, and testers that are
        included in PyMOSO.
        """
        ## list of problem classes
        probclasses = getmembers(problems, isclass)
        ## list of solver classes
        solvclasses = getmembers(solvers, isclass)
        ## list of classes with test problems
        testclasses = getmembers(testers, isclass)
        ## print the solvers and their docstrings
        sstr = 'Solver'
        sstrund = '************************'
        descstr = 'Description'
        print(f'\n{sstr:30} {descstr:30}')
        print(f'{sstrund:30} {sstrund:30}')
        for s0, s1 in solvclasses:
            docstr = s1.__doc__.split('\n')[1].strip()
            print(f'{s0:30} {docstr:30}')
        ## print the problems, their docstrings, and determine if they have a
        ##      tester
        pstr = 'Problems'
        tstr = 'Test Name (if available)'
        print(f'\n{pstr:30} {descstr:60} {tstr:30}')
        print(f'{sstrund:30} {sstrund:60} {sstrund:30}')
        for p0, p1 in probclasses:
            ctlist = [t[0] for t in testclasses if issubclass(t[1]().ranorc, p1)]
            p2 = ctlist[0] if ctlist else ''
            docstr = p1.__doc__.split('\n')[1].strip()
            print(f'{p0:30} {docstr:60} {p2:30}')
