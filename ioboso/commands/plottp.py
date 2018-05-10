"""Plot a Test Problem"""

from .basecomm import *
from inspect import getmembers, isclass
from ioboso.simplotting import plot_testproblem


class Solve(BaseComm):
    """Save the plot and exit"""
    def run(self):
        testarg = self.options['<tester>']
        testmod = getattr(testcases, testarg)
        show = False
        print('hi........')
        if self.options['--show']:
            show = True
        tp = testmod()
        print('***** Generating plot data ****')
        plot_testproblem(tp, show)
        print('..... Done! .....')
