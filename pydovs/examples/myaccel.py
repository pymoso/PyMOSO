# import the R-MinRLE class - required
from pychn.solvers.rminrle import RMINRLE

# create a subclass of RMINRLE
class MyAccel(RMINRLE):
    '''Example implementation of an R-MinRLE accelerator.'''

    def accel(self, aold):
        '''Return a collection of points to send to RLE.'''
        # bring up the sample sizes of the "warm start" aold
        self.upsample(aold)
        # determine the number of objectives returned by the oracle
        dr = range(self.num_obj)
        # initialize an empty set
        new_mins = set()
        # set a value to run spline unconstrained
        unconst = float('inf')
        for i in dr:
            for a in aold:
                # use spline to acquire a sample path minimizer
                _, spmin, _, _  = self.spline(a, unconst, i, i)
                # keep the union of the set of minimizers
                new_mins |= spmin
        return new_mins
