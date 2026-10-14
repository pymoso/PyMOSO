"""MOSOSolver subclasses written to the README's contract, for tests
that need a worker process to import them."""
from pymoso.chnbase import MOSOSolver


class DocumentedKeysOnly(MOSOSolver):
    """Returns exactly the three keys the README documents, and nothing
    the framework added later. Takes 10 replications of x0 per
    iteration."""

    def __init__(self, orc, **kwargs):
        self.sprn = kwargs.pop('sprn')
        self.x0 = kwargs.pop('x0')
        super().__init__(orc)

    def solve(self, budget):
        itersoln, simcalls, nu = {}, {}, 0
        while self.num_calls < budget:
            self.orc.hit(self.x0, 10)
            self.num_calls += 10
            itersoln[nu] = {self.x0}
            simcalls[nu] = self.num_calls
            nu += 1
        return {'itersoln': itersoln, 'simcalls': simcalls, 'endseed': self.orc.get_endseed()}


class ReportsItsHighWaterMark(DocumentedKeysOnly):
    """The same solver, also returning the key the framework reads."""

    def solve(self, budget):
        results = super().solve(budget)
        results['oracle_high_water_mark'] = self.orc.get_high_water_mark()
        return results
