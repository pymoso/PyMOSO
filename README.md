# PyMOSO

PyMOSO is software for solving multi-objective simulation optimization (MOSO) problems and for creating, comparing, and testing MOSO algorithms.

## Reference

If you use PyMOSO in work leading to publication, please cite the paper which introduces PyMOSO.

Cooper, K., Hunter, S. R. 2020. PyMOSO: Software for Multi-Objective Simulation Optimization with R-PERLE and R-MinRLE. <em>INFORMS Journal on Computing</em>, 32(4): 1101-1108. DOI: http://dx.doi.org/10.1287/ijoc.2019.0902, Preprint: http://web.ics.purdue.edu/~hunter63/PAPERS/pre2019coohun.pdf.

## Additional Reading
The initial release of PyMOSO contains solvers that implement four total algorithms, in alphabetical order: R-MinRLE, R-PE, R-PERLE, and R-SPLINE.  The algorithms R-MinRLE, R-PE, R-PERLE were introduced in the following paper:

Cooper, K., Hunter, S. R., and Nagaraj, K. 2020. Bi-objective simulation optimization on integer lattices using the epsilon-constraint method in a retrospective approximation framework. <em>INFORMS Journal on Computing</em>, 32(4): 1080-1100. DOI: http://dx.doi.org/10.1287/ijoc.2019.0918, Preprint: http://web.ics.purdue.edu/~hunter63/PAPERS/pre2019coohunnag.pdf.

The algorithm R-SPLINE was introduced in the following paper:

Wang, H., Pasupathy, R., and Schmeiser, B. W. 2013. Integer-ordered simulation optimization using R-SPLINE: Retrospective Search with Piecewise-Linear Interpolation and Neighborhood Enumeration. <em>ACM Transactions on Modeling and Computer Simulation</em>, Vol. 23, No. 3, Article 17 (July 2013), 24 pages.  http://dx.doi.org/10.1145/2499913.2499916

We recommend reading these papers to understand the algorithms, what they return, and the algorithm parameter options that we describe in the user manual.

