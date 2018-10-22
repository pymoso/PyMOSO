import sys, os
sys.path.insert(0,os.path.dirname(__file__))
# use hausdorff distance (dh) as an example metric
from pymoso.chnutils import dh
# import the MyProblem oracle
from myproblem import MyProblem

# optionally, define a function to randomly choose a MyProblem feasible x0
def get_ranx0(rng):
    val = rng.choice(range(-100, 101))
    x0 = (val, )
    return x0

# compute the true values of x, for computing the metric
def true_g(x):
    '''Compute the objective values.'''
    obj1 = x[0]**2
    obj2 = (x[0] - 2)**2
    return obj1, obj2

# define an answer as appropriate for the metric
myanswer = {(0, 4), (4, 0), (1, 1)}

class MyTester(object):
    '''Example tester implementation for MyProblem.'''
    def __init__(self):
        self.ranorc = MyProblem
        self.answer = myanswer
        self.true_g = true_g
        self.get_ranx0 = get_ranx0

    def metric(self, eles):
        '''Metric to be computed per retrospective iteration.'''
	epareto = [self.true_g(point) for point in eles]
        haus = dh(epareto, self.answer)
        return haus
