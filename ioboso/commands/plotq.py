"""Implements the qplot command"""

from .basecomm import *
from inspect import getmembers, isclass
from ioboso.simplotting import plot_hdquantplot
import sys

class PlotQ(BaseComm):
    """Save the plot and exit"""
    def run(self):
        expname = self.options['<expname>']
        show = False
        if self.options['--show']:
            show = True
        runmd = check_expname(expname)
        if not runmd:
            sys.exit('''   Warning!\n   Experiment does not exist! Make sure you have run the experiments and are in the parent directory.''')
        pref = expname + '/'
        suff = '_plt.pkl'
        budget = runmd['Budget']
        algoname = runmd['Algorithm']
        pname = runmd['Problem']
        names = (expname, )
        labels = {expname: algoname}
        savename = pref + expname + '_quant.pdf'
        plot_hdquantplot(names, labels, pref, suff, budget, savename, show)
