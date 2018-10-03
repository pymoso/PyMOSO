# pydovs

This project implements the R-PERLE algorithm for solving bi-objective simulation optimization problems on integer lattices and the R-MinRLE algorithm, a benchmark algorithm for solving multi-objective simulation optimization problems on integer lattices. THIS PROJECT IS IN ALPHA! Please email the authors with any issues.

## Reference
If you use this software for work leading to publications, please cite the article in which R-PERLE and R-MinRLE were proposed:

Cooper, K., Hunter, S. R., and Nagaraj, K. 2018. Bi-objective simulation optimization on integer lattices using the epsilon-constraint method in a retrospective approximation framework. Optimization Online, http://www.optimization-online.org/DB_HTML/2018/06/6649.html.

We also include an implementation of R-SPLINE, which can be cited as follows:

Wang, H., Pasupathy, R., and Schmeiser, B. W. 2013. Integer-ordered simulation optimization using R-SPLINE: Retrospective Search with Piecewise-Linear Interpolation and Neighborhood Enumeration. ACM Transactions on Modeling and Computer Simulation, Vol. 23, No. 3, Article 17 (July 2013), 24 pages. DOI:http://dx.doi.org/10.1145/2499913.2499916

## Installation
### Install Python 3.6+
This software requires Python 3.6 or higher. Python can be downloaded from https://www.python.org/downloads/.

### Install from PyPI
`pip install pydovs`

### Install latest trunk version from git
`pip install git+https://github.rcac.purdue.edu/HunterGroup/pydovs.git`

### Install from source
1. Install prerequisite packages.   
`pip install wheel docopt`
1. Download the project code either from  
https://github.rcac.purdue.edu/HunterGroup/pydovs/releases   
for the official releases or using  
`git clone git@github.rcac.purdue.edu:HunterGroup/pydovs.git`  
for the latest version.  
1. Navigate to the newly downloaded project directory containing setup.py and build the binary wheel.  
`python setup.py bdist_wheel`
1. Install the wheel.  
`pip install dist/pydovs-x.x.x-py3-none-any.whl`  
Replace the x.x.x with the correct file name corresponding to the code version. Modify the command to select the particular wheel you've built or downloaded.

## Command line help
```
pydovs

Usage:
  pydovs listitems
  pydovs solve [--budget=B] [--odir=D] [--radius=R] [--simpar=P]
    [(--seed <s> <s> <s> <s> <s> <s>)] [(--params <param> <val>)]...
    <problem> <solver> <x>...
  pydovs testsolve [--budget=B] [--odir=D] [--radius=R] [--isp=T] [--proc=Q]
    [(--seed <s> <s> <s> <s> <s> <s>)] [(--params <param> <val>)]...
    <tester> <solver> <x>...
  pydovs -h | --help
  pydovs -v | --version

Options:
  --budget=B                Simulation budget [default: 50000]
  --isp=T                   Number of independent sample paths of the algorithm to solve. [default: 1]
  --odir=D                  A name to assign to the output. [default: testrun]
  --simpar=P                Number of processes available for simulation replications. [default: 1]
  --seed                    Specify a seed by entering 6 spaced integers > 0.
  --radius=R                Specify a neighborhood radius. [default: 1]
  --proc=Q                  Total number of processes to make available to pydovs. [default: 1]
  --params                  Allows specifying a <param> <val> pair.
  -h --help                 Show this screen.
  -v --version              Show version.

Examples:
  pydovs listitems
  pydovs solve ProbTPA RPERLE 4 14
  pydovs solve --budget=100000 --odir=test1 --radius=3 ProbTPB RMINRLE 3 12
  pydovs solve --seed 12345 32123 5322 2 9543 666666666 ProbTPC RPERLE 31 21 11
  pydovs solve --parsim --proc=4 --params betaeps 0.4 ProbTPA RPERLE 30 30
  pydovs solve --params betaeps 0.7 --params betadel 0.5 ProbTPA RPERLE 45 45
  pydovs solve ProbSimpleSO RSPLINE 97
  pydovs testsolve --isp=10 --proc=10 ProbTPA RMINRLE 32 32
```
The `<x>` argument cannot take negative numbers from the command line. Use the commands in a Python program if a negative starting point is required (see examples below).

## Programming guide
### Example problem (myproblem.py)
```
# import the Oracle base class
from pydovs.chnbase import Oracle

class MyProblem(Oracle):
    '''Example implementation of a user-defined MOSO problem.'''
    def __init__(self, rng):
        '''Specify the number of objectives and dimensionality of points.'''
        self.num_obj = 2
        self.dim = 1
        super().__init__(rng)

    def g(self, x, rng):
        '''Check feasibility and simulate objective values.'''
        # feasible values for x in this example
        feas_range = range(-100, 101)
        # initialize obj to empty and is_feas to False
        obj = []
        is_feas = False
        # check that dimensions of x match self.dim
        if len(x) == self.dim:
            is_feas = True
            # then check that each component of x is in the range above
            for i in x:
                if not i in feas_range:
                    is_feas = False
        # if x is feasible, simulate the objectives
        if is_feas:
            #use rng to generate random numbers
            z0 = rng.normalvariate(0, 1)
            z1 = rng.normalvariate(0, 1)
            obj1 = x[0]**2 + z0
            obj2 = (x[0] - 2)**2 + z1
            obj = (obj1, obj2)
        return is_feas, obj

```
To set up a problem to solve, typically a Monte Carlo simulation oracle, follow the example above which can be used with the `solve` command. Subclass the Oracle class shipped with pydovs. Implement `__init__` and `g` with the signatures `__init__(self, rng)` and `g(self, x, rng)`. For `__init__`, it's enough to set the desired values for the number of objectives, `self.num_obj`, and the dimensionality of the feasible domain, `self.dim`.  

