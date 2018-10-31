#!/usr/bin/env python
from ..chnbase import RLESolver
import sys


class RMINRLE(RLESolver):
    """A solver using R-MinRLE for integer-ordered MOSO."""

    def accel(self, warm_start):
        if not warm_start:
            print('--* R-MinRLE Error: No feasible warm start. Is x0 feasible?')
            print('--* Aborting.')
            sys.exit()
        return self.get_min(warm_start)
