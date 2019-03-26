# PyMOSO

PyMOSO is software for solving multi-objective simulation optimization (MOSO) problems and for creating, comparing, and testing MOSO algorithms.

## Reference

If you use PyMOSO in work leading to publication, please cite the paper which introduces PyMOSO.

Cooper, K., Hunter, S. R. 2018. PyMOSO: Software for Multi-Objective Simulation Optimization with R-PERLE and R-MinRLE. Optimization Online, http://www.optimization-online.org/DB_HTML/2018/10/6876.html.

## Additional Reading
The initial release of PyMOSO contains solvers that implement four total algorithms, in alphabetical order: R-MinRLE, R-PE, R-PERLE, and R-SPLINE.  The algorithms R-MinRLE, R-PE, R-PERLE were introduced in the following paper:

Cooper, K., Hunter, S. R., and Nagaraj, K. 2018. Bi-objective simulation optimization on integer lattices using the epsilon-constraint method in a retrospective approximation framework. Optimization Online, http://www.optimization-online.org/DB_HTML/2018/06/6649.html.

The algorithm R-SPLINE was introduced in the following paper:

Wang, H., Pasupathy, R., and Schmeiser, B. W. 2013. Integer-ordered simulation optimization using R-SPLINE: Retrospective Search with Piecewise-Linear Interpolation and Neighborhood Enumeration. ACM Transactions on Modeling and Computer Simulation, Vol. 23, No. 3, Article 17 (July 2013), 24 pages.  http://dx.doi.org/10.1145/2499913.2499916

We recommend reading these papers to understand the algorithms, what they return, and the algorithm parameter options that we describe in the user manual.

