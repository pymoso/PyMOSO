# import the simulation oracle we just implemented
from myproblem import MyProblem

# implement a function that generates the expected value of g(x) in myproblem.py
def true_g(x):
    '''Compute the objective values.'''
    obj1 = x[0]**2
    obj2 = x[0]**2
    return obj1, obj2

# the solution is the images of local efficient sets as a list of sets
soln = [{(0, 4), (4, 0), (1, 1)}]

class MyTester(object):
    '''Example tester implementation of MyProblem and its solution.'''
    def __init__(self):
        self.ranorc = MyProblem
        self.true_g = true_g
        self.soln = soln
