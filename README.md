# PyMOSO

This project implements the R-PERLE algorithm for solving bi-objective simulation optimization problems on integer lattices and the R-MinRLE algorithm, a benchmark algorithm for solving multi-objective simulation optimization problems on integer lattices. This project is in beta! Please contact us here regarding issues.

## Reference
If you use this software for work leading to publications, please cite the article in which R-PERLE and R-MinRLE were proposed:

Cooper, K., Hunter, S. R., and Nagaraj, K. 2018. Bi-objective simulation optimization on integer lattices using the epsilon-constraint method in a retrospective approximation framework. Optimization Online, http://www.optimization-online.org/DB_HTML/2018/06/6649.html.

We also include an implementation of R-SPLINE, which can be cited as follows:

Wang, H., Pasupathy, R., and Schmeiser, B. W. 2013. Integer-ordered simulation optimization using R-SPLINE: Retrospective Search with Piecewise-Linear Interpolation and Neighborhood Enumeration. ACM Transactions on Modeling and Computer Simulation, Vol. 23, No. 3, Article 17 (July 2013), 24 pages. DOI:http://dx.doi.org/10.1145/2499913.2499916

Table of Contents
=================

   * [PyMOSO](#pymoso)
      * [Reference](#reference)
      * [Installation](#installation)
         * [Dependency: Python 3.6 ](#dependency-python-36)
         * [Install from PyPI](#install-from-pypi)
         * [Install latest trunk version from git](#install-latest-trunk-version-from-git)
         * [Install from source](#install-from-source)
      * [CLI](#cli)
         * [listitems](#listitems)
         * [solve](#solve)
         * [testsolve](#testsolve)
         * [Output](#output)
         * [Table of options for solve and testsolve](#table-of-options-for-solve-and-testsolve)
         * [Table of algorithm-specific parameters](#table-of-algorithm-specific-parameters)
      * [Implementing problems, testers, and algorithms in PyMOSO](#implementing-problems-testers-and-algorithms-in-pymoso)
         * [Implementing a problem in PyMOSO](#implementing-a-problem-in-pymoso)
            * [Template for implementing problems (myproblem.py)](#template-for-implementing-problems-myproblempy)
            * [Using rng](#using-rng)
            * [Simple example problem](#simple-example-problem)
         * [Implementing a Tester in PyMOSO](#implementing-a-tester-in-pymoso)
         * [Implementing algorithms in PyMOSO](#implementing-algorithms-in-pymoso)
            * [Example MOSO algorithm in PyMOSO that uses RLE to ensure convergence (myaccel.py)](#example-moso-algorithm-in-pymoso-that-uses-rle-to-ensure-convergence-myaccelpy)
            * [Example of an RA algorithm (myraalg.py)](#example-of-an-ra-algorithm-myraalgpy)
            * [Example of a MOSO algorithm (mymoso.py)](#example-of-a-moso-algorithm-mymosopy)
            * [PyMOSO internals](#pymoso-internals)
               * [Table of PyMOSO internals](#table-of-pymoso-internals)
               * [Table of chnutils functions](#table-of-chnutils-functions)
            * [Useful snippets for implementing RA algorithms](#useful-snippets-for-implementing-ra-algorithms)
               * [Sample a point](#sample-a-point)
               * [Sample the point's neighbors](#sample-the-points-neighbors)
               * [argsort the points by 1st objective](#argsort-the-points-by-1st-objective)
               * [choose the minimizer and its objectives](#choose-the-minimizer-and-its-objectives)
               * [Use SPLINE to get a local minimizer](#use-spline-to-get-a-local-minimizer)
               * [Get the non-dominated subset of every visited point](#get-the-non-dominated-subset-of-every-visited-point)
               * [Randomly choose points from the subset](#randomly-choose-points-from-the-subset)
      * [Using PyMOSO in Python programs](#using-pymoso-in-python-programs)
         * [Solve example](#solve-example)
         * [TestSolve example](#testsolve-example)

## Installation
### Dependency: Python 3.6+
This software requires Python 3.6 or higher. Python can be downloaded from https://www.python.org/downloads/.

### Install from PyPI
`pip install pymoso`

### Install latest trunk version from git
`pip install git+https://github.rcac.purdue.edu/HunterGroup/pymoso.git`

### Install from source
1. Install prerequisite packages.   
`pip install wheel docopt`
1. Download the project code either from  
https://github.rcac.purdue.edu/HunterGroup/pymoso/releases   
for the official releases or using  
`git clone git@github.rcac.purdue.edu:HunterGroup/pymoso.git`  
for the latest version.  
1. Navigate to the newly downloaded project directory containing setup.py and build the binary wheel.  
`python setup.py bdist_wheel`
1. Install the wheel.  
`pip install dist/pymoso-x.x.x-py3-none-any.whl`  
Replace the x.x.x with the correct file name corresponding to the code version. Modify the command to select the particular wheel you've built or downloaded.

## CLI
```
Usage:
  pymoso listitems
  pymoso solve [--budget=B] [--odir=D] [--crn] [--simpar=P]
    [(--seed <s> <s> <s> <s> <s> <s>)] [(--param <param> <val>)]...
    <problem> <solver> <x>...
  pymoso testsolve [--budget=B] [--odir=D] [--crn] [--isp=T] [--proc=Q]
    [--metric] [(--seed <s> <s> <s> <s> <s> <s>)] [(--param <param> <val>)]...
    <tester> <solver> [<x>...]
  pymoso -h | --help
  pymoso -v | --version

Options:
  --budget=B                Set the simulation budget [default: 200]
  --odir=D                  Set the output file directory name. [default: testrun]
  --crn                     Set if common random numbers are desired.
  --seed                    Set the random number seed with 6 spaced integers.
  --simpar=P                Set number of parallel processes for simulation replications. [default: 1]
  --isp=T                   Set number of algorithm instances to solve. [default: 1]
  --proc=Q                  Set number of parallel processes for the algorithm instances. [default: 1]
  --metric                  Set if metric computation is desired.
  --param                   Specify a solver-specific parameter <param> <val>.
  -h --help                 Show this screen.
  -v --version              Show version.

Examples:
  pymoso listitems
  pymoso solve ProbTPA RPERLE 4 14
  pymoso solve --budget=100000 --odir=test1  ProbTPB RMINRLE 3 12
  pymoso solve --seed 12345 32123 5322 2 9543 666666666 ProbTPC RPERLE 31 21 11
  pymoso solve --simpar=4 --param betaeps 0.4 ProbTPA RPERLE 30 30
  pymoso solve --param radius 3 ProbTPA RPERLE 45 45
  pymoso testsolve --isp=16 --proc=4 TPATester RPERLE
  pymoso testsolve --isp=20 --proc=10 --metric --crn TPBTester RMINRLE 9 9

Help:
  Use the listitems command to view a list of available solvers, problems, and
  test problems.
```
For now, PyMOSO has three commands: `listitems`, `solve`, and `testsolve`, which we explain below.
### listitems
The command `listitems` shows the PyMOSO objects (problems, testers, solvers) included in the default installation. The identifiers can be used as arguments to `solve` and `testsolve`. PyMOSO objects implemented by users will not show up when using `listitems`.
### solve
The `solve` command is intended for practitioners seeking to a solve a simulation optimization problem. Three arguments are required: `<problem>`, `<solver>`, and  `<x>...`. For `<problem>`, users may specify an identifier for a built-in problem. A list of such identifiers can be viewed using `listitems`. Alternatively, users may implement their own problem as a PyMOSO oracle (see the code examples below) and specify the file name.
For example,  
`pymoso solve myproblem.py RPERLE 40 40`  
The `<solver>` argument again either an identifier to a built-in algorithm, or a file name for a user-implemented algorithm. The `<x>...` is a feasible starting point for the algorithm, with each component of the starting point separated by a space. Any number of the options listed above can also be specified before the arguments. At the end of this section, we list the options and provide more detailed explanations. The `<x>` argument cannot take negative numbers from the command line. Use PyMOSO in a Python program if a negative starting point is required (see examples below).   
### testsolve
The `testsolve` command is intended for researchers creating new simulation optimization algorithms.  Two arguments are required: `<tester>` and `<solver>`. Similar to `solve`, `<tester>` and `<solver>` may be specified as identifiers to built-in testers or as Python files containing user-implemented objects. Specifying `<x>...` is optional: testers may implement a method to generate feasible starting points. If not, then `<x>...` can be provided.  
### Output
Both `solve` and `testsolve` create a subdirectory within the working directory in which the generated results are saved. In the case of `solve`, the directory typically contains two files: a file containing metadata such as the arguments and options specified, date, run time, and more. The second file contains the solution generated by the chosen solver. If applicable, an error file may be generated. If an error is generated, users may send the metadata file, the error file, and any user-implemented PyMOSO objects to us for assistance. In the case of `testsolve`, the file containing the solution will instead contain multiple solutions, with the last row containing the end solution returned by the algorithm. The intermediate solutions are provided to give a researchers a sense of how the algorithm progresses. If the `--isp` option is specified to generate multiple independent sample path solutions, there will a solution file for every independent sample path. If the `--metric` options is specified, the metric defined in the `<tester>` will be computed on the solutions and saved in a separate file.  All available options to `solve` or `testsolve` are specified below.  

### Table of options for solve and testsolve
| Option | Description |
| ----------- | ----------- |
|`--budget=B`| The simulation budget limits the number of simulations the algorithm can use to generate a solution. `B` should be a natural number. |
|`--odir=D`| Specify the name of the directory that will contain the program output. Be sure to use different names so that previous experiments aren't over-written. |
|`--crn` | Turn on common random numbers. For some problems, this will make algorithms that support CRN more effective. |
|`--seed`| Specify a seed for the internal PyMOSO `mrg32k3a` generator. The seed is 6 integers separated by spaces. E.g. `--seed 1 2 3 4 5 6`|
|`--simpar=P`| Simulation replications can be taken in parallel. That is, for example, when obtaining 10 observations of a problem for some `x`, PyMOSO will split the work across `P` processes. This is desirable on complex problems, e.g. such that a single observation takes on the order of at least 1 scecond. Works only with `solve`.|
|`--isp=T`| Only available to `testsolve`, specify the number of algorithm instances to solve where the simulation observations are generated independently. The `<tester>` can optionally a method to randomly generate a different feasible starting point for each algorithm instance. |
|`--proc=Q`| Specify the number of parallel processes available to run the independent algorithm instances. Only use if `--isp=T > 1`.|
|`--metric`| If a metric is defined in `<tester>` the `testsolve` will compute the metric on the generated solutions and save the results. |
|`--param <param> <val>`| Specify a parameter by name and value. These are algorithm-specific parameters.|


### Table of algorithm-specific parameters
| Algorithm | Parameter | Default | Description |
| --------- | --------- | ------- | ----------- |
| `RPERLE`, `RMINRLE`, `RPE`, `RSPLINE` | `mconst` | `2` | Sets the initial sample size, and subsequent schedule of sample sizes. |
| `RPERLE`, `RMINRLE`, `RPE`, `RSPLINE` | `mconst` | `8` | Affects the initial search sampling limit, and subsequent schedule of limits. |
| `RPERLE`, `RMINRLE`, `RPE`, `RSPLINE` | `radius` | `1` | Sets radius that determines a point's neighborhood.|
| `RPERLE`, `RMINRLE` | `betadel` | `0.5` | Roughly, affects how likely it is for RLE to keep its given solution. See http://www.optimization-online.org/DB_HTML/2018/06/6649.html. |
| `RPERLE` and `RPE` | `betaeps` | `0.5`   | Roughly, affects how likely PE will perform a search from a point. See http://www.optimization-online.org/DB_HTML/2018/06/6649.html. |

## Implementing problems, testers, and algorithms in PyMOSO
### Implementing a problem in PyMOSO
Users can implement their own problems in PyMOSO using `myproblem.py` below as the template. The function signatures of `__init__` and `g` must remain the same as shown. Furthermore, in `__init__`, the only changes will be to set `self.num_obj` and `self.dim` as appropriate. The `g` function needs to implement a single simulation observation at `x`, a Python tuple of length `self.dim` representing some point. The function `g` can be a wrapper to external simulation or other programs, but must return two values:
1. `True` or `False` depending on if `x` is feasible to the problem.
1. A tuple of length `self.num_obj` containing the value of each objective.

#### Template for implementing problems (myproblem.py)
```python
# import the Oracle base class
from pymoso.chnbase import Oracle

class MyProblem(Oracle):
    '''Example implementation of a user-defined MOSO problem.'''
    def __init__(self, rng):
        '''Specify the number of objectives and dimensionality of points.'''
        self.num_obj = 2
        self.dim = 1
        super().__init__(rng)

    def g(self, x, rng):
        '''Check feasibility and simulate objective values.'''
        # set is_feas = True or False, if x is feasible or not
        # if feasible, compute the objectives such that
        ## obj is a tuple of length self.num_obj
        # if not feasible, set each objective to None
        # this function can be a wrapper to, e.g. a C simulation or
        ## other simulation software
        return is_feas, (obj1, obj2)
```

#### Using `rng`
Though not required, users may use the `rng` random number generator object. Doing so allows algorithms to take advantage of common random numbers and ensures parallelized simulation replications are independent. The implementation of the `rng` object is a subclass of Python's `random.Random()` where the underlying generator is `mrg32k3a`. Thus, Python's own `random` documentation applies to `rng` and can be found at https://docs.python.org/3/library/random.html. We follow the example of L'Ecuyer et al. 2001 for `mrg32k3a` and implementing its independent streams and substreams.

L'Ecuyer, P., Simard, R., Chen, E. J., Kelton, W. D. An Object-Oriented Random-Number Package with Many Long Streams and Substreams. (2002). Operations Research, 50(6), 1073-1075.  

To decide if common randon numbers are appropriate to a particular problem, see the following reference.  

Law AM (2015) Simulation Modeling and Analysis (New York: McGraw Hill Education), 5th edition.  

To be compatible with common random numbers, users can simply use the generator. See the below code listing for a simple example problem which is compatible with PyMOSO common random numbers. If `g` is a wrapper to an external simulation, users can still remain compatible with common random numbers  by generating the random numbers using `rng` and passing them to the simulation or by using `rng.get_seed()` and sending the seed to the generator used by the simulation. It is up to the user to ensure the seed obtained from `rng.get_seed()`, an `mrg32k3a` seed, is compatible with their simulation's generator.

To ensure independent sampling of observations, PyMOSO "jumps" the stream after every observation by a fixed amount of `pow(2, 76)`. Thus, we require that every simulation observation use fewer than `pow(2, 76)` random numbers for users needing independent replications. We ensure independence among parallel replications by "giving" each processor an `rng` each of which are `pow(2, 127)` randomn numbers apart. When using the included algorithms, each retrospective iteration begins with a new independent stream `pow(2, 127)` from the beginning of the previous stream, where PyMOSO sets the previous stream to account for any parallel streams used within a retrospective iteration. thus, in a given retrospective iteration, a user may simulate 100 million points at a sample size of 1 million, without common random numbers, and easily not reach the limit.  For researchers using `testsolve`, the observations cannot be taken in parallel, but independent algorithm instances can be. To ensure the instances remain independent, researchers should set the budget such that the included algorithms do not surpass 200 retrospective iterations. For reference, on default settings, the sample size at every point in the 200th iteration is almost 380 million.

#### Simple example problem
```python
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
Once implemented, the problem can be solved with, say, R-PERLE using the following command. For your problem, choose an appropriate starting point and algorithm.  
`pymoso solve myproblem.py RPERLE 97`  

Researchers will want to incorporate the `MyProblem` into a `MyTester`. Testers allow researchers to compare algorithm performance using a known solution, a function to generate the true objective values at every feasible point, and a function to compute a metric from a generated solution to the known solution. For the included algorithms, the metric will be recorded on the solution generated every algorithm iteration.

### Implementing a Tester in PyMOSO
```python
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

# define a solution as appropriate for the metric
soln = {(0, 4), (4, 0), (1, 1)}


class MyTester(object):
    '''Example tester implementation for MyProblem.'''
    def __init__(self):
        self.ranorc = MyProblem
        self.soln = soln
        self.true_g = true_g
        self.get_ranx0 = get_ranx0

    def metric(self, eles):
        '''Metric to be computed per retrospective iteration.'''
        efrontier = []
        for point in eles:
            objs = self.true_g(point)s
            efrontier.append(objs)
        haus = dh(efrontier, self.soln)
        return haus
```
To test a problem using the `testsolve` command, implement a `Tester` object as above. The only strict pymoso requirement is that a tester is a class with a member called `ranorc` which is an Oracle class. To generate useful test metrics, programmers may find it convenient to include a solution and a function which can generate the expected values of the objectives of the oracle.  Once implemented, test an algorithm against `MyProblem` as follows.   
`pymoso testsolve mytester.py RPERLE 97`   

Implement a `MyTester.get_ranx0(rng)` method if you want a tester that can generate random starting points. For example, using `MyProblem` feasible space.
```python
def get_ranx0(self, rng):
    val = rng.choice(range(-100, 101))
    x0 = (val, )
    return x0
```
Then, testsolve can run multiple independent sample paths of an algorithm using different starting points, and no `x0` needs to be specified. The following command will run 16 independent sample paths using 4 processes, where each sample path has a random starting points, and save the .  

`pymoso testsolve --isp=16 --proc=4 --metric mytester.py RPERLE`

The command creates a results file for each independent sample path. The file contains the solutions generated at every algorithm iteration, such that the solution of iteration 2 is on line 2, iteration 10 on line 10, and so forth. If `--metric` is specified, PyMOSO generates a second file for each independent sample path containing a set of triples (iteration number, simulations used at end of iteration, metric output), one for each algorithm iteration.  

### Implementing algorithms in PyMOSO
Users can leverage internal PyMOSO structures to implement new algorithms. It is particularly easy to implement retrospective approximation algorithms (see below reference) requiring users to implement only the sample path solver.

Pasupathy R, Ghosh S (2013) Simulation optimization: a concise overview and implementation guide. Topaloglu H, ed., TutORials in Operations Research, chapter 7, 122–150 (Catonsville, MD: INFORMS), URL http://dx.doi.org/10.1287/educ.2013.0118.

#### Example MOSO algorithm in PyMOSO that uses RLE to ensure convergence (myaccel.py)
```python
from pymoso.chnbase import RLESolver

# create a subclass of RLESolver
class MyAccel(RLESolver):
    '''Example implementation of an RLE accelerator.'''

    def accel(self, warm_start):
        '''Return a collection of points to send to RLE.'''
        # bring up the sample sizes of the "warm start"
        self.upsample(warm_start)
        return warm_start
```
Programmers can use pymoso to create new algorithms that use RLE for convergence. The novel part of these algorithms, carefully created by MOSO researchers, will be the `accel` function which should efficiently collect points to send to RLE for certification. The function `accel` must have the signature `accel(self, warm_start)` where `warm_start` is a set of tuples. The tuples represent feasible points. PyMOSO allows programmers to easily implement and test these accelerators. These accelerators are to be used in a retrospective approximation framework.  Every retrospective iterations, PyMOSO will first call `accel(self, warm_start)` and send the returned set to `rle(self, warm_start)`. The return value must be a set of tuples, where each tuple is a feasible point. The implementer does not need to implement or call `RLE`, as in the example above.  

Once implmented, solve a problem using the accelerator as follows.  
`pymoso solve myproblem.py myaccel.py 97`  

#### Example of an RA algorithm (myraalg.py)
```python
from pymoso.chnbase import RASolver

# create a subclass of RASolver
class MyRAAlg(RASolver):
    '''Example implementation of an RA algorithm.'''

    def spsolve(self, warm_start):
        '''Compute a solution to the sample path problem.'''
        # bring up the sample sizes of the "warm start"
        self.upsample(warm_start)
        return warm_start
```
More generally, algorithm designers can quickly implement any retrospective approximation algorithm by subclassing `RASolver` and implementing the `spsolve` function as shown. The algorithm can be a single-objective algorithm even though its class is a child of `MOSOSolver`.  This particular algorithm is technically valid in PyMOSO, but it won't solve anything.

`pymoso solve myproblem.py myraalg.py 97`

#### Example of a MOSO algorithm (mymoso.py)
```python
from pymoso.chnbase import MOSOSolver

# create a subclass of MOSOSolver
class MyMOSO(MOSOSolver):
    '''Example implementation of a MOSO algorithm.'''

    def solve(self, budget):
    ```Initialize and solve a simulation optimization problem.'''
      seed1 = self.orc.rng.get_seed()
      self.endseed = seed1
      itersoln = dict()
      simcalls = dict()
      itersoln[0] = set() | {self.x0}
      simcalls[0] = 0
      # generate solutions (perhaps in iterations) and save them to itersoln
      # save the corresponding cumulative number of simulations to simcalls
      # generate a seed that a user can input to PyMOSO to start the next independent run
      resdict = {'itersoln': itersoln, 'simcalls': simcalls, 'endseed': self.endseed}
      return resdict
```

PyMOSO can accommodate any simulation optimization algorithm by implementing the `solve` function of a `MOSOSolver` class as shown. It does not have to be a multi-objective algorithm.  PyMOSO will require users to send an initial feasible point `x0` whether or not the algorithm needs it. It is accessed through `self.x0` which is a tuple. The return value must be a Python dictionary with the keys 'itersoln', 'simcalls', and 'endseed'. 'itersoln' itself is a dictionary with a key for every iteration (or a number indicating some ordered, intermediate step of the algorithm). Similarly, `simcalls` is itself a dictionary of iteration number by cumulative number of simulations at the end of the corresponding iteration. `endseed` is a tuple of length 6 representing a new indpendent `rng` seed users can pass into the next PyMOSO invocation.

#### PyMOSO internals
The base class `MOSOSolver` implements basic members required to solve MOSO problems. To implement a general (i.e. non-RA) MOSO algorithm in pymoso, one must subclass `MOSOSolver` and implement the `MOSOSolver.solve` function with signature `solve(self, budget)` and it must return a set, even if the set contains a single point. `RASolver` is a subclass of `MOSOSolver` which provides the machinery needed to quickly implement a retrospective approximation algorithm. To implement an RA algorithm, one must subclass `RASolver` and implement its `spsolve` method with signature `spsolve(self, warm_start)` which returns a set of points.`RLESolver`, subclass of `RASolver`, allows quick implementation of MOSO solvers that use `RLE` to ensure convergence, as shown in the example accelerator above. One only needs to implement the `accel` method of `RLESolver`. Oracles are the problems that PyMOSO can solve. Here, we provide a listing of the important objects available to pymoso programmers who are implementing MOSO algorithms.

##### Table of PyMOSO internals
| PyMOSO internal object | Example | Description |
| ------------- | ------- | ----------- |
|`pymoso.prng.mrg32k3a.MRG32k3a`| `rng = MRG32k3a()` | Subclass of `random.Random()` for generating random numbers. |
|`pymoso.prng.mrg32k3a.get_next_prnstream`| `prn = get_next_prnstream(seed)` | Returns a stream 2^127 places from the given `seed` |
|`pymoso.chnbase.Oracle`| `orc = Oracle(rng)` | Implements the `Oracle` class. |
|`pymoso.chnbase.MOSOSolver` | `ms = MOSOSolver(orc)` | Implements the `MOSOSolver` class. |
|`pymoso.chnbase.RASolver` | `ras = RASolver(orc)` | Implements the `RASolver` class. |
|`pymoso.chnbase.RLESolver` | `res = RLESolver(orc)`| Implements the `RLESolver` class. |
|`pymoso.chnutils.solve` | `soln = solve(prob, alg, x0)` | The solve command used in the examples. |
|`pymoso.chnutils.testsolve` | `solns = testsolve(tester, alg, x0)`| The testsolve command used in the examples. |
|`pymoso.chnutils` | Not applicable. | The module contains a number of functions useful in algorithm implementation. See the next table. |
| `Oracle.hit` | `isfeas, gx, se = Oracle.hit(x, 4)` | Call the simulation 4 times and compute the mean value and standard error of each objective at `x`. For RA algorithms, don't call this directly but use `RASolver.estimate`. |
| `Oracle.set_crnflag` | `Oracle.set_crnflag(False)` | Turn common random numbers on or off. Default is true (on). |
| `Oracle.crn_advance` | `Oracle.crn_advance()` | Wind the rng forward. pymoso handles this automatically for RA algorithms. |
| `Oracle.rng` | `r = Oracle.rng.random()` | A random.Random() object used in `hit`. Usually don't use `rng` directly in algorithms. |
| `Oracle.num_obj` | `no = Oracle.num_obj` | The number of objectives. |
| `Oracle.dim` | `dim = Oracle.dim` | The cardinality of the feasible points. |
| `MOSOSolver.orc` | `MOSOSolver.orc.hit(x, 4)` | The simulation oracle object being solved. |
| `MOSOSolver.num_calls` | `nc = MOSOSolver.num_calls` | The current number of simulations used. |
| `MOSOSOlver.num_obj` | `no = MOSOSolver.num_obj` | Should match `MOSOSolver.orc.num_obj` |
| `MOSOSolver.dim` | `dim = MOSOSolver.dim` | Should match `MOSOSolver.orc.dim` |
| `RASolver.gbar`   | `objs = self.gbar[x]` | A dictionary of the estimated values for visited points in the current retrospective iteration. |
| `RASolver.sehat` | `seobjs = self.sehat[x]`| A dictionary of the estimated standard errors for visited points in the current retrospective iteration. |
| `RASolver.nbor_rad` | `radius = RASolver.nbor_rad` | The radius defining which points are considered neighbors. |
| `RASolver.sprn` | `RASolver.sprn.random()` | The random generator used by the solver. |
| `RASolver.x0` | `x0 = RASolver.x0` | The initial feasible point. |
| `RASolver.estimate` | `isfeas, gx, se = RASolver.estimate(x, 4, const, obj)` | Performs simulations and updates `gbar` and `sehat`. `const` and `obj` are optional. If provided, `isfeas` will only be `True` when `gx[obj] < const`. |
|`RASolver.upsample`| `RASolver.upsample(mcS)` | Sample a set of points at the current iteration's sample size. |
|`RASolver.calc_m` | `m = RASolver.calc_m(nu)` | Compute the sample size for iteration `nu`. Overwrite this function if desired. |
|`RASolver.calc_b` | `b = RASolver.calc_b(nu)` | Compute the searching sample limit for iteration `nu`. Overwrite this function if desired. |
|`RASolver.spline` | `T, xmin, gxmin, sexmin = RASolver.spline(x, const, objmin, objcon)` | Find a sample path local minimizer such that `gxmin[objmin]` is a local min and `gxmin[objcon] < const`. |
|`RLESolver.betadel` | `bd = RLESolver.betadel` | The relaxation parameter used by `RLE`. |
|`RLESolver.calc_delta` | `d = RLESolver.calc_delta(nu)` | Compute the relaxation for iteration `nu`. |

##### Table of chnutils functions
| chnutils function | Example | Description |
| ------------- | ------- | ----------- |
|`does_weak_dominate` | `dwd = does_weak_dominate(g1, g2, rel1, rel2)` | Returns true if `g1[i] - rel1[i] <= g2[i] + rel2[i]` for every `i`.
|`does_dominate` | `dd = does_dominate(g1, g2, rel1, rel2)` | Returns true if `g1[i] - rel1[i] <= g2[i] + rel2[i]` for every `i` and `g1[i] - rel1[i] < g2[i] + rel2[i]` for at least one `i`. |
|`does_strict_dominate` | `dsd = does_strict_dominate(g1, g2, rel1, rel2)` | Returns true if `g1[i] - rel1[i] < g2[i] + rel2[i]` for every `i`. |
|`get_biparetos` | `pars = get_biparetos(mcS)` | `mcS` is a dictionary where each key is a tuple and each value is a tuple of length 2. Returns the set of keys with non-dominated values. |
|`get_nondom` | `nd = get_nondom(mcS)` | Like `get_biparetos` but the values are tuples of any length. |
|`get_nbors` | `nbors = get_nbors(x, r)` | Return the set of points no farther than `r` from `x` and exclude `x`. |
|`get_setnbors` | `nbors = get_setnbors(S, r)` | Excluding points in the set `S`, return `get_nbors(s, r)` for every `s` in `S`. |

#### Useful snippets for implementing RA algorithms
These snippets will work within the `spsolve` and/or the `accel` functions in the `myaccel.py` and `myraalg.py` examples above.
##### Sample a point
```python
from pymoso.chnutils import get_nbors
# pretend x has not yet been visited in this RA iteration and is feasible
x = (1, 1, 1)

# self.m is the sample size of the current RA iteration
m = self.m
# self.num_calls is the cumulative number of simulations used till now
start_num_calls = self.num_calls
# use estimate to sample x and put results in self.gbar and self.sehat
isfeas, fx, se = self.estimate(x)
calls_used = self.num_calls - start_num_calls
print(m == calls_used) # True
print(fx == self.gbar[x]) # True
print(se == self.sehat[x]) # True

# estimate will not simulate again in subsequent visits to a point
start_num_calls = self.num_calls
isfeas, fx, se = self.estimate(x)
calls_used = self.num_calls - start_num_calls
print(calls_used == 0) # True
```
##### Sample the point's neighbors
```python
# neighborhood radiuss
r = self.nbor_rad
nbors = get_nbors(x0, r)
self.upsample(nbors)
for n in nbors:
  print(n in self.gbar) # True if n feasible else False

# upsample also returns the feasible subset
nbors = self.upsample(nbors)
```
##### argsort the points by 1st objective
```python
# 0 index for first objective
sorted_feas = sorted(nbors | {x}, key=lambda t: self.gbar[t][0])
```
##### choose the minimizer and its objectives
```python
xmin = sorted_feas[0]
fxmin = self.gbar[x]
```
##### Use SPLINE to get a local minimizer
```python
# no constraints and minimize the 2nd objective
x0 = (2, 2, 2)
isfeas, fx, sex = self.estimate(x0)
# the suppressed value is the set visited along SPLINE's trajectory
_, xmin, fxmin, sexmin = self.spline(x0, float('inf'), 1, 0)
print(self.gbar[xmin] == fxmin) # True
```
##### Get the non-dominated subset of every visited point
```python
from chnutils import get_nondom
nondom = get_nondom(self.gbar)
```
##### Randomly choose points from the subset
```python
solver_rng = self.sprn
# pick 5 points -- returns a list, not a set.
ran_pts = solver_rng.sample(list(nondom), 5)
one_in_five = solver_rng.choice(ran_pts)
```

## Using PyMOSO in Python programs
### Solve example
```python
# import the solve function
from pymoso.chnutils import solve
# import the module containing the RPERLE implementation
import pymoso.solvers.rperle as rp
# import MyProblem - myproblem.py should usually be in the script directory
import myproblem as mp

# specify an x0. In MyProblem, it is a tuple of length 1
x0 = (97,)
soln = solve(mp.MyProblem, rp.RPERLE, x0)
print(soln)
```

The `solve` function can take keyword arguments. The keyword values correspond to options in the command line help.
Here is a listing:  `budget`, `simpar`, `seed`. Algorithm-specific parameters can also be passed as keyword arguments. `soln` is a set of tuples representing points.

### TestSolve example
```python
# import the testsolve functions
from pymoso.chnutils import testsolve
# import the module containing RPERLE
import pymoso.solvers.rperle as rp
# import the MyTester class
from mytester import MyTester

# choose a feasible starting point of MyProblem
x0 = (97,)
run_data = testsolve(MyTester, rp.RPERLE, x0, isp=20, proc=4)
```

The `testsolve` function can take keyword arguments. The keyword values correspond to options in the command line help.
Here is a listing: `budget`, `seed`, `isp`, `proc`. `run_data` is a dictionary with `range(isp)` as the keys. The value of each key is also a dictionary, with keys of `itersoln`, `simcalls`, and `endseed`. `itersoln` is itself a dictionary containing the list of solutions generated by the algorithm as it progresses. It's keys are iteration numbers. To compute the metric from, say, the solution at iteration 5 to the known solution of the 12th independent sample path, add code as follows.

```python
iter5_soln = run_data[12]['itersoln'][5]
isp12_iter5_metric = MyTester.metric(iter5_soln)
```
