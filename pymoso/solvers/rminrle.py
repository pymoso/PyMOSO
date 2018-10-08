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

    def get_min(self, mcS):
        """return a minimum for every objective using spline"""
        self.upsample(mcS)
        unconst = float('inf')
        kcon = 0
        xmin = set()
        krange = range(self.num_obj)
        for k in krange:
            kmin = min(mcS, key=lambda t: self.gbar[t][k])
            _, xmink, _, _ = self.spline(kmin, unconst, k, kcon)
            xmin |= {xmink}
        return xmin
