from pymoso.chnbase import RLESolver

# create a subclass of RLESolver
class MyAccel(RLESolver):
    '''Example implementation of an R-MinRLE accelerator.'''

    def accel(self, warm_start):
        '''Return a collection of points to send to RLE.'''
        # implement efficient logic here. The following is a trivial example
        self.upsample(warm_start)
        return warm_start
