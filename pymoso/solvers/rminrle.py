#!/usr/bin/env python
"""
Summary
-------
Provide an implementation of R-MinRLE for users needing a
multi-objective simulation optimization solver.
"""
from ..chnbase import RLESolver, _check_warm_start


class RMINRLE(RLESolver):
    """
    A solver using R-MinRLE for integer-ordered MOSO.

    See also
    --------
    chnbase.RLESolver
    """

    def accel(self, warm_start):
        """
        Compute a candidate ALES. RLESolvers require that this function
        is implemented.

        Parameters
        ----------
        warm_start : set of tuple of int

        Returns
        -------
        set of tuple of int
        """
        if not warm_start:
            raise ValueError('No feasible warm start. Is x0 feasible?')
        if self.nu > 1:
            # the estimate get_min makes first, made here so that a warm
            # start found infeasible is reported as that; get_min reuses it
            candidates = warm_start | {self.x0}
            self.upsample(candidates)
            _check_warm_start(self, candidates)
        return self.get_min(warm_start)