Table of Contents
=================

   * [PyMOSO](#pymoso)
      * [Reference](#reference)
      * [Additional Reading](#additional-reading)
      * [Installation](#installation)
         * [Install PyMOSO from the Python Packaging Index using pip](#install-pymoso-from-the-python-packaging-index-using-pip)
         * [Install PyMOSO from the repository using pip](#install-pymoso-from-the-repository-using-pip)
         * [Install PyMOSO from Source Code](#install-pymoso-from-source-code)
      * [Command Line Interface (CLI)](#command-line-interface-cli)
         * [CLI help](#cli-help)
         * [The listitems command for viewing solvers, testers, and oracles included in PyMOSO](#the-listitems-command-for-viewing-solvers-testers-and-oracles-included-in-pymoso)
         * [The solve command](#the-solve-command)
            * [The Example Oracle](#the-example-oracle)
            * [Table of Algorithm-Specific Parameters](#table-of-algorithm-specific-parameters)
         * [The testsolve Command](#the-testsolve-command)
            * [The Example Tester](#the-example-tester)
      * [Implementing problems, testers, and algorithms in PyMOSO](#implementing-problems-testers-and-algorithms-in-pymoso)
         * [Implementing PyMOSO Oracles](#implementing-pymoso-oracles)
            * [Example Oracle that Wraps a C Simulation](#example-oracle-that-wraps-a-c-simulation)
            * [Example Wrapper with PyMOSO Random Numbers](#example-wrapper-with-pymoso-random-numbers)
         * [Implementing PyMOSO Testers](#implementing-pymoso-testers)
            * [Example Metric 1](#example-metric-1)
            * [Example Metric 2](#example-metric-2)
         * [Implementing PyMOSO Algorithms](#implementing-pymoso-algorithms)
            * [Template Accelerator](#template-accelerator)
            * [Template RA Solver](#template-ra-solver)
            * [Template MOSO Solver](#template-moso-solver)
               * [Take Simulation Replications at a Point](#take-simulation-replications-at-a-point)
               * [Find Neighbors and Take Simulation Replications](#find-neighbors-and-take-simulation-replications)
               * [Argsort a Dictionary of Points](#argsort-a-dictionary-of-points)
               * [Select the Minimizer and its Value](#select-the-minimizer-and-its-value)
               * [Use SPLINE to Retrive a Local Minimizer](#use-spline-to-retrive-a-local-minimizer)
               * [Find the Non-Dominated Points in a Dictionary](#find-the-non-dominated-points-in-a-dictionary)
               * [Randomly Select Points in a Set](#randomly-select-points-in-a-set)
         * [Using solve and <code>testsolve</code> in Python Programs](#using-solve-and-testsolve-in-python-programs)
            * [Minimal solve Example](#minimal-solve-example)
            * [Some solve Examples with Options](#some-solve-examples-with-options)
            * [A testsolve Example](#a-testsolve-example)
            * [Computing a Metric on testsolve Output](#computing-a-metric-on-testsolve-output)
      * [PyMOSO Object Reference](#pymoso-object-reference)
         * [The pymoso.prng.mrg32k3a Module](#the-pymosoprngmrg32k3a-module)
         * [The pymoso.chnbase Module](#the-pymosochnbase-module)
         * [The pymoso.chnutils Module](#the-pymosochnutils-module)
         * [The Oracle Class](#the-oracle-class)
         * [The MOSOSolver Class](#the-mososolver-class)
         * [The RASolver Class](#the-rasolver-class)
         * [The RLESolver Class](#the-rlesolver-class)

## Installation
Since PyMOSO is programmed in Python, every PyMOSO user must first install Python, which can be downloaded from https://www.python.org/downloads/. PyMOSO is compatible with Python versions 3.6 and higher. In the remainder of this section, we assume an appropriate Python version is installed. We discuss three different methods to install PyMOSO: first, from the Python Packaging Index; second, directly from our source code using git; and third, manually installing PyMOSO from our source code.

### Install PyMOSO from the Python Packaging Index using `pip`
For ease of distribution, we keep stable, recent releases of PyMOSO on the Python Packaging Index (PyPI). Since the program `pip` is included in Python versions 3.6 and higher, we recommend using `pip` to install PyMOSO. To do so, open a terminal, type the following command, and press enter.  

`pip install pymoso`  

Depending on how users configure their Python installation and how many version of Python they install, they may need to replace `pip` with `pip3`, or other variants of `pip`.  

### Install PyMOSO from the repository using `pip`
Users with `git` installed can use `pip` to install the most current version of PyMOSO directly from our source code:  

`pip install git+https://github.com/pymoso/PyMOSO.git`  

We consider the latest source to be less stable than the fixed releases we upload to PyPI, and thus we recommend most users install PyMOSO from PyPI.  

### Install PyMOSO from Source Code
Users may follow the steps below to manually install PyMOSO from any version of the source code.  
1. Acquire the PyMOSO source code, for example, by downloading it from the repository https://github.com/HunterResearch/PyMOSO.
1. Install the `wheel` package, e.g. using the `pip install wheel` command.
1. Open a terminal and navigate into the main project directory which contains the file `setup.py`.
1. Build the installable PyMOSO package, called a wheel, using the command `python setup.py bdist_wheel`. As with `pip`, some users may need to replace `python` with `python3` or something similar. The command should create a directory named `dist` containing the PyMOSO wheel.
1. Install the PyMOSO wheel using pip install `dist/pymoso-x.x.x-py3-none-any.whl`, where users replace `x.x.x` with the appropriate PyMOSO version.


## Command Line Interface (CLI)
PyMOSO users solving MOSO problems and testing MOSO algorithms may do so using the command line interface. First, we show how to access the included help file. Then, we show how to view the lists of solvers, testers, and oracles installed by default with PyMOSO. Finally, we discuss the `solve` and `testsolve` commands.

### CLI help
PyMOSO includes a command line help file. The help file shows syntax templates for every PyMOSO command, the available options, and a selection of example invocations. The `pymoso --help` invocation prints the file to the terminal. The file is also printed when PyMOSO cannot parse an invocation that begins with `pymoso`. We show the current help file below.  

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
```
For now, PyMOSO has three commands: `listitems`, `solve`, and `testsolve`, which we explain below.
### The `listitems` command for viewing solvers, testers, and oracles included in PyMOSO
The default installation of PyMOSO includes a selection of solvers, testers, and oracles. Users can view the complete lists of included solvers, testers, and oracles using the `pymoso listitems` command. We show the current listing below. Test problems A, B, and C refer to those in Cooper et al (2018).

```
Solver                         Description
************************       ************************
RMINRLE                        A solver using R-MinRLE for integer-ordered MOSO.
RPE                            A solver using R-Pe for integer-ordered bi-objective MOSO.
RPERLE                         A solver using RPERLE for integer-ordered bi-objective MOSO.
RSPLINE                        A solver using R-SPLINE for single objective SO.

Problems                       Description                    Test Name (if available)
************************       ************************       ************************
ProbSimpleSO                   x^2 + noise.                   SimpleSOTester
ProbTPA                        Test Problem A                 TPATester
ProbTPB                        Test Problem B                 TPBTester
ProbTPC                        Test Problem C                 TPCTester
```

### The `solve` command
The PyMOSO `solve` command is for solving MOSO problems. Users can solve the built-in problems (use the `listitems` command to view the built-in problems), however, PyMOSO `solve` users typically will have their own MOSO problem they wish to solve. Thus, we assume users have implemented a PyMOSO oracle named `MyProblem` in `myproblem.py`.  In the examples that follow, we assume the `MyProblem` implementation below, which is a bi-objective oracle with one-dimensional feasible points. See [Implementing PyMOSO Oracles](#implementing-pymoso-oracles) for instructions on implementing a MOSO problem as a PyMOSO oracle.  

#### The Example Oracle
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

The template `solve` command is `pymoso solve oracle solver x0`, where `oracle` is a built-in or user-defined oracle, `solver` is a built-in or user-defined algorithm, and `x0` is a feasible starting point for the solver, with a space between each component. As a first example, we solve the user-defined `MyProblem` using the built-in R-PERLE starting at the feasible point 97.  


`pymoso solve myproblem.py RPERLE 97`  

Similarly, we can solve built-in problems, such as `ProbTPA` which has two-dimensional feasible points.  

`pymoso solve ProbTPA RPERLE 40 40`  

Henceforth, we present `solve` examples only for solving `MyProblem`.  Since `MyProblem` is bi-objective, we recommend using the `R-PERLE` solver. However, for two or more objectives, PyMOSO implements `R-MinRLE`.  

`pymoso solve myproblem.py RMINRLE 97`  

For a single objective problem, PyMOSO implements `R-SPLINE`. We remark that if given a multi-objective problem, `R-SPLINE` will simply minimize the first objective. We do not necessarily prohibit such use, but urge that users take care when using R-SPLINE to minimize one objective of a many-objective problem.  

`pymoso solve myproblem.py RSPLNE 97`  

Regardless of the chosen solver, PyMOSO creates a new sub-directory of the working directory containing output. There will be a metadata file, indicating the date, time, solver, problem, and any other specified options. In addition, PyMOSO creates a file containing the solver-generated solution. PyMOSO provides additional options for users solving MOSO problems. We present examples of each option below. First, users can specify the name of the output directory.  

`pymoso solve --odir=OutDirectory myproblem.py RPERLE 45`  

Users can specify the simulation budget, which is currently set to a default of 200.  

`pymoso solve --budget=100000 myproblem.py RPERLE 12`  

Users may specify to take simulation replications in parallel. We only recommend doing so if the user has thought through appropriate pseudo-random number stream control issues (see [Implementing PyMOSO Oracles](#implementing-pymoso-oracles)). Furthermore, due to the overhead of parallelization, we only recommend using the parallel simulation replications feature if observations are sufficiently "expensive" to compute, e.g. the simulation takes a half second or more to generate a single observation. We remark that the run-time complexity of the simulation oracle may not perfectly indicate when it is appropriate to use parallelization; other factors include, e.g., the total simulation budget.  

`pymoso solve --simpar=4 myproblem.py RPERLE 44`  

Currently, all PyMOSO solvers support using common random numbers. Users may enable the functionality using the `--crn` option.  

`pymoso solve --crn myproblem.py RMINRLE 62`  

We do not recommend this option unless the oracle is implemented to be compatible, that is, the oracle uses PyMOSO's pseudo-random number generator to generate pseudo-random numbers or to provide a seed to an external `mrg32k3a` generator (see [Implementing PyMOSO Oracles](#implementing-pymoso-oracles)).   

Users may specify an initial seed to PyMOSO's `mrg32k3a` pseudo-random number generator. Seeds must be 6 positive integers with spaces. The default is 12345 for each of the 6 components.  

`pymoso solve --seed 1111 2222 3333 4444 5555 6666 myproblem.py RPERLE 23`  

Users may specify algorithm-specific parameters (see the papers in which the algorithms were introduced for detailed explanations of the parameters.) All parameters are specified in the form `--param name value`. For example, the RLE relaxation parameter can be specified and set as `betadel` to a real number. We refer the reader to [the table](#table-of-algorithm-specific-parameters) for the full list of currently available algorithm-specific parameters.  

`pymoso solve --param betadel 0.2 myproblem.py RPERLE 34`  

Finally, users may specify any number of options in one invocation. However, all options must be specified in after the `solve` command and before the `myproblem.py` argument. Furthermore, any `--param` options must be the last options. (Note that the `\` at the end of the first line continues the command to the second line.)

`pymoso solve --crn --simpar=4 --budget=10000 --seed 1 2 3 4 5 6 \`  
`     --odir=Exp1 --param mconst 4 --param betadel 0.7 myproblem.py RPERLE 97`  


#### Table of Algorithm-Specific Parameters  

| Parameter Name | Default Value | Affected Solvers | Description |
| -------------- | ------------- |  --------------  | ----------- |
| `mconst`       |    2          |`RPERLE`, `RMINRLE`, `RPE`, `RSPLINE` | Initialize the sample size and subsequent schedule of sample sizes.|  
| `bconst`       |    8          |`RPERLE`, `RMINRLE`, `RPE`, `RSPLINE` | Initialize the search sampling limit and subsequent schedule of limits. |  
| `radius`       |   1           |`RPERLE`, `RMINRLE`, `RPE`, `RSPLINE` | Sets radius that determines a point's neighborhood. |  
| `betadel` | `0.5` | `RPERLE`, `RMINRLE` | Roughly, affects how likely it is for RLE to keep its given solution. |  
| `betaeps` | `0.5` | `RPERLE`, `RPE` | Roughly, affects how likely PE will perform a search from a point. |   


### The `testsolve` Command  
The PyMOSO `testsolve` command tests algorithms on problems using a PyMOSO tester. Users can test built-in or user-defined solvers with built-in or user-defined testers. In the examples that follow, we assume users have implemented `MyProblem` as in [The Example Oracle](#the-example-oracle) and the corresponding tester named `MyTester` in `mytester.py`, shown in [The Example Tester](#the-example-tester). See [Implementing PyMOSO Testers](#implementing-pymoso-testers) for instructions on implementing a user-defined tester, including a metric for comparing algorithms, in PyMOSO.  

#### The Example Tester
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
```

The template `testsolve` command is `pymoso testsolve tester solver` where `tester` is a built-in or user-defined tester, and `solver` is a built-in or user-defined solver. Users may also specify an `x0`, as in the `solve` command, if the `tester` does not implement the function to generate feasible points. As a first example, we test `RPERLE` on `MyProblem` using `MyTester`. Since some options are compatible with both `solve` and `testsolve`, we include those options in this example.  

`pymoso testsolve --budget=999 --odir=exp1 \`  
`    --crn --seed 1 2 3 4 5 6 mytester.py RPERLE`  

Users may want to compute some metric on the algorithm-generated solutions. If a metric is defined as part of the tester, such as in `MyTester`, the `testsolve` command can compute the metric on every algorithm iteration using the `--metric` option.  

`pymoso testsolve  --metric  mytester.py RPERLE`  

The `testsolve` command cannot perform simulation replications in parallel. However, testers can apply the solvers to independent sample paths of the problems. For example, to test `RPERLE` on 100 independent sample paths of `MyProblem`, compute the metrics for each sample path, and use common random numbers in each sample path, use the following command.  

`pymoso testsolve --crn --metric --isp=100 mytester.py RPERLE`  

PyMOSO can perform independent algorithm runs in parallel. Use the `--proc` option to specify the number of processes available to PyMOSO.  

`pymoso testsolve --crn --metric --isp=100 --proc=20 mytester.py RPERLE`  

We remark here that, to ensure the algorithm runs remain independent using PyMOSO's pseudo-random number generator (see [Implementing PyMOSO Oracles](#implementing-pymoso-oracles)), researchers should set the total simulation budget so that the included algorithms do not surpass 200 retrospective approximation (RA) iterations. For reference, using the default settings, the sample size at every point in the 200th RA iteration is almost 380 million.  

The `testsolve` command creates a results file for each independent sample path. The file contains the solutions generated at every algorithm iteration, such that the solution of iteration 2 is on line 2, iteration 10 on line 10, and so forth. If `--metric` is specified, PyMOSO generates a second file for each independent sample path containing the collection of triples (iteration number, simulations used at end of iteration, metric).  

## Implementing problems, testers, and algorithms in PyMOSO
To use PyMOSO, users solving MOSO problems must implement a PyMOSO oracle, and users testing MOSO algorithms should implement, at least, a PyMOSO oracle and tester. In this section, we provide template Python code to help users quickly implement oracles, testers, and perhaps solvers in PyMOSO.

### Implementing PyMOSO Oracles
Usually, implementing a PyMOSO oracle implies implementing a Monte Carlo simulation oracle as a black box function while following the PyMOSO rules put forth in this section. For reference, we discuss the example PyMOSO oracle `MyProblem` in [The Example Oracle](#the-example-oracle). Users may copy the code in [The Example Oracle](#the-example-oracle) and re-implement the function `g` as needed. We now list the basic requirements of every `g` implementation.  

1. The function `g` must be an instance method of an `Oracle` sub-class, and thus take `self` as its first parameter.
1. The function `g` must take an arbitrarily-named second parameter which is a tuple of length `self.dim` and represents a point. Stylistically, PyMOSO consistently names this parameter `x`.
1. The function `g` must take an arbitrarily-named third parameter which is a modified Python `random.Random` object. Stylistically, PyMOSO consistently names this parameter `rng`.
1. The function `g` must return a boolean first and a tuple of length `self.num_obj` second.
   - The boolean is `True` if `x` is feasible, and `False` otherwise.
   - If `x` is feasible, the tuple contains a single observation of every objective. If `x` is not feasible, each element in the tuple is `None`.

If users already have an implemented simulation oracle, they may find it convenient to implement `g` as wrapper which calls that simulation from Python. As an example, suppose a user has implemented a simulation in C which is compiled to a C library called `mysim.so` and placed in the working directory. Suppose further that the simulation function takes the following as parameters: an array of integers representing a point and an unsigned integer representing the number of observations to take at `x`. The function output is defined as `struct Simout` with members `feas` set to 0 or 1, `obj` a double array set to the mean of the observed objective values, and `var` a double array set to the sample variance of the observed objective values. Then users can modify the template to wrap the C function `struct Simout c_func(int x, int n)` as in [the example](#example-oracle-that-wraps-a-c-simulation).  

#### Example Oracle that Wraps a C Simulation
```python
from ctypes import CDLL, c_double, c_uint, c_int, Structure
import os.path
libname = 'mysim.so'
libabspath = os.path.dirname(os.path.abspath(__file__)) + os.path.sep + dll_name
libobj = CDLL(libabspath)

class Simout(Structure):
    _fields_ = [("feas", c_int), ("obj", c_double*2), ("var", c_double*2)]
csimout = libobj.c_func
csimout.restype = Simout

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
        is_feasible = True
        objective_values = (None, None)
        # g takes only one observation so set the c_func parameter to 1
        c_n = c_uint(1)
        # c_func requires is an integer so convert it -- this is a 1D example
        c_x = c_int(x[0])
        # call the C function
        mysimout = csimout(c_x, c_n)
        if not mysimout.feas:
            is_feasible = False
        else:
            is_feasible = True
        if is_feasible:
            objective_values = tuple(mysimout.obj)
        return is_feasible, objective_values
```


[The C wrapper example](#example-oracle-that-wraps-a-c-simulation) is a valid PyMOSO oracle which wraps a C function. However, PyMOSO algorithms cannot enable common random numbers on this oracle. Furthermore, PyMOSO cannot guarantee that observations are independent when taken in parallel. To enable these properties, the external simulation must use `mrg32k3a` as the generator and must accept a user-specified seed.  

Suppose the library `mysim.so` also implements the function `set_simseed` which accepts a long array representing an `mrg32k3a` seed. We modify the [wrapper](#example-oracle-that-wraps-a-c-simulation) for compatibility with common random numbers and to guarantee independence of parallel observations.  [The new wrapper](#example-wrapper-with-pymoso-random-numbers) demonstrates using `rng.get_seed()` to return the current `mrg32k3a` seed.

#### Example Wrapper with PyMOSO Random Numbers
```python
from ctypes import CDLL, c_double, c_uint, c_int, Structure, c_long
import os.path
libname = 'mysim.so'
libabspath = os.path.dirname(os.path.abspath(__file__)) + os.path.sep + dll_name
libobj = CDLL(libabspath)

class Simout(Structure):
    _fields_ = [("feas", c_int), ("obj", c_double*2), ("var", c_double*2)]
csimout = libobj.c_func
csetseed = libobj.set_simseed
csimout.restype = Simout

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
        is_feasible = True
        objective_values = (None, None)
        # get the PyMOSO seed from rng
        seed = rng.get_seed()
        # convert the seed to c_long array
        c_longarr = c_long*6
        c_seed = c_longarr(seed[0], seed[1], seed[2], seed[3], seed[4], seed[5])
        # use the library function to set the sim seed
        csetseed(c_seed)
        # g takes only one observation so set the c_func parameter to 1
        c_n = c_uint(1)
        # c_func requires is an integer so convert it -- this is a 1D example
        c_x = c_int(x[0])
        # call the C function
        mysimout = csimout(c_x, c_n)
        if not mysimout.feas:
            is_feasible = False
        else:
            is_feasible = True
        if is_feasible:
            objective_values = tuple(mysimout.obj)
        return is_feasible, objective_values
```

Alternatively, if the number of required pseudo-random numbers is known, users can use `rng.random()` to generate pseudo-random numbers and then pass them to an external simulation if such functionality is supported.

The `rng` object is implemented as a sub-class of Python's `random.Random` class, thus the official Python documentation for `random` applies to `rng` and is found at https://docs.python.org/3/library/random.html. In addition to `rng` using `mrg32k3a` as its generator, we also implement `rng.normalvariate` such that it uses the Beasley-Springer-Moro algorithm (Law 2015, p. 458) to approximate the inverse of the standard normal cumulative distribution function.

When using `rng`, to ensure independent sampling of observations, PyMOSO "jumps" forward in the pseudo-random number stream after obtaining every simulation replication. Each jump is of fixed size 2^76 pseudo-random numbers. Thus, we require that every simulation replication use fewer than 2^76 pseudo-random numbers. We ensure independence among parallel replications by "giving" each processor a stream (an `rng`), each of which is 2^127 pseudo-random numbers apart. When using the current PyMOSO algorithms that rely on RA, each RA iteration begins the next available independent stream 2^127, where PyMOSO accounts for the possibility of parallel computation within an RA iteration. Thus, in a given RA iteration, a user may simulate 100 million points at a sample size of 1 million, without common random numbers, and easily not reach the limit.

### Implementing PyMOSO Testers  
Consider again the [example tester](#the-example-tester). As a minimal valid PyMOSO tester, users may do nothing but assign the `MyTester` member `self.ranorc` to a PyMOSO oracle, such as [`MyProblem`](#the-example-oracle), in Line 27. However, we expect most users to leverage PyMOSO features by implementing metrics and  feasible point generators. The function `get_ranx0` allows the tester to generate feasible points to `MyProblem` and `metric` allows the tester to compute a metric on sets returned by a solver. Researchers may implement any number of additional supporting functions, including members and methods of the tester class. The `true_g` function is an example of such a supporting function, which is used to compute the example metric.  

First, we list the rules for implementing a feasible point generator.
1. The function is arbitrarily named but must be set to the `self.get_ranx0` member of a tester.
1. The function must take a single parameter, an arbitrarily named `random.Random` object we suggest naming `rng`.
1. The function must return a tuple with length corresponding to the `self.dim` member of the `self.ranorc` member of the tester.

Since a researcher's desired metric depends on the algorithm capabilities and problem complexity, PyMOSO allows researchers to implement any metric they choose. We provide three example metrics, but first, we list the implementation rules of the `metric` function.  

1. The \inline{metric} function must be an instance method of a tester, and thus take \inline{self} as its first parameter.
1. The second parameter of \inline{metric} is arbitrarily named and is a Python set of tuples.
1. PyMOSO does not enforce the return value of \inline{metric}, but we recommend a scalar real number.

The metric implemented in the [example tester](#the-example-tester) is the Hausdorff distance from (a) the true image of an estimated solution returned by an algorithm, to (b) the true solution hard-coded as `myanswer`.  

For an example of a different metric, consider a MOSO problem that has more than one local efficient set (LES) and such that each LES contains no members of another LES. Since an algorithm that converges to a LES is may find only one LES, we may define the metric to compute the Hausdorff distance between the true image of the estimated solution and the "closest" true LES, as follows. Let `self.answer` be implemented as a list of sets, and assume a `self.true_g` implementation. Then the [following example](#example-metric-1) implements the described metric.  

#### Example Metric 1
```python
def metric(self, eles):
    # use the distance to the closest set.
    epareto = [self.true_g(point) for point in eles]
    # self.soln is a list of sets
    dist_list = [dh(epareto, les) for les in self.answer]
    return min(dist_list)
```

For single-objective problems with one correct solution `x*`, a simple metric that takes an estimated solution `X` is `|g(X) - g(x*)|`, which we implement in the [second example metric](#example-metric-2) assuming an appropriate implementation of `self.answer` and `self.true_g`.  

#### Example Metric 2
```python
def metric(self, singleton_set):
    # single objective algorithms still return a set
    point, = singleton_set
    # let self.soln be a real number
    dist = abs(self.true_g(point) - self.answer)
    return dist

```

### Implementing PyMOSO Algorithms
Researchers can implement simulation optimization algorithms in the PyMOSO framework. PyMOSO provides support for algorithms in three categories:
1. PyMOSO provides strong support for implementing new MOSO algorithms that rely on RLE in an RA framework.
1. PyMOSO provides strong support for implementing general RA algorithms.
1. PyMOSO provides basic support, such as pseudo-random number control, for implementing other simulation optimization algorithms.
We provide templates of algorithms implemented in each of these three categories, along with example code snippets.

In the first category, programmers can use PyMOSO to create new RA algorithms that use RLE for convergence. The novel part of these algorithms, created by the user, will be the `accel` function which should collect points to send to RLE for certification. Here, we list the rules for `accel`.
1. The `accel` function must be an instance method of an `RLESolver` object, and thus its first parameter must be `self`.
1. The second parameter is arbitrarily named and is a set of tuples. We recommend naming the parameter `warm_start`, as it represents the sample-path solution of the previous RA iteration.
1. The return value must be a set of tuples representing feasible points; we do not recommend any particular name.
In every RA iteration, PyMOSO will first call `accel(self, warm_start)` and send the returned set to `rle(self, candidate_les)`. The return value must be a set of tuples. The implementer does not need to implement or call RLE, as in the [template accelerator](#template-accelerator).

#### Template Accelerator
```python
from pymoso.chnbase import RLESolver

# create a subclass of RLESolver
class MyAccel(RLESolver):
    '''Example implementation of an RLE accelerator.'''

    def accel(self, warm_start):
        '''Return a collection of points to send to RLE.'''
        # implement algorithm logic here and return a set
        return warm_start
```

In the second category, algorithm designers can quickly implement any RA algorithm by sub-classing `RASolver` and implementing the `spsolve` function, as shown in the [RA solver template](#template-ra-solver). The algorithm can be a single-objective algorithm. PyMOSO cannot guarantee the convergence of such algorithms. The template is technically valid in PyMOSO but is probably not effective.  

#### Template RA Solver
```python
from pymoso.chnbase import RASolver

class MyRAAlg(RASolver):
    '''Template implementation of an RA solver.'''

    def spsolve(self, warm_start):
        '''Return the sample path solution.'''
        # implement algorithm logic here and return a set
        return warm_start
```

Though analogous to those of an `RLESolver.accel` method, for completeness, we list the requirements for an `RASolver.spsolve` method.
1. The `spsolve` function must be an instance method of an `RASolver` object, and thus its first parameter must be `self`.
1. The second parameter is arbitrarily named and is a set of tuples. We recommend naming the parameter `warm_start` as it represents the sample-path solution of the previous RA iteration.
1. The return value must be a set of tuples representing feasible points; we do not recommend any particular name.  

In the third category, PyMOSO can accommodate any simulation optimization algorithm by implementing the `solve` function of a `MOSOSolver` sub-class [as shown](#template-moso-solver). It does not have to be a multi-objective algorithm. PyMOSO will require users to send an initial feasible point `x0` whether or not the algorithm needs it. The initial feasible point `x0` is accessed through `self.x0` which is a tuple. We now list the rules for implementing any `MOSOSolver.solve` function.
1. The `solve` function must be an instance method of `MOSOSolver`, and thus take `self` as its first parameter.
1. The second parameter is the simulation budget, a natural number.
1. The `solve` function must return a dictionary (we name it `results` in our example) with at least 3 keys: `'itersoln'`, `'simcalls'`, `'endseed'`. Researchers may track additional data and add it to `results` as desired.
   - The `'itersoln'` key itself corresponds to a dictionary with a key for each algorithm iteration labeled {0, 1, ...}. The value at each iteration is a set containing the estimated solution at the end of the iteration.
   - The `'simcalls'` key itself corresponds to a dictionary with a key for each algorithm iteration labeled {0, 1, ...}. The value at each iteration is a natural number containing the cumulative number of simulation replications taken at the end of the iteration.
   - The `'endseed'` key corresponds to a tuple of length 6, representing an `mrg32k3a` seed. The algorithm programmer should ensure the stream generated by `results['endseed']` is independent of all streams used by the algorithm.

Researchers may use the [MOSO template](#template-moso-solver)  to implement new simulation optimization algorithms.  

#### Template MOSO Solver
```python
from pymoso.chnbase import MOSOSolver

class MyMOSOAlg(MOSOSolver):
    '''Template implementation of a MOSO solver.'''

    def solve(self, budget):
        while self.num_calls <= budget:
            # implement algorithm logic and return the results
        return results
```

For convenience, in the mini-sections below, we also provide some example code snippets that we find useful when implementing algorithms in PyMOSO. They work without modification when using the templates above that inherit \inline{RLESolver} or \inline{RASolver}, but some functions may require implementation or modification for use in a `MOSOSolver`. For reference, [this section](#pymoso-object-reference) contains a list of most objects accessible to PyMOSO programmers.

##### Take Simulation Replications at a Point
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
##### Find Neighbors and Take Simulation Replications
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
##### Argsort a Dictionary of Points
```python
# 0 index for first objective
sorted_feas = sorted(nbors | {x}, key=lambda t: self.gbar[t][0])
```
##### Select the Minimizer and its Value
```python
xmin = sorted_feas[0]
fxmin = self.gbar[x]
```
##### Use SPLINE to Retrive a Local Minimizer
```python
# no constraints and minimize the 2nd objective
x0 = (2, 2, 2)
isfeas, fx, sex = self.estimate(x0)
# the suppressed value is the set visited along SPLINE's trajectory
_, xmin, fxmin, sexmin = self.spline(x0, float('inf'), 1, 0)
print(self.gbar[xmin] == fxmin) # True
```
##### Find the Non-Dominated Points in a Dictionary
```python
from chnutils import get_nondom
nondom = get_nondom(self.gbar)
```
##### Randomly Select Points in a Set
```python
solver_rng = self.sprn
# pick 5 points -- returns a list, not a set.
ran_pts = solver_rng.sample(list(nondom), 5)
one_in_five = solver_rng.choice(ran_pts)
```

### Using `solve` and `testsolve` in Python Programs
Users may the `solve` and `testsolve` functions within a Python program.

#### Minimal `solve` Example
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
#### Some `solve` Examples with Options
```python
# example for specifying budget and seed
budget=10000
seed = (111, 222, 333, 444, 555, 666)
soln1 = solve(mp.MyProblem, rp.RPERLE, x0, budget=budget, seed=seed)

# specify crn and simpar
soln2 = solve(mp.MyProblem, rp.RPERLE, x0, crn=True, simpar=4)

# specify algorithm specific parameters
soln3 = solve(mp.MyProblem, rp.RPERLE, x0, radius=2, betaeps=0.3, betadel=0.4)

# mix them
soln4 = solve(mp.MyProblem, rp.RPERLE, x0, crn=True, seed=seed, radius=5)
```

#### A `testsolve` Example
```python
# import the testsolve functions
from pymoso.chnutils import testsolve
# import the module containing RPERLE
import pymoso.solvers.rperle as rp
# import the MyTester class
from mytester import MyTester

# testsolve needs a "dummy" x0 even if MyTester will generate them
x0 = (1, )
run_data = testsolve(MyTester, rp.RPERLE, x0, isp=100, crn=True, radius=2)
```

#### Computing a Metric on `testsolve` Output
Programmers must compute their metric. Here, `run_data` is a dictionary of the form described [here](#implementing-pymoso-algorithms) and we compute the metric on the 5th iteration of of the 12th independent algorithm instance.
```python
iter5_soln = run_data[11]['itersoln'][4]
isp12_iter5_metric = MyTester.metric(iter5_soln)
```

## PyMOSO Object Reference
### The `pymoso.prng.mrg32k3a` Module
The `pymoso.prng.mrg32k3a` module exposes the pseudo-random number generator and functions to manipulate it.

| Object | Description |
| ------ | ----------- |
| `MRG32k3a` | Sub-class of random.Random, defines all `rng` objects. |
| `get_next_prnstream(seed)` | Return an `rng` object seeded 2^127 steps from the input seed.|
| `jump_substream(rng)` | Seed the input `rng` object 2^76 steps forward. |

### The `pymoso.chnbase` Module
The `pymoso.chnbase` module implements the base classes for oracles and solvers. Programmers should sub-class these when creating new PyMOSO implementations.
| Class | Description |
| ------ | ----------- |
| `Oracle` | Base class for implementing oracles. |
| `RLESolver` | Base class for implementing solvers using RLE. |
| `RASolver` | Base class for implementing RA solvers.|
|`MOSOSolver` | Base class for all solvers. |

### The `pymoso.chnutils` Module
The `pymoso.chnutils` contains useful functions for implementing and testing algorithms.  

| Function | Description |
| ------ | ----------- |
|`solve(oracle, solver, x0, **kwargs)` | [See here](#minimal-solve-example) for instructions. |
|`testsolve(tester, solver, x0, **kwargs)` | [See here](#a-testsolve-example) for instructions. |
|`does_weak_dominate(g, h, relg, relh)` | All inputs are tuples of equal length. Returns `True` if `g` weakly dominates `h` with the relaxations. |
|`does_dominate(g, h, relg, relh)` | Returns `True` if `g` dominates `h` with the relaxations. |
|`does_strict_dominate(g, h, relg, relh)` | Returns `True` if `g` strictly dominates `h` with the relaxations. |
|`get_nondom(obj_dict)` | Input: a dictionary with tuples for keys and values. The keys are feasible points; the values are their objective values. Return: a set of tuples representing non-dominated points. |
|`get_nbors(x, r)` | Input: a tuple `x`, a positive real scalar `r` indicating the neighborhood radius. Return: Set of tuples which are the neighbors.|
|`get_setnbors(S, r)` | Input: a set of tuples, and the neighborhood radius. Return: the union of `get_nbors(s, r)` for every `s` in `S`. |
| `dh(A, B)` | Returns the Hausdorff distance between set `A` and set `B`. |
|`edist(x1, x2)` | Return the Euclidean distance from `x1` to `x2`. |
|`get_metric(results, tester)` | Input: `results` is a dictionary, the output of each sample path of `testsolve`. `tester` must implement `metric`. Returns: The set of triples (iteration, simulation count, metric) for an algorithm run.|

### The `Oracle` Class
When implementing `RASolver` algorithms, programmers may not need to access `Oracle` objects directly at all. When implementing `MOSOSolver` algorithms, programmers will use (or wrap) `hit` and `crn_advance()`.  

| Member/Method | Description |
| ------ | ----------- |
|`num_obj` | A positive integer, the number of objectives.|
|`dim` | A positive integer, the dimensionality of feasible points. |
| `rng` | An instance of `MRG32k3a`.|
|`hit(x, n)` | Take `n` observations of `x`. Return: `True`, and a tuple containing the mean of the observations for each objective, and a tuple containing the standard error for each objective if `x` is feasible. The function handles CRN internally. |
|`set_crnflag(bool)` | Turn CRN on (`True`) or off. |
|`set_crnold(state)` | Save the `rng` state as the CRN baseline, e.g. for an algorithm iteration. Get the state using `rng.getstate()`. |
|`crn_reset()` | Back the oracle `rng` to the CRN baseline. |
|`crn_advance()` | If CRN is on, reset, and then jump to the next independent pseudo-random stream and save the new baseline, e.g. before starting a new algorithm iteration. |
|`crn_setobs()` | Set an intermediate CRN for individual oracle observations. |
|`crn_nextobs()` | Jump the `rng` forward, e.g. after taking an observation, and `crn_setobs` the seed. |
|`crn_check()` | f CRN is on, return to the baseline. Otherwise, use `crn_nextobs` before taking the next observation. |

### The `MOSOSolver` Class

The class provides a basic structure for implementing new MOSO algorithms in PyMOSO.  

| Member/Method | Description |
| ------ | ----------- |
|`orc` | The oracle object for the solver to solve. |
|`dim` | Number of dimensions of points in the feasible set. Should match `self.orc`|
|`num_obj`| Similarly, the number of objectives in `self.orc`. |
|`num_calls` | A running count of the number of simulation replications taken of `self.orc`.|
|`x0` | A feasible starting point. This point is additionally supplied to algorithms that don't need one.|

### The `RASolver` Class

The class implements a common structure for all RA algorithms, including: caching of simulation replications, scheduling and updating of sample sizes and limits, and a wrapper to `Oracle.hit`.  

| Member/Method | Description |
| ------ | ----------- |
|`sprn` | An instance of `MRG32k3a` for the solver to use.|
|`nbor_rad` | The neighborhood radius used by solvers seeking local optimality. |
| `gbar` | A dictionary where every key and value is a tuple. The keys are feasible points, values are their objective values. `gbar` is "wiped" every retrospective iteration. |
|`sehat` | Exactly like `gbar` except the values are standard errors.|
|`m` | The sample size of the current iteration. |
|`calc_m(nu)` | Compute the sample size of the current iteration. RA algorithms automatically do this every iteration and assign the value to `m'.|
|`b` | The searching sample limit of the current iteration. |
|`calc_b(nu)` | Exactly as `calc_m` but for the searching sample limit.|
|`estimate(x, c, obj)`| The `estimate` function is essentially a smart wrapper for `self.orc.hit`. Inputs: tuple `x` to sample, `c` a feasibility constraint, `obj` the objective to constrain. Return: same as `Oracle.hit`. Retrieves or saves the results from/to `gbar` and `sehat` as appropriate. Returns not feasible if the otherwise feasible result is not less than the constraint.|
|`upsample(S)`| A version of `estimate` for sets. Returns the feasible subset of `S`.|
|`spline(x, c, obmin, obcon)` | Return a sample path local minimizer. Input: a feasible start, constraint, objective to minimize, objective to constrain. Return: a set of tuples of the trajectory, the minimizer tuple, the minimum tuple, the standard error tuple.|

### The `RLESolver` Class

The sub-class of \inlinetwo{RASolver} adds RLE and its relaxation.

| Member/Method | Description |
| ------ | ----------- |
|`betadel` | Affects the relaxation values computed in RLE. |
|`calc_delta(se)` | Computes the RLE relaxation given a standard error, using `self.m` and `self.betadel`. |
|`rle(candidate_les)` | Input: set of tuples, Returns: set of tuples. Finds the LES at sample size `self.m`.|
