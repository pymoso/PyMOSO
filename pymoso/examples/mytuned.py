from pymoso.solvers.rperle import RPERLE

class MyTunedRPERLE(RPERLE):
    '''R-PERLE with a parameter of its own.'''
    PARAMS = ('stubbornness',)

    def __init__(self, orc, **kwargs):
        # take this solver's own parameters before passing the rest on
        self.stubbornness = kwargs.pop('stubbornness', 1.0)
        super().__init__(orc, **kwargs)
