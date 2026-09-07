'''
Example metric for a single-objective problem with one correct
solution x*, for use in PyMOSO. Computes |g(X) - g(x*)| for an
estimated solution X.

This is a fragment, not a whole tester: metric below is meant to be
copied into a tester class as an instance method. self.answer is
assumed to be a real number (the true objective value at x*) and
self.true_g the function computing the true objective value.
'''
def metric(self, singleton_set):
    # single objective algorithms still return a set
    point, = singleton_set
    # let self.soln be a real number
    dist = abs(self.true_g(point) - self.answer)
    return dist