The function `g` must run one simulation at the feasible point `x`. The return values must be ordered correctly. The first value is a boolean (`True` or `False`) indicating whether `x` is feasible. It is up to the programmer to implement the feasibility check. The second value is a tuple of length `self.num_obj` where each element is a number indicating one of the objective values. The simulation doesn't necessarily have to be implemented in Python, but of course the implementation of `g` must be valid Python code. For example, `g` may wrap a function call to a C library which runs the simulation and returns the objectives.  

The `rng` parameter is a subclass of Python's built-in `random.Random()` class and implements the same methods. Thus, its used in the same way as a `random.Random()` object for programmers implementing their simulations in Python. For example, `rng.random()`, `rng.normalvariate()`, `rng.normalvariate(4, 7)`, and `rng.getState()` are valid. The generator uses mrg32k3a as it's backbone and uses Beasley-Springer-Moro to generate normal random variates.  

Once implemented, the problem can be solved with, say, R-PERLE using the following command. For your problem, choose an appropriate starting point.  
`pydovs solve myproblem.py RPERLE 97`

### Example tester (mytester.py)
```
import sys, os
sys.path.insert(0,os.path.dirname(__file__))
# import an the MyProblem oracle
from myproblem import MyProblem

# implement a function that generates the expected value of g(x) in myproblem.py
def true_g(x):
    '''Compute the objective values.'''
    obj1 = x[0]**2
    obj2 = (x[0] - 2)**2
    return obj1, obj2

# the solution is the image of all local efficient sets, a list of sets
soln = [{(0, 4), (4, 0), (1, 1)}]

class MyTester(object):
    '''Example tester implementation for MyProblem.'''
    def __init__(self):
        self.ranorc = MyProblem
        self.true_g = true_g
        self.soln = soln

```
To test a problem using the `testsolve` command, implement a `Tester` object as above. The only strict pydovs requirement is that a tester is a class with a member called `ranorc` which is an Oracle class. To generate useful test metrics, programmers may find it convenient to include a solution and a function which can generate the expected values of the objectives of the oracle.  Once implemented, the tester can be solved as follows.  
`pydovs testsolve mytester.py RPERLE 97`

### Example accelerator
```
from pydovs.chnbase import RLESolver

# create a subclass of RLESolver
class MyAccel(RLESolver):
    '''Example implementation of an R-MinRLE accelerator.'''

    def accel(self, warm_start):
        '''Return a collection of points to send to RLE.'''
        # bring up the sample sizes of the "warm start"
        self.upsample(warm_start)
        return warm_start
```
Programmers can use pydovs to create new algorithms that use RLE for convergence. The novel part of these algorithms will be the `accel` function, which should efficiently collect points to send to RLE for certification. The function `accel` must have the signature `accel(self, warm_start)` where `warm_start` is a set of tuples. The tuples are feasible points. The pydovs method, shown above, allows programmers to easily implement and test these accelerators. These accelerators are to be used in a retrospective approximation framework.  Every retrospective iterations, pydovs will first call `accel(self, warm_start)` and send the returned set to `RLE`. The return value must be a set of tuples, where each tuple is a feasible point. The implementer does not need to implement or call `RLE`.

### Class Structure and internal functions
The base class `MOSOSolver` implements basic members required to solve MOSO problems. Its subclass `RASolver` provides the machinery needed to quickly implement a retrospective approximation algorithm. It's child class, `RLESolver`, allows quick implementation of MOSO solvers that use `RLE` to ensure convergence, as shown in the example accelerator. Oracles are the problems that pydovs can solve. Here, we provide a listing of the important objects available to pydovs programmers who are implementing MOSO algorithms.

| pydovs object | Example | Description |
| ------------- | ------- | ----------- |
| `Oracle.hit(x, m)` | `isfeas, gx, se = Oracle.hit(x, 4)` | Call the simulation 4 times and compute the mean value and standard error of each objective at `x`. |
| `MOSOSolver.orc` |  | The simulation oracle object which can be called. |

| `RASolver.gbar`   | `objs = self.gbar[x]` | A dictionary of the estimated values for visited points in the current retrospective iteration. |
| `RASolver.sehat` | `seobjs = self.sehat[x]`| A dictionary of the estimated standard errors for visited points in the current retrospective iteration. |
| `RASolver.estimate(x, )` | 'gx, se = self.estimate(x, )'

### Solve example
```
# import the solve function
from pydovs.chnutils import solve
# import the module containing the RPERLE implementation
import pydovs.solvers.rperle as rp
# import MyProblem - myproblem.py should usually be in the script directory
import myproblem as mp

# specify an x0. In MyProblem, it is a tuple of length 1
x0 = (97,)
soln = solve(mp.MyProblem, rp.RPERLE, x0)
print(soln)

```

The `solve` function can take keyword arguments. The keyword values correspond to options in the command line help.
Here is a listing: `radius`, `budget`, `simpar`, `seed`.

### TestSolve example
```
# import the testsolve functions
from pydovs.chnutils import testsolve
# import the module containing RPERLE
import pydovs.solvers.rperle as rp
# import the MyTester class
from mytester import MyTester

# choose a feasible starting point of MyProblem
x0 = (97,)
run_data = testsolve(MyTester, rp.RPERLE, x0)
print(run_data)
```

The `testsolve` function can take keyword arguments. The keyword values correspond to options in the command line help.
Here is a listing: `radius`, `budget`, `seed`, `isp`, `proc`.
