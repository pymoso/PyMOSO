#!/usr/bin/env python
"""
Summary
-------
Provide an implementation of R-MinRLE for users needing a
multi-objective simulation optimization solver.
"""
from ..chnbase import RLESolver
import sys


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
            print('--* R-MinRLE Error: No feasible warm start. Is x0 feasible?')
            print('--* Aborting.')
            sys.exit()
        return self.get_min(warm_start)
