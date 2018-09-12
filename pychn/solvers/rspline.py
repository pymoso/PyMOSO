#!/usr/bin/env python
from ..chnbase import RASolver


class RSPLINE(RASolver):
    """A solver using R-SPLINE for single objective SO."""

    def spsolve(self, warm_start):
        _, xmin, _, _ = self.spline(warm_start)
        return xmin
