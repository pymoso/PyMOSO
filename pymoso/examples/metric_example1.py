'''
Example metric for a MOSO problem with multiple local efficient sets
(LES), for use in PyMOSO. Computes the Hausdorff distance from the true
image of an estimated solution to the closest true LES.

This is a fragment, not a whole tester: metric below is meant to be
copied into a tester class as an instance method. self.answer is
assumed to be a list of sets (one per true LES) and self.true_g the
function computing true objective values, as in mytester.py.
'''
from pymoso.chnutils import dh


def metric(self, eles):
    # use the distance to the closest set.
    epareto = [self.true_g(point) for point in eles]
    # self.soln is a list of sets
    dist_list = [dh(epareto, les) for les in self.answer]
    return min(dist_list)