Table of Contents
=================

   * [PyMOSO](#pymoso)
      * [Reference](#reference)
      * [Additional Reading](#additional-reading)
      * [Installation](#installation)
         * [Before you begin](#before-you-begin)
         * [Install PyMOSO from the Python Packaging Index](#install-pymoso-from-the-python-packaging-index)
         * [Install PyMOSO from the repository](#install-pymoso-from-the-repository)
         * [Install PyMOSO from source code](#install-pymoso-from-source-code)
         * [Confirm the installation](#confirm-the-installation)
         * [Optional extras](#optional-extras)
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
            * [Selecting a Generator, and Running on Spark](#selecting-a-generator-and-running-on-spark)
            * [A testsolve Example](#a-testsolve-example)
            * [Computing a Metric on testsolve Output](#computing-a-metric-on-testsolve-output)
      * [PyMOSO Object Reference](#pymoso-object-reference)
         * [The pymoso.prng.mrg32k3a Module](#the-pymosoprngmrg32k3a-module)
         * [The pymoso.chnbase Module](#the-pymosochnbase-module)
         * [The pymoso.chnutils Module](#the-pymosochnutils-module)
         * [The Oracle Class](#the-oracle-class)
         * [Errors About Streams](#errors-about-streams)
         * [The MOSOSolver Class](#the-mososolver-class)
         * [The RASolver Class](#the-rasolver-class)
         * [The RLESolver Class](#the-rlesolver-class)

## Installation
Since PyMOSO is programmed in Python, every PyMOSO user must first install Python. We discuss three different methods to install PyMOSO: first, from the Python Packaging Index; second, directly from our source code using git; and third, installing PyMOSO from a copy of our source code. PyMOSO itself needs nothing beyond Python; the [optional extras](#optional-extras) at the end of this section add dependencies for specific uses.

### Before you begin

PyMOSO requires Python 3.10 or newer, which can be downloaded from https://www.python.org/downloads/. PyMOSO 1.0.8 and earlier ran on Python 3.6. To check which version you have, open a terminal and run `python --version`. On Windows, use `py --version`; on some systems, use `python3 --version`.

We recommend installing PyMOSO into a *virtual environment*, a self-contained folder that keeps PyMOSO and its setup separate from other Python software on your computer. Many recent operating systems require this and will refuse to install packages without one. To create and activate a virtual environment, open a terminal, navigate to the folder where you want to work, and run:

On macOS and Linux:

```shell
python3 -m venv .venv
source .venv/bin/activate
```

On Windows:

```shell
py -m venv .venv
.venv\Scripts\activate
```

While the environment is active, the commands `python` and `pip` refer to the environment's own copy, on every operating system. Run the activation command again whenever you open a new terminal to use PyMOSO.

In a hosted notebook, such as Databricks, the notebook's environment takes the place of a virtual environment; see [Optional extras](#optional-extras).

### Install PyMOSO from the Python Packaging Index

We keep stable releases of PyMOSO on the Python Packaging Index (PyPI), and we recommend this method for most users. With your virtual environment active, run:

```shell
python -m pip install pymoso
```

We write `python -m pip` rather than `pip` because it guarantees that PyMOSO is installed for the same Python you will run it with.

This installs the latest release. PyMOSO 2 changes some commands and functions from PyMOSO 1; [`CHANGELOG.md`](CHANGELOG.md) lists what to change. To stay on PyMOSO 1, run `python -m pip install "pymoso<2"` instead.

### Install PyMOSO from the repository

Users with `git` installed can install PyMOSO directly from our source code:

```shell
python -m pip install "git+https://github.com/pymoso/PyMOSO.git"
```

This installs whatever the repository's default branch holds at that moment: the development version of PyMOSO 2, which may be newer than the latest release and is less tested. We consider it less stable than the releases we publish to PyPI, and thus we recommend most users install PyMOSO from PyPI. To install a specific release from the repository instead, add its tag to the address, for example:

```shell
python -m pip install "git+https://github.com/pymoso/PyMOSO.git@v2.0.0"
```

### Install PyMOSO from source code

Users may follow the steps below to install PyMOSO from any version of the source code.

1. Acquire the PyMOSO source code from https://github.com/pymoso/PyMOSO. Users without `git` can use the green **Code** button and choose **Download ZIP**, then unzip the file. Specific versions are available from the repository's **Releases** page.
1. Open a terminal and navigate into the project directory, the folder that contains the file `pyproject.toml`.
1. With your virtual environment active, install PyMOSO from the current directory:

   ```shell
   python -m pip install .
   ```

   The trailing `.` means "this folder."

**Alternative: build a wheel file.** Most users can skip this. A wheel is PyMOSO packaged as a single installable file, which is sometimes what is needed when installing onto a cluster or a machine without internet access. From the project directory, with your virtual environment active, run:

```shell
python -m pip install build
python -m build
```

This creates a folder named `dist` containing a file named like `pymoso-x.x.x-py3-none-any.whl`, where `x.x.x` is the version. Copy that file wherever it is needed and install it with `python -m pip install`, followed by the file's path.

### Confirm the installation

To confirm any of the three methods worked, run `pymoso --version`. It prints the version of PyMOSO that was installed. <!-- verified: tests/test_cli.py::test_version_exits_zero_and_prints_version -->

### Optional extras
PyMOSO itself needs nothing beyond Python: it has no third-party runtime dependencies. <!-- verified: tests/test_dependency_boundary.py::test_the_core_runs_where_the_optional_dependencies_cannot_be_imported --> Two optional extras add dependencies for specific uses. Most users need neither.

- `python -m pip install "pymoso[notebook]"` adds `cloudpickle`, and nothing else. It is needed to run, with `simpar` or `proc` above 1, a problem, tester or solver class defined in a notebook cell, a REPL or inside a function, where a worker process cannot import it. Without it, such a call raises `ValueError` naming this extra. <!-- verified: tests/test_library_arguments.py::test_the_advice_for_a_class_with_no_source_leads_with_the_notebook_extra; tests/test_path_jobs.py::test_a_tester_that_cannot_be_transported_is_refused_only_when_it_would_have_to_be --> This is the extra a notebook on your own computer needs.
- `python -m pip install "pymoso[spark]"` adds `pyspark` (and `cloudpickle`), for opening a Spark session on your own machine. On Databricks or any cluster that already provides Spark, do not install it: it would install PyPI's `pyspark` over the cluster's own. Install `pymoso[notebook]` there instead; see [`docs/spark-backend.md`](docs/spark-backend.md).

An extra works with the other two methods too: `python -m pip install "pymoso[notebook] @ git+https://github.com/pymoso/PyMOSO.git"` from the repository, or `python -m pip install ".[notebook]"` from source code.

## Command Line Interface (CLI)
PyMOSO users solving MOSO problems and testing MOSO algorithms may do so using the command line interface. First, we show how to access the included help file. Then, we show how to view the lists of solvers, testers, and oracles installed by default with PyMOSO. Finally, we discuss the `solve` and `testsolve` commands.

### CLI help
PyMOSO includes a command line help file. The help file shows syntax templates for every PyMOSO command, the available options, and a selection of example invocations. The `pymoso --help` invocation prints the file to the terminal. When PyMOSO cannot parse an invocation that begins with `pymoso`, it prints the usage line of the command and an error. <!-- verified: tests/test_cli.py::test_malformed_invocation_exits_2_with_usage_on_stderr --> We show the current help file below.  

```
$ pymoso --help
usage: pymoso [-h] [-v] <command> ...

pymoso

positional arguments:
  <command>
    listitems    List the built-in solvers, problems, and testers.
    solve        Solve a MOSO problem.
    testsolve    Test a MOSO algorithm on a MOSO problem.

options:
  -h, --help     show this help message and exit
  -v, --version  show program's version number and exit

Examples:
  pymoso listitems
  pymoso solve ProbTPA RPERLE 4 14
  pymoso solve --budget=100000 --odir=test1  ProbTPB RMINRLE 3 12
  pymoso solve --seed 12345,32123,5322,2,9543,666666666 ProbTPC RPERLE 5 5 5
  pymoso solve --simpar=4 --param betaeps 0.4 ProbTPA RPERLE 30 30
  pymoso solve --param radius 3 ProbTPA RPERLE 45 45
  pymoso testsolve --isp=16 --proc=4 TPATester RPERLE
  pymoso testsolve --isp=20 --proc=10 --metric --crn TPBTester RMINRLE 9 9

Help:
  Use the listitems command to view a list of available solvers, problems, and
  test problems.

$ pymoso solve --help
usage: pymoso solve [-h] [--budget BUDGET] [--odir ODIR] [--crn] [--seed <s>]
                    [--generator {mrg31k3p,mrg32k3a,philox4x32}]
                    [--param <param> <val>] [--simpar SIMPAR]
                    <problem> <solver> <x> [<x> ...]

positional arguments:
  <problem>
  <solver>
  <x>

options:
  -h, --help            show this help message and exit
  --budget BUDGET       Set the simulation budget [default: 200]
  --odir ODIR           Set the output file directory name. [default: testrun]
  --crn                 Set if common random numbers are desired.
  --seed <s>            Set the random number seed, as comma-separated
                        integers with no spaces -- 6 for mrg32k3a/mrg31k3p, 2
                        for philox4x32 (see --generator), e.g. --seed
                        12345,32123,5322,2,9543,666666666. Arity and content
                        are validated against whichever generator is selected.
  --generator {mrg31k3p,mrg32k3a,philox4x32}
                        Set the pseudo-random number generator [default:
                        mrg32k3a].
  --param <param> <val>
                        Specify a solver-specific parameter <param> <val>.
                        Repeatable.
  --simpar SIMPAR       Set number of parallel processes for simulation
                        replications. [default: 1]

$ pymoso testsolve --help
usage: pymoso testsolve [-h] [--budget BUDGET] [--odir ODIR] [--crn]
                        [--seed <s>]
                        [--generator {mrg31k3p,mrg32k3a,philox4x32}]
                        [--param <param> <val>] [--isp ISP] [--proc PROC]
                        [--metric]
                        <tester> <solver> [<x> ...]

positional arguments:
  <tester>
  <solver>
  <x>

options:
  -h, --help            show this help message and exit
  --budget BUDGET       Set the simulation budget [default: 200]
  --odir ODIR           Set the output file directory name. [default: testrun]
  --crn                 Set if common random numbers are desired.
  --seed <s>            Set the random number seed, as comma-separated
                        integers with no spaces -- 6 for mrg32k3a/mrg31k3p, 2
                        for philox4x32 (see --generator), e.g. --seed
                        12345,32123,5322,2,9543,666666666. Arity and content
                        are validated against whichever generator is selected.
  --generator {mrg31k3p,mrg32k3a,philox4x32}
                        Set the pseudo-random number generator [default:
                        mrg32k3a].
  --param <param> <val>
                        Specify a solver-specific parameter <param> <val>.
                        Repeatable.
  --isp ISP             Set number of algorithm instances to solve. [default:
                        1]
  --proc PROC           Set number of parallel processes for the algorithm
                        instances. [default: 1]
  --metric              Set if metric computation is desired.

$ pymoso listitems --help
usage: pymoso listitems [-h]

options:
  -h, --help  show this help message and exit
```
For now, PyMOSO has three commands: `listitems`, `solve`, and `testsolve`, which we explain below.
### The `listitems` command for viewing solvers, testers, and oracles included in PyMOSO
The default installation of PyMOSO includes a selection of solvers, testers, and oracles. Users can view the complete lists of included solvers, testers, and oracles using the `pymoso listitems` command. We show the current listing below. Test problems A, B, and C refer to those in Cooper et al (2018). The listing includes two example solvers, `ExampleSearchSolver` and `ExampleBnBSolver`, that this README does not describe: they are installed, but their correctness has not been reviewed; see [`docs/mocompass-mopbnb-known-issues.md`](docs/mocompass-mopbnb-known-issues.md).

```

Solver                 Description
*********************  ************************************************************
ExampleBnBSolver       Example implementation of MOPBnB, unverified against the
                       source paper.
ExampleSearchSolver    Example implementation of MO-COMPASS, unverified against the
                       source paper.
RMINRLE                A solver using R-MinRLE for integer-ordered MOSO.
RPE                    R-Pe solver for bi-objective simulation optimization.
RPERLE                 R-PERLE solver for bi-objective simulation optimization.
RSPLINE                R-SPLINE solver for single-objective simulation
                       optimization.

Problems               Description                                                   Test Name (if available)
*********************  ************************************************************  ************************
BSProb                 An Oracle that simulates a bus-scheduling problem,            BSTester
                       minimizing total passenger wait time and bus-dispatch cost.
ProbExpensive          An Oracle simulating the same problem as ProbSimpleSO, plus
                       a tunable CPU burn per replication that does not affect
                       g()'s output.
ProbExpensiveHeavy     ProbExpensive at a heavy cost tier: burn_units=60,000.
ProbExpensiveLight     ProbExpensive at a light cost tier: burn_units=2,000.
ProbExpensiveModerate  ProbExpensive at a moderate cost tier: burn_units=20,000.     ExpensiveTester
ProbSimpleSO           An Oracle that simulates the Test Simple SO problem.          SimpleSOTester
ProbTPA                An Oracle that simulates Test Problem A.                      TPATester
ProbTPB                An Oracle that simulates Test Problem B.                      TPBTester
ProbTPC                An Oracle that simulates Test Problem C.                      TPCTester
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

`pymoso solve myproblem.py RSPLINE 97`  

Regardless of the chosen solver, PyMOSO creates a new sub-directory of the working directory containing output. There will be a metadata file, indicating the date, time, solver, problem, and any other specified options. In addition, PyMOSO creates a file containing the solver-generated solution. PyMOSO provides additional options for users solving MOSO problems. We present examples of each option below. First, users can specify the name of the output directory.  

`pymoso solve --odir=OutDirectory myproblem.py RPERLE 45`  

Users can specify the simulation budget, which is currently set to a default of 200.  

`pymoso solve --budget=100000 myproblem.py RPERLE 12`  

Users may specify to take simulation replications in parallel. With an oracle that draws its random numbers from `rng` (see [Implementing PyMOSO Oracles](#implementing-pymoso-oracles)), the results are identical to a run without `--simpar`, for any number of processes. <!-- verified: tests/test_parallel_dispatch.py::test_simpar_num_calls_and_results_match_serial; tests/test_executor.py::test_pool_results_equal_serial_results_for_any_worker_count --> How much faster a run becomes depends on the cost of one replication and on how many replications the solver requests at once, which bounds the speedup whatever the number of processes; [`docs/simpar-ceiling.md`](docs/simpar-ceiling.md) has measurements.  

`pymoso solve --simpar=4 myproblem.py RPERLE 44`  

All built-in solvers except the two example solvers, `ExampleSearchSolver` and `ExampleBnBSolver`, support common random numbers. <!-- verified: tests/test_example_solvers_compat.py::test_crn_refused_at_construction; tests/test_golden.py::test_end_seed_matches_baseline; tests/test_get_nbors_equivalence.py::test_whole_solver_runs_are_identical_to_runs_on_the_box_enumeration --> Users may enable the functionality using the `--crn` option.  

`pymoso solve --crn myproblem.py RMINRLE 62`  

We do not recommend this option unless the oracle is implemented to be compatible, that is, the oracle uses PyMOSO's pseudo-random number generator to generate pseudo-random numbers or to provide a seed to an external `mrg32k3a` generator (see [Implementing PyMOSO Oracles](#implementing-pymoso-oracles)).   

Users may specify an initial seed to PyMOSO's pseudo-random number generator using `--seed`, as comma-separated integers with no spaces. The required count and shape depend on which generator is selected (`--generator`, below): the default `mrg32k3a`, and `mrg31k3p`, both take 6 integers; `philox4x32` takes 2. The default seed is `12345` for each component: 6 of them for `mrg32k3a` and `mrg31k3p`, 2 for `philox4x32`. <!-- verified: tests/test_kwarg_defaults.py::test_default_values_are_the_documented_ones; tests/test_generator_selection.py::test_solve_with_no_generator_still_uses_mrg32k3a_default -->  

`pymoso solve --seed 1111,2222,3333,4444,5555,6666 myproblem.py RPERLE 23`  

Users may select which pseudo-random number generator to use with `--generator {mrg32k3a,mrg31k3p,philox4x32}` (default `mrg32k3a`). Every generator supports `--crn`. <!-- verified: tests/test_generator_selection.py::test_mrg31k3p_supports_crn; tests/test_generator_selection.py::test_philox_solves_end_to_end_under_crn -->  

`pymoso solve --generator philox4x32 --seed 1111,2222 myproblem.py RPERLE 23`  

Users may specify algorithm-specific parameters (see the papers in which the algorithms were introduced for detailed explanations of the parameters.) All parameters are specified in the form `--param name value`. For example, the RLE relaxation parameter can be specified and set as `betadel` to a real number. We refer the reader to [the table](#table-of-algorithm-specific-parameters) for the full list of currently available algorithm-specific parameters.  

`pymoso solve --param betadel 0.2 myproblem.py RPERLE 34`  

Finally, users may specify any number of options in one invocation, in any order. <!-- verified: tests/test_cli.py::test_options_after_positional_args_still_accepted; tests/test_cli.py::test_seed_and_param_interleaved_out_of_order_now_parses_correctly --> (Note that the `\` at the end of the first line continues the command to the second line.)

`pymoso solve --crn --simpar=4 --budget=10000 --seed 1,2,3,4,5,6 \`  
`     --odir=Exp1 --param mconst 4 --param betadel 0.7 myproblem.py RPERLE 97`  


#### Table of Algorithm-Specific Parameters  

| Parameter Name | Default Value | Affected Solvers | Description |
| -------------- | ------------- | ---------------- | ----------- |
| `mconst` | `2` | `RMINRLE`, `RPE`, `RPERLE`, `RSPLINE` | Initialize the sample size and subsequent schedule of sample sizes. |
| `bconst` | `8` | `RMINRLE`, `RPE`, `RPERLE`, `RSPLINE` | Initialize the search sampling limit and subsequent schedule of limits. |
| `radius` | `1` | `RMINRLE`, `RPE`, `RPERLE`, `RSPLINE` | Sets radius that determines a point's neighborhood. |
| `bestimprove` | `0` | `RMINRLE`, `RPE`, `RPERLE`, `RSPLINE` | Set to 1 to search the whole neighborhood for its best point, rather than move to the first improving one. |
| `quadratic` | `0` | `RMINRLE`, `RPE`, `RPERLE`, `RSPLINE` | Set to 1 to add a quadratic candidate to the neighborhood search, fitted along each axis (radius 1 only; useful with bestimprove). |
| `betadel` | `0.5` | `RMINRLE`, `RPERLE` | Roughly, affects how likely it is for RLE to keep its given solution. |
| `betaeps` | `0.5` | `RPE`, `RPERLE` | Roughly, affects how likely PE will perform a search from a point. |
| `lb` | *(required)* | `ExampleBnBSolver`, `ExampleSearchSolver` | Lower bound each feasible point's components may take. |
| `ub` | *(required)* | `ExampleBnBSolver`, `ExampleSearchSolver` | Upper bound each feasible point's components may take. |
| `numsamples` | `8` | `ExampleSearchSolver` | Number of feasible points to sample per iteration. |
| `subregions` | `2` | `ExampleBnBSolver` | Number of subregions to branch each region into. |
| `alpha` | `0.05` | `ExampleBnBSolver` | Overall confidence parameter. |
| `delta` | `0.1` | `ExampleBnBSolver` | Sampling ratio used for subregion elimination. |
| `R0` | `20` | `ExampleBnBSolver` | Initial number of replications taken per point. |


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
`    --crn --seed 1,2,3,4,5,6 mytester.py RPERLE`  

Users may want to compute some metric on the algorithm-generated solutions. If a metric is defined as part of the tester, such as in `MyTester`, the `testsolve` command can compute the metric on every algorithm iteration using the `--metric` option.  

`pymoso testsolve  --metric  mytester.py RPERLE`  

The `testsolve` command cannot perform simulation replications in parallel. However, testers can apply the solvers to independent sample paths of the problems. For example, to test `RPERLE` on 100 independent sample paths of `MyProblem`, compute the metrics for each sample path, and use common random numbers in each sample path, use the following command.  

`pymoso testsolve --crn --metric --isp=100 mytester.py RPERLE`  

PyMOSO can perform independent algorithm runs in parallel. Use the `--proc` option to specify the number of processes available to PyMOSO.  

`pymoso testsolve --crn --metric --isp=100 --proc=20 mytester.py RPERLE`  

Every independent sample path has its own streams, with room for 2^31 retrospective approximation (RA) iterations (2^30 with `philox4x32`). A run that would exceed it raises `IterationOverflow` rather than continuing into another path's streams; <!-- verified: tests/test_sync_isp_nesting.py::test_iteration_past_the_default_zone_raises --> with the default settings the sample size would long since have exceeded what any budget allows. <!-- verified: tests/test_sync_isp_nesting.py::test_builtin_sample_size_schedule_cannot_approach_the_iteration_ceiling -->  

The `testsolve` command creates a results file for each independent sample path. The file contains the solutions generated at every algorithm iteration, such that the solution of iteration 2 is on line 2, iteration 10 on line 10, and so forth. If `--metric` is specified, PyMOSO generates a second file for each independent sample path containing the collection of triples (iteration number, simulations used at end of iteration, metric).  

## Implementing problems, testers, and algorithms in PyMOSO
To use PyMOSO, users solving MOSO problems must implement a PyMOSO oracle, and users testing MOSO algorithms should implement, at least, a PyMOSO oracle and tester. In this section, we provide template Python code to help users quickly implement oracles, testers, and perhaps solvers in PyMOSO.

### Implementing PyMOSO Oracles
Usually, implementing a PyMOSO oracle implies implementing a Monte Carlo simulation oracle as a black box function while following the PyMOSO rules put forth in this section. For reference, we discuss the example PyMOSO oracle `MyProblem` in [The Example Oracle](#the-example-oracle). Users may copy the code in [The Example Oracle](#the-example-oracle) and re-implement the function `g` as needed. We now list the basic requirements of every `g` implementation.  

1. The function `g` must be an instance method of an `Oracle` sub-class, and thus take `self` as its first parameter.
1. The function `g` must take an arbitrarily-named second parameter which is a tuple of length `self.dim` and represents a point. Stylistically, PyMOSO consistently names this parameter `x`.
1. The function `g` must take an arbitrarily-named third parameter, a pseudo-random number generator with the methods of Python's `random.Random`. Stylistically, PyMOSO consistently names this parameter `rng`.
1. The function `g` must return a boolean first and a tuple of length `self.num_obj` second.
   - The boolean is `True` if `x` is feasible, and `False` otherwise.
   - If `x` is feasible, the tuple contains a single observation of every objective. If `x` is not feasible, each element in the tuple is `None`.
1. At a feasible `x`, every objective's observations must have finite variance. The convergence results of the built-in algorithms assume it (Lemma 5.2 of the paper that introduces R-SPLINE; Assumption 3 of the paper that introduces R-MinRLE, R-PE and R-PERLE). PyMOSO does not check it.

If users already have an implemented simulation oracle, they may find it convenient to implement `g` as wrapper which calls that simulation from Python. As an example, suppose a user has implemented a simulation in C which is compiled to a C library called `mysim.so` and placed in the working directory. Suppose further that the simulation function takes the following as parameters: an array of integers representing a point and an unsigned integer representing the number of observations to take at `x`. The function output is defined as `struct Simout` with members `feas` set to 0 or 1, `obj` a double array set to the mean of the observed objective values, and `var` a double array set to the sample variance of the observed objective values. Then users can modify the template to wrap the C function `struct Simout c_func(int x, int n)` as in [the example](#example-oracle-that-wraps-a-c-simulation).  

#### Example Oracle that Wraps a C Simulation
```python
from ctypes import CDLL, c_double, c_uint, c_int, Structure
import os.path
libname = 'mysim.so'
libabspath = os.path.dirname(os.path.abspath(__file__)) + os.path.sep + libname
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


[The C wrapper example](#example-oracle-that-wraps-a-c-simulation) is a valid PyMOSO oracle which wraps a C function. However, PyMOSO algorithms cannot enable common random numbers on this oracle. Furthermore, PyMOSO cannot guarantee that observations are independent when taken in parallel. To enable these properties, the external simulation must use the same generator as the run (`mrg32k3a` by default) and must accept a user-specified seed.  

Suppose the library `mysim.so` also implements the function `set_simseed` which accepts an array of six 64-bit integers representing an `mrg32k3a` seed. (A component of an `mrg32k3a` seed can exceed 2^31, so a C `long`, which is 32 bits on Windows, is not wide enough.) We modify the [wrapper](#example-oracle-that-wraps-a-c-simulation) for compatibility with common random numbers and to guarantee independence of parallel observations.  [The new wrapper](#example-wrapper-with-pymoso-random-numbers) demonstrates using `rng.get_seed()` to return the current `mrg32k3a` seed.

#### Example Wrapper with PyMOSO Random Numbers
```python
from ctypes import CDLL, c_double, c_uint, c_int, Structure, c_int64
import os.path
libname = 'mysim.so'
libabspath = os.path.dirname(os.path.abspath(__file__)) + os.path.sep + libname
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
        # convert the seed to an array of 64-bit integers
        c_int64arr = c_int64*6
        c_seed = c_int64arr(seed[0], seed[1], seed[2], seed[3], seed[4], seed[5])
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

The `rng` object provides the methods of Python's `random.Random` class: with `mrg32k3a` and `mrg31k3p` it is a sub-class of `random.Random`, and with `philox4x32` it is an adapter offering the same methods. <!-- verified: tests/test_generator_selection.py::test_ensure_random_compatible_leaves_a_random_random_subclass_alone; tests/test_generator_selection.py::test_ensure_random_compatible_wraps_a_bare_stream --> The official Python documentation for `random` therefore applies to `rng` and is found at https://docs.python.org/3/library/random.html. With every generator, `rng.normalvariate` uses the Beasley-Springer-Moro algorithm (Law 2015, p. 458) to approximate the inverse of the standard normal cumulative distribution function.

When using `rng`, PyMOSO computes where each replication's random numbers begin from its coordinates -- the run's seed, the RA iteration, the point, and the replication's number -- rather than by walking one stream forward. Replications are therefore independent of each other, and a run's results do not depend on the order in which replications are taken or on which process takes them. <!-- verified: tests/test_oracle_coordinate_migration.py::test_order_independence_within_one_iteration_crnflag_false; tests/test_executor.py::test_results_do_not_depend_on_grouping_or_order_of_blocks; tests/test_replication_independence.py::test_replications_do_not_share_raw_draws -->

Without common random numbers, each replication has room for 16,384 uniform draws, with every generator, unless the oracle's class says otherwise. Most methods of `rng` (`random`, `normalvariate`, `expovariate`, ...) use one draw per call. A `g` that uses more raises `ReplicationDrawOverflow` instead of reaching into the next replication's random numbers. <!-- verified: tests/test_replication_independence.py::test_every_generator_gives_a_replication_16384_draws; tests/test_executor.py::test_the_draw_reserve_is_enforced_in_the_worker --> An oracle whose `g` needs more sets `replication_draws` on its class, to a power of two up to 2^40, for example `replication_draws = 2**20` beside `num_obj` and `dim`. <!-- verified: tests/test_replication_draws.py::test_a_larger_reserve_is_honoured_exactly; tests/test_replication_draws.py::test_a_value_that_is_not_a_power_of_two_in_range_is_refused --> The room comes out of the code a point's random numbers are computed from: at 2^20 draws a two-dimensional point's components are coded exactly up to about 8.6 billion, at 2^40 up to about 8.4 million, and a point beyond that, or with many components, is hashed instead. Hashing is checked: two points in one RA iteration that would share random numbers raise `PointCodeCollision`. <!-- verified: tests/test_replication_draws.py::test_the_bits_come_out_of_the_point_code; tests/test_point_code_fallback.py::test_two_different_points_with_the_same_code_raise --> Changing `replication_draws` changes that oracle's random numbers. With `--crn`, replications are 2^76 draws apart (more with `philox4x32`), and every point in an RA iteration uses the same replications. <!-- verified: tests/test_oracle_coordinate_migration.py::test_crn_every_replication_within_one_iteration_matches_the_coordinate_formula; tests/test_oracle_coordinate_migration.py::test_crn_different_points_in_the_same_iteration_share_the_same_replication_streams --> Every RA iteration, and every independent sample path of `testsolve`, has streams of its own. <!-- verified: tests/test_testsolve_role_layout.py::test_no_two_role_streams_start_at_the_same_position; tests/test_oracle_visit_sync.py::test_no_collision_between_isp_paths_at_iteration_counts_well_beyond_max_ri -->

A point is a tuple of numbers. A whole number of any numeric type is that integer, so `30.0` and `30` are the same point with the same random numbers. <!-- verified: tests/test_point_types.py::test_a_whole_number_of_any_numeric_type_is_the_integer_it_equals --> A point containing `nan`, an infinity or something that is not a number is reported infeasible without calling `g`, with and without `--crn`. <!-- verified: tests/test_point_types.py::test_a_point_that_cannot_be_encoded_is_infeasible_and_is_not_simulated -->

### Implementing PyMOSO Testers  
Consider again the [example tester](#the-example-tester). As a minimal valid PyMOSO tester, users may do nothing but assign the `MyTester` member `self.ranorc` to a PyMOSO oracle, such as [`MyProblem`](#the-example-oracle), in Line 27. However, we expect most users to leverage PyMOSO features by implementing metrics and  feasible point generators. The function `get_ranx0` allows the tester to generate feasible points to `MyProblem` and `metric` allows the tester to compute a metric on sets returned by a solver. Researchers may implement any number of additional supporting functions, including members and methods of the tester class. The `true_g` function is an example of such a supporting function, which is used to compute the example metric.  

First, we list the rules for implementing a feasible point generator.
1. The function is arbitrarily named but must be set to the `self.get_ranx0` member of a tester.
1. The function must take a single parameter, an arbitrarily named `random.Random` object we suggest naming `rng`.
1. The function must return a tuple with length corresponding to the `self.dim` member of the `self.ranorc` member of the tester.

Since a researcher's desired metric depends on the algorithm capabilities and problem complexity, PyMOSO allows researchers to implement any metric they choose. We provide three example metrics, but first, we list the implementation rules of the `metric` function.  

1. The `metric` function must be an instance method of a tester, and thus take `self` as its first parameter.
1. The second parameter of `metric` is arbitrarily named and is a Python set of tuples.
1. PyMOSO does not enforce the return value of `metric`, but we recommend a scalar real number.

The metric implemented in the [example tester](#the-example-tester) is the Hausdorff distance from (a) the true image of an estimated solution returned by an algorithm, to (b) the true solution hard-coded as `myanswer`.  

For an example of a different metric, consider a MOSO problem that has more than one local efficient set (LES) and such that each LES contains no members of another LES. Since an algorithm that converges to a LES may find only one LES, we may define the metric to compute the Hausdorff distance between the true image of the estimated solution and the "closest" true LES, as follows. Let `self.answer` be implemented as a list of sets, and assume a `self.true_g` implementation. Then the [following example](#example-metric-1) implements the described metric.  

#### Example Metric 1
```python
def metric(self, eles):
    # use the distance to the closest set.
    epareto = [self.true_g(point) for point in eles]
    # self.answer is a list of sets
    dist_list = [dh(epareto, les) for les in self.answer]
    return min(dist_list)
```

For single-objective problems with one correct solution `x*`, a simple metric that takes an estimated solution `X` is `|g(X) - g(x*)|`, which we implement in the [second example metric](#example-metric-2) assuming an appropriate implementation of `self.answer` and `self.true_g`.  

#### Example Metric 2
```python
def metric(self, singleton_set):
    # single objective algorithms still return a set
    point, = singleton_set
    # let self.answer be a real number
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
As written below, this template cannot reach a normal budget-exhausted stop when run via `solve()`, at any budget: `spsolve` never calls `self.estimate`, so `self.num_calls` never advances past 0. It does not run forever, though -- after about 3,900 simulation-free iterations, a few milliseconds, the retrospective-approximation loop's own iteration-dependent search-limit formula (`calc_b`) overflows Python's float range and raises `OverflowError` (its message depends on the problem's dimension), naming neither this template nor the real cause. <!-- verified: tests/test_readme_examples.py::test_myraalg_solve_raises_overflowerror_quickly --> A real implementation must call `self.estimate` (directly, or via `self.upsample`/`self.spline`) to make progress against the budget; see KNOWN_ISSUES.md for the exact failure this produces as written.

```python
from pymoso.chnbase import RASolver

class MyRAAlg(RASolver):
    '''Template implementation of an RA solver.'''

    def spsolve(self, warm_start):
        '''Return the sample path solution.'''
        # implement algorithm logic here and return a set
        return warm_start
```

A solver that takes parameters of its own declares their names in a class attribute `PARAMS`, a tuple of strings, and removes them from its keyword arguments before calling `super().__init__(orc, **kwargs)`:

```python
from pymoso.solvers.rperle import RPERLE

class MyTunedRPERLE(RPERLE):
    '''R-PERLE with a parameter of its own.'''
    PARAMS = ('stubbornness',)

    def __init__(self, orc, **kwargs):
        # take this solver's own parameters before passing the rest on
        self.stubbornness = kwargs.pop('stubbornness', 1.0)
        super().__init__(orc, **kwargs)
```

A parameter no class in the solver's hierarchy takes -- a misspelling, or a parameter of another solver -- raises `TypeError` naming it and listing the parameters the solver does take. <!-- verified: tests/test_library_arguments.py::test_an_unknown_solver_parameter_is_refused_by_name_with_the_ones_that_exist; tests/test_readme_examples.py::test_mytuned_takes_its_parameter_and_refuses_a_misspelling --> A parameter's value must be a real number, and is passed to the solver as a float. <!-- verified: tests/test_library_arguments.py::test_a_parameter_that_is_not_a_number_is_refused_by_name; tests/test_library_arguments.py::test_a_numeric_parameter_reaches_the_solver_as_the_float_it_always_was -->

Though analogous to those of an `RLESolver.accel` method, for completeness, we list the requirements for an `RASolver.spsolve` method.
1. The `spsolve` function must be an instance method of an `RASolver` object, and thus its first parameter must be `self`.
1. The second parameter is arbitrarily named and is a set of tuples. We recommend naming the parameter `warm_start` as it represents the sample-path solution of the previous RA iteration.
1. The return value must be a set of tuples representing feasible points; we do not recommend any particular name.  

In the third category, PyMOSO can accommodate any simulation optimization algorithm by implementing the `solve` function of a `MOSOSolver` sub-class [as shown](#template-moso-solver). It does not have to be a multi-objective algorithm. PyMOSO will require users to send an initial feasible point `x0` whether or not the algorithm needs it. The initial feasible point `x0` is accessed through `self.x0` which is a tuple. A sub-class need not define `__init__` to receive it: `MOSOSolver` takes `x0`, and the solver's own stream `sprn`, whether or not the algorithm uses them, and refuses any other parameter no class in the solver's hierarchy takes. <!-- verified: tests/test_custom_mososolver.py::test_a_solver_with_no_constructor_receives_x0_and_sprn; tests/test_custom_mososolver.py::test_an_unknown_parameter_is_still_refused_by_name --> A sub-class with parameters of its own declares them in `PARAMS` and removes them before calling `super().__init__(orc, **kwargs)`, as shown [above](#template-ra-solver). We now list the rules for implementing any `MOSOSolver.solve` function.
1. The `solve` function must be an instance method of `MOSOSolver`, and thus take `self` as its first parameter.
1. The second parameter is the simulation budget, a natural number.
1. The `solve` function must return a dictionary (we name it `results` in our example) with at least 3 keys: `'itersoln'`, `'simcalls'`, `'endseed'`. Researchers may track additional data and add it to `results` as desired.
   - The `'itersoln'` key itself corresponds to a dictionary with a key for each algorithm iteration labeled {0, 1, ...}. The value at each iteration is a set containing the estimated solution at the end of the iteration.
   - The `'simcalls'` key itself corresponds to a dictionary with a key for each algorithm iteration labeled {0, 1, ...}. The value at each iteration is a natural number containing the cumulative number of simulation replications taken at the end of the iteration.
   - The `'endseed'` key corresponds to a seed for the run's generator from which no stream the algorithm used can be reached. `self.orc.get_endseed()` computes it from the oracle's own record of the streams it used. <!-- verified: tests/test_oracle_endseed.py::test_endseed_does_not_collide_with_any_touched_coordinate_offset_branch; tests/test_custom_mososolver.py::test_testsolve_runs_it_and_computes_the_same_end_seed -->

Researchers may use the [MOSO template](#template-moso-solver)  to implement new simulation optimization algorithms.  

#### Template MOSO Solver
This is a structural sketch, not a runnable template: it shows the required shape of a `MOSOSolver.solve()` (loop against the budget, return a `results` dict) rather than a working algorithm. Do not call `solve()` on this class as written.

```python
from pymoso.chnbase import MOSOSolver

class MyMOSOAlg(MOSOSolver):
    '''Structural sketch of a MOSO solver, illustrative only -- not meant to be run as written.'''

    def solve(self, budget):
        while self.num_calls <= budget:
            pass  # implement algorithm logic and return the results
        return results
```

For convenience, in the mini-sections below, we also provide some example code snippets that we find useful when implementing algorithms in PyMOSO. They work without modification when using the templates above that inherit `RLESolver` or `RASolver`, but some functions may require implementation or modification for use in a `MOSOSolver`. For reference, [this section](#pymoso-object-reference) contains a list of most objects accessible to PyMOSO programmers.

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
nbors = get_nbors(x, r)
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
fxmin = self.gbar[xmin]
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
from pymoso.chnutils import get_nondom
nondom = get_nondom(self.gbar)
```
##### Randomly Select Points in a Set
```python
solver_rng = self.sprn
# pick up to 5 points -- returns a list, not a set.
ran_pts = solver_rng.sample(list(nondom), min(5, len(nondom)))
one_in_five = solver_rng.choice(ran_pts)
```

### Using `solve` and `testsolve` in Python Programs
Users may use the `solve` and `testsolve` functions within a Python program. `solve` returns the solution and the seed the run ended at; `testsolve` returns a dictionary of every sample path's results and the seed the run ended at.

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
# solve returns the solution and the seed the run ended at
soln, endseed = solve(mp.MyProblem, rp.RPERLE, x0)
print(soln)
```
#### Some `solve` Examples with Options
```python
# example for specifying budget and seed
budget=10000
seed = (111, 222, 333, 444, 555, 666)
soln1, endseed1 = solve(mp.MyProblem, rp.RPERLE, x0, budget=budget, seed=seed)

# specify crn and simpar
soln2, endseed2 = solve(mp.MyProblem, rp.RPERLE, x0, crn=True, simpar=4)

# specify algorithm specific parameters
soln3, endseed3 = solve(mp.MyProblem, rp.RPERLE, x0, radius=2, betaeps=0.3, betadel=0.4)

# mix them
soln4, endseed4 = solve(mp.MyProblem, rp.RPERLE, x0, crn=True, seed=seed, radius=5)
```

#### Selecting a Generator, and Running on Spark
`solve` and `testsolve` take `generator=` with the same values as the CLI's `--generator` (`'mrg32k3a'`, the default, `'mrg31k3p'` or `'philox4x32'`); `seed=` must then have that generator's length.

They also take `backend=`, which decides where worker processes run. Without it, `simpar` and `proc` start processes on this machine. `pymoso.backends.spark.SparkBackend(spark)` runs `testsolve`'s sample paths, or `solve`'s replications, as Spark tasks, with results identical to the same call without `backend=`. <!-- verified: tests/test_remote_backend.py::test_sample_paths_on_a_remote_backend_are_identical_to_serial; tests/test_remote_backend.py::test_replications_on_a_remote_backend_are_identical_to_serial; tests/test_spark_backend.py::test_spark_computes_what_no_backend_computes --> [`docs/spark-backend.md`](docs/spark-backend.md) describes it, including when sending replications to a cluster pays.

`pymoso.dispatch_cost(problem, x, replications=..., parts=..., backend=...)` times one request for replications in this process and on a backend, and reports both times and whether the results were identical. It runs only when called. <!-- verified: tests/test_dispatch_cost.py::test_it_reports_one_request_in_place_and_on_the_backend; tests/test_dispatch_cost.py::test_it_reports_and_does_not_advise -->

#### A `testsolve` Example
```python
# import the testsolve functions
from pymoso.chnutils import testsolve
# import the module containing RPERLE
import pymoso.solvers.rperle as rp
# import the MyTester class
from mytester import MyTester

# testsolve always requires an x0 positionally, even though it is only
# actually used when ranx0=True is passed (otherwise every independent
# sample path uses this x0 unchanged); MyTester can generate its own
# per sample path via get_ranx0 if you pass ranx0=True below.
x0 = (1, )
run_data = testsolve(MyTester, rp.RPERLE, x0, isp=100, crn=True, radius=2)
```

#### Computing a Metric on `testsolve` Output
Programmers must compute their metric. Here, `run_data[0]` is a dictionary with one entry per independent sample path, each of the form described [here](#implementing-pymoso-algorithms), and we compute the metric on the 5th iteration of of the 12th independent algorithm instance.
```python
iter5_soln = run_data[0][11]['itersoln'][4]
isp12_iter5_metric = MyTester().metric(iter5_soln)
```

## PyMOSO Object Reference
### The `pymoso.prng.mrg32k3a` Module
The `pymoso.prng.mrg32k3a` module exposes the default pseudo-random number generator and functions to manipulate it. Two more generators, `pymoso.prng.mrg31k3p.MRG31k3p` and `pymoso.prng.philox4x32.Philox4x32Stream`, are also selectable via `--generator`/the `generator=` keyword argument to `solve()`/`testsolve()` (see [The `solve` command](#the-solve-command)); this table documents the default's own module only.

| Object | Description |
| ------ | ----------- |
| `MRG32k3a` | Sub-class of `random.Random`; the class of every `rng` object when `mrg32k3a` is selected. |
| `stream_at(seed, stream, offset)` | Return an `rng` object positioned `stream` streams of 2^127 and `offset` steps from `seed`. This is how PyMOSO computes every stream it uses. |
| `get_next_prnstream(seed)` | Return an `rng` object seeded 2^127 steps from the input seed. Kept from earlier versions; PyMOSO itself no longer uses it.|
| `jump_substream(rng)` | Seed the input `rng` object 2^76 steps forward. Kept from earlier versions; PyMOSO itself no longer uses it. |

### The `pymoso.chnbase` Module
The `pymoso.chnbase` module implements the base classes for oracles and solvers. Programmers should sub-class these when creating new PyMOSO implementations.
| Class | Description |
| ------ | ----------- |
| `Oracle` | Base class for implementing oracles. |
| `RLESolver` | Base class for implementing solvers using RLE. |
| `RASolver` | Base class for implementing RA solvers.|
|`MOSOSolver` | Base class for all solvers. |

| Function | Description |
| ------ | ----------- |
|`accepted_params(solver_class)` | The parameter names a solver class declares in `PARAMS`, merged over the classes it inherits from, sorted. |
|`reject_unknown_params(solver, leftover)` | Raise `TypeError` naming any parameter left in `leftover` and listing the accepted ones. For a solver that does not derive from `RASolver`, to call after taking its own parameters. |

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
|`gen_metric(results, tester)` | Input: `results` is a dictionary, the output of one sample path of `testsolve`. `tester` must implement `metric`. Returns: a dictionary with one triple (iteration, simulation count, metric) per algorithm iteration.|

### The `Oracle` Class
When implementing `RASolver` algorithms, programmers may not need to access `Oracle` objects directly at all. When implementing `MOSOSolver` algorithms, programmers will use (or wrap) `hit` or `hit_many`.  

| Member/Method | Description |
| ------ | ----------- |
|`num_obj` | A positive integer, the number of objectives.|
|`replication_draws` | A class attribute: how many uniform draws one replication of `g` may make without CRN. 16,384 unless set; a power of two up to 2^40. |
|`dim` | A positive integer, the dimensionality of feasible points. |
| `rng` | The oracle's stream, an instance of the selected generator's stream class. The streams `g` receives are computed from it. |
|`hit(x, m, visit=0, sync=None)` | Take `m` observations of `x`. Return: whether `x` is feasible, a tuple containing the mean of the observations for each objective, and a tuple containing the standard error for each objective. Without CRN, a second call for the same `x` in the same RA iteration takes new observations; with CRN, it takes the same ones again. <!-- verified: tests/test_oracle_noncrn_default.py::test_repeated_hit_for_the_same_point_continues_rather_than_restarts; tests/test_oracle_coordinate_migration.py::test_crn_repeat_hit_restarts_at_the_iteration_baseline --> `visit` and `sync` are for solvers that control which observations are shared (see `docs/rng-interface-design.md`, sections 4.1 and 4.3). The function handles CRN internally. |
|`hit_many(requests)` | The same as `[hit(x, m) for x, m in requests]`, with every observation handed to the parallel processes together under `--simpar`. <!-- verified: tests/test_batching.py::test_hit_many_is_the_hits_one_by_one; tests/test_batching.py::test_hit_many_hands_the_executor_every_block_in_one_call --> |
|`set_crnflag(bool)` | Turn CRN on (`True`) or off. Off unless set. <!-- verified: tests/test_oracle_direct_use.py::test_hit_on_a_fresh_oracle_is_hit_after_set_crnflag_false --> |
|`get_endseed()` | A seed for the run's generator from which none of the streams this oracle used can be reached. |

### Errors About Streams
Each of these is raised instead of letting two uses of random numbers overlap, and is importable from `pymoso.prng.base`. <!-- verified: tests/test_replication_independence.py::test_exceeding_the_replication_reserve_raises; tests/test_replication_independence.py::test_replication_count_overflow_raises; tests/test_sync_isp_nesting.py::test_iteration_past_the_default_zone_raises; tests/test_testsolve_role_layout.py::test_more_paths_than_the_layout_holds_raises_immediately; tests/test_testsolve_role_layout.py::test_a_role_stream_that_overran_its_stream_raises; tests/test_sync_isp_nesting.py::test_sync_value_past_the_zone_raises; tests/test_replication_independence.py::test_visit_overflow_raises; tests/test_point_code_fallback.py::test_two_different_points_with_the_same_code_raise -->

| Exception | Raised when |
| ------ | ----------- |
|`ReplicationDrawOverflow` | Without CRN, one replication of `g` used more than the oracle's `replication_draws` uniform draws (16,384 unless its class sets it). |
|`ReplicationOverflow` | One `hit` asked for more replications than a coordinate holds (2^32 with `mrg32k3a` and `mrg31k3p`, 2^30 with `philox4x32`). |
|`IterationOverflow` | A run passed the RA iterations one sample path has room for (2^31, or 2^30 with `philox4x32`). |
|`IspOverflow` | `testsolve` was asked for more independent sample paths than the generator lays out. |
|`RoleDrawOverflow` | A solver's own stream, or the stream that draws starting points, used more than one stream holds. |
|`SyncOverflow`, `VisitOverflow` | A solver passed `hit` a `sync` or `visit` value too large. |
|`PointCodeCollision` | Two different points in one RA iteration would have shared random numbers. Possible only for points too large or too many-dimensional for an exact code. |

### The `MOSOSolver` Class

The class provides a basic structure for implementing new MOSO algorithms in PyMOSO.  

| Member/Method | Description |
| ------ | ----------- |
|`orc` | The oracle object for the solver to solve. |
|`dim` | Number of dimensions of points in the feasible set. Should match `self.orc`|
|`num_obj`| Similarly, the number of objectives in `self.orc`. |
|`num_calls` | A running count of the number of simulation replications taken of `self.orc`.|
|`x0` | A feasible starting point. This point is additionally supplied to algorithms that don't need one.|
|`sprn` | The solver's own stream, of the selected generator, for the solver's own random choices. |

### The `RASolver` Class

The class implements a common structure for all RA algorithms, including: caching of simulation replications, scheduling and updating of sample sizes and limits, and a wrapper to `Oracle.hit`.  

| Member/Method | Description |
| ------ | ----------- |
|`sprn` | The solver's own stream, of the selected generator, for the solver to use.|
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

The sub-class of `RASolver` adds RLE and its relaxation.

| Member/Method | Description |
| ------ | ----------- |
|`betadel` | Affects the relaxation values computed in RLE. |
|`calc_delta(se)` | Computes the RLE relaxation given a standard error, using `self.m` and `self.betadel`. |
|`rle(candidate_les)` | Input: set of tuples, Returns: set of tuples. Finds the LES at sample size `self.m`.|
