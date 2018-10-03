# import the R-MinRLE class - required
from pydovs.solvers.rminrle import RMINRLE

# create a subclass of RMINRLE
class MyAccel(RMINRLE):
    '''Example implementation of an R-MinRLE accelerator.'''

    def accel(self, warm_start):
        '''Return a collection of points to send to RLE.'''
        # implement efficient logic here. The following is a trivial example
        self.upsample(warm_start)
        return warm_start
