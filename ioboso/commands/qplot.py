"""Implements the qplot command"""

from .basecomm import *
from inspect import getmembers, isclass


class Qplot(BaseComm):
    """Generate quantile plot for an existing experiment"""
    def run(self):
        name = self.options['<expname>']
        
