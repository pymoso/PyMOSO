"""The solve and testsolve command"""

from .basecomm import *
from inspect import getmembers, isclass


class TestSolve(BaseComm):
    """Run experiments with a known solution"""
    def run(self):
        raise NotImplementedError('testsolve is not yet implemented ¯\_(ツ)_/¯. Use solve instead.')
