#!/usr/bin/env python
from ..chnbase import RASolver


class RSPLINE(RASolver):
    """A solver using R-SPLINE for single objective SO."""

    def spsolve(self, warm_start):
        ws = warm_start.pop()
        isfeas, _, _ = self.estimate(ws)
        if isfeas:
            _, xmin, _, _ = self.spline(ws)
        else:
            # ¯\_(ツ)_/¯
            xmin = ws
        return {xmin}
