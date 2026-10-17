#!/usr/bin/env python
"""
Summary
-------
Provide an implementation of R-SPLINE for users needing a 
single-objective simulation optimization solver. 
"""
from ..chnbase import RASolver, _check_warm_start


class RSPLINE(RASolver):
    """
    R-SPLINE solver for single-objective simulation optimization.
    
    Parameters
    ----------
    orc : chnbase.Oracle object
	kwargs : dict
	
	See also
	--------
	chnbase.RASolver
    """

    def __init__(self, orc, **kwargs):
        if orc.num_obj > 1:
            print('--* Warning: R-SPLINE operates on single objective problems!')
            print('--* Continuing: R-SPLINE will optimize only the first objective.')
        super().__init__(orc, **kwargs)

    def spsolve(self, warm_start):
        """
        Use SPLINE to solve the sample path problem. 
        
        Parameters
        ----------
        warm_start : set of tuple of int
			For RSPLINE, this is a singleton set
		
		Returns
		-------
		set of tuple of int
			For RSPLINE, this is a singleton set containing the sample
			path minimizer
        """
        # warm_start is a singleton set, so extract the item
        candidate = next(iter(warm_start))
        # x0 is estimated again every iteration, as R-PE, R-PERLE and
        # R-MinRLE do, and the search starts from x0 if its estimate is
        # better than the warm start's (docs/phase7-plan.md, step 7)
        candidates = {candidate, self.x0}
        feasible = self.upsample(candidates)
        _check_warm_start(self, candidates)
        if not feasible:
            # iteration 1, where the warm start is x0
            raise ValueError(
                'x0={0} is infeasible. RA solvers require a feasible starting point.'.format(self.x0)
            )
        ws = candidate
        if self.gbar[self.x0][0] < self.gbar[ws][0]:
            ws = self.x0
        _, xmin, _, _ = self.spline(ws)
        # return a singleton set
        return {xmin}
