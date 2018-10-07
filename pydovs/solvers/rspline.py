#!/usr/bin/env python
from ..chnbase import RASolver
import sys


class RSPLINE(RASolver):
    """A solver using R-SPLINE for single objective SO."""

    def spsolve(self, warm_start):
        """Use SPLINE to get a sample path minimizer."""
        # warm_start is a singleton set, so extract the item
        warm_start = self.upsample(warm_start)
        if not warm_start:
            print('--* R-SPLINE Error: Empty warm start. Is x0 feasible?')
            print('--* Aborting. ')
            sys.exit()
        ws = warm_start.pop()
        _, xmin, _, _ = self.spline(ws)
        # return a singleton set
        return {xmin}
