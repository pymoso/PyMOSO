#!/usr/bin/env python
from ..chnbase import RASolver


class RSPLINE(RASolver):
    """A solver using R-SPLINE for single objective SO."""

    def spsolve(self, warm_start):
        """Use SPLINE to get a sample path minimizer."""
        # warm_start is a singleton set, so extract the item
        self.upsample(warm_start)
        ws = warm_start.pop()
        _, xmin, _, _ = self.spline(ws)
        # return a singleton set
        return {xmin}
