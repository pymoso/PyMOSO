# pychn

This project implements the R-PERLE algorithm for solving bi-objective simulation optimization problems on integer lattices and the R-MinRLE algorithm, a benchmark algorithm for solving multi-objective simulation optimization problems on integer lattices.

### Reference
If you use this software for work leading to publications, please cite the article in which R-PERLE and R-MinRLE were proposed:

Cooper K, Hunter SR, Nagaraj K (2018) Bi-objective simulation optimization on integer lattices using the epsilon-constraint method in a retrospective approximation framework.

### Install from source
1. Install Python 3.7+ from https://www.python.org/. You should be able to type `python` and `pip` into the terminal. Depending on your system it may be `python3` and `pip3` instead.
1. Download the project either from  
https://github.rcac.purdue.edu/HunterGroup/pychn/releases   
or using  
`git clone git@github.rcac.purdue.edu:HunterGroup/pychn.git`.
1. Navigate to the project folder you to and build the binary wheel. The packages docopt, numpy should be installed automatically, but we will install them explicitly.  
`pip install wheel numpy docopt`
1. Build the binary wheel.  
`python setup.py bdist_wheel`
1. Install the wheel.  
`pip install dist/pychn-0.1.0-py3-none-any.whl`

### Install from PyPI
*not yet available*  
`pip install pychn`

### Getting started
For a help file containing all the commands and options, type `pychn --h`.

### Command help

Use the listitems command to view a list of available solvers, problems, and
test problems.

Use solve to generate a solution to <problem> using algorithm <solver>.
After specifying any desired options, optionally specify algorithm-specific
parameters and their values. For complex, long-running simulations, specify
the --mp option to take replications in parallel.

Use testsolve to generate a solution to a <tester> test problem using
algorithm <solver>. The listitems command shows which problems have an
associated tester and how to specify the tester. Testers are problems for
which a solution is known and implemented. In addition to the regular run
data, testsolve will generate solution quality metrics against the known
solution. Testsolve can run independent instances of the chosen algorithm
by setting the --trials option. The user may specify both --trails and --mp
but should choose values carefully if doing so.

An experiment is any single invocation of solve or testsolve. Experiments can
be instances of an algorithm run in parallel using independent random numbers
by setting the --trials option. The simulation budget determines how many
simulation replications an algorithm instance uses to generate a solution, and
can be set using --budget. Use --name to assign a name to the experiment. A
directory will be generated with the given name in the working directory. Make
sure the user invoking pychn has write access to the working directory. The
--seed option specifies 6 positive integers used to generate random number
streams used in the experiment. The neighborhood radius specifies the maximum
distance between feasible points such that an compliant algorithm considers
them neighbors. Since algorithms in pychn are integer-ordered, --nr values
less than 1 are trivial. Finally, simulation replications can be taken in
parallel for simulations with non-trival run times using --mp. When using
--trials and --mp, (or both) choose values appropriate for the machine, as
pychn will not adjust them.
