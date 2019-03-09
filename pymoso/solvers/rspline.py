#!/usr/bin/env python
"""
Summary
-------
Provide an implementation of R-SPLINE for users needing a 
single-objective simulation optimization solver. 
"""
from ..chnbase import RASolver
import sys


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
        warm_start = self.upsample(warm_start)
        if not warm_start:
            print('--* R-SPLINE Error: Empty warm start. Is x0 feasible?')
            print('--* Aborting. ')
            sys.exit()
        ws = warm_start.pop()
        _, xmin, _, _ = self.spline(ws)
        # return a singleton set
        return {xmin}
