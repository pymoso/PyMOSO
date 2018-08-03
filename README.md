# pychn

This project implements the R-PERLE algorithm for solving bi-objective simulation optimization problems on integer lattices and the R-MinRLE algorithm, a benchmark algorithm for solving multi-objective simulation optimization problems on integer lattices.

### Reference
If you use this software for work leading to publications, please cite the article in which R-PERLE and R-MinRLE were proposed:

Cooper K, Hunter SR, Nagaraj K (2018) Bi-objective simulation optimization on integer lattices using the epsilon-constraint method in a retrospective approximation framework. http://www.optimization-online.org/DB_HTML/2018/06/6649.html.

### Install from source
1. Install Python 3.7+ from https://www.python.org/. You should be able to type `python` and `pip` into the terminal. Depending on your system it may be `python3` and `pip3` instead.  If you are using the `python3` command, the command to upgrade pip is  
`pip3 intall --upgrade pip`  
1. Download the project either from  
https://github.rcac.purdue.edu/HunterGroup/pychn/releases   
or using  
`git clone git@github.rcac.purdue.edu:HunterGroup/pychn.git`.  
From the link, you may download the .whl file and skip to the last step.  
1. The packages docopt, numpy should be installed automatically in step 4, but we will install them explicitly.   
`pip install wheel numpy docopt`  
1. Navigate to the newly downloaded project directory containing setup.py and build the binary wheel.  
`python setup.py bdist_wheel`
1. Install the wheel.  
`pip install dist/pychn-0.1.0-py3-none-any.whl`  
The exact name of the file may be different. Modify the command to select the particular wheel you've built or downloaded.

### Install from PyPI
*not yet available*  
`pip install pychn`

### Getting started
For a help file containing all the commands and options, type `pychn --h`.

### Command help
```
pychn

Usage:
  pychn listitems
  pychn solve [--budget=B] [--name=N] [--radius=R] [(--parsim --proc=Q)]
            [(--seed <s> <s> <s> <s> <s> <s>)] [(--params <param> <val>)]...
            <problem> <solver> <x>...
  pychn -h | --help
  pychn -v | --version

Options:
  --budget=B                Simulation budget [default: 50000]
  --x0                      Specify a feasible point as spaced integers.
  --isp=T                   Number of independent sample paths of the algorithm to solve. [default: 1]
  --name=N                  A name to assign to the output. [default: testrun]
  --seed                    Specify a seed by entering 6 spaced integers > 0.
  --radius=R                Specify a neighborhood radius. [default: 1]
  --parsim                  Run simulations in parallel if proc is specified. [default: 1]
  --proc=Q                  Total number of processes to make available to pychn. [default: 1]
  --params                  Allows specifying param val pairs.
  -h --help                 Show this screen.
  -v --version              Show version.

Examples:
  pychn solve ProbTPA RPERLE 4 14
  pychn solve --budget=100000 --name=test1 --radius=3 ProbTPB RMINRLE 3 12
  pychn solve --seed 12345 32123 5322 2 9543 666666666 ProbTPC RPERLE 31 21 11
  pychn solve --parsim --proc=4 --params betaeps 0.4 ProbTPA RPERLE 30 30
  pychn solve --params betaeps 0.7 --params betadel 0.5 ProbTPA RPERLE 45 45

Help:
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
  by setting the --isp option. The user may specify both --trails and --mp
  but should choose values carefully if doing so.

  An experiment is any single invocation of solve or testsolve. Experiments can
  be instances of an algorithm run in parallel using independent random numbers
  by setting the --isp option. The simulation budget determines how many
  simulation replications an algorithm instance uses to generate a solution, and
  can be set using --budget. Use --name to assign a name to the experiment. A
  directory will be generated with the given name in the working directory. Make
  sure the user invoking pychn has write access to the working directory. The
  -seed option specifies 6 positive integers used to generate random number
  streams used in the experiment. The neighborhood radius specifies the maximum
  distance between feasible points such that an compliant algorithm considers
  them neighbors. Since algorithms in pychn are integer-ordered, --nr values
  less than 1 are trivial. Finally, simulation replications can be taken in
  parallel for simulations with non-trival run times using --mp. When using
  --isp and --mp, (or both) choose values appropriate for the machine, as
  pychn will not adjust them.
```
