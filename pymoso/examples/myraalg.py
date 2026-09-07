from pymoso.chnbase import RASolver

class MyRAAlg(RASolver):
    '''Template implementation of an RA solver.'''

    def spsolve(self, warm_start):
        '''Return the sample path solution.'''
        # implement algorithm logic here and return a set
        return warm_start
