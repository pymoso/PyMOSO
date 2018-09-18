# pydovs

This project implements the R-PERLE algorithm for solving bi-objective simulation optimization problems on integer lattices and the R-MinRLE algorithm, a benchmark algorithm for solving multi-objective simulation optimization problems on integer lattices.

### Reference
If you use this software for work leading to publications, please cite the article in which R-PERLE and R-MinRLE were proposed:

Cooper K, Hunter SR, Nagaraj K (2018) Bi-objective simulation optimization on integer lattices using the epsilon-constraint method in a retrospective approximation framework. http://www.optimization-online.org/DB_HTML/2018/06/6649.html.

### Install from source
1. Install Python 3.4+ from https://www.python.org/. You should be able to type `python` and `pip` into the terminal. Depending on your system it may be `python3` and `pip3` instead.  If you are using the `python3` command, the command to upgrade pip is  
`pip3 intall --upgrade pip`  
1. Download the project either from  
https://github.rcac.purdue.edu/HunterGroup/pydovs/releases   
or using  
`git clone git@github.rcac.purdue.edu:HunterGroup/pychn.git`.  
From the link, you may download the .whl file and skip to the last step.  
1. The packages docopt, numpy should be installed automatically in step 4, but we will install them explicitly.   
`pip install wheel numpy docopt`  
1. Navigate to the newly downloaded project directory containing setup.py and build the binary wheel.  
`python setup.py bdist_wheel`
1. Install the wheel.  
`pip install dist/pydovs-0.1.8-py3-none-any.whl`  
The exact name of the file may be different. Modify the command to select the particular wheel you've built or downloaded.

### Install experimental version from git
`pip install git+https://github.rcac.purdue.edu/HunterGroup/pydovs.git`  

### Getting started
For a help file containing all the commands and options, type `pydovs --h`.

### Command help
'''
pydovs

Usage:
  pydovs listitems
  pydovs solve [--budget=B] [--odir=D] [--radius=R] [--simpar=P]
    [(--seed <s> <s> <s> <s> <s> <s>)] [(--params <param> <val>)]...
    <problem> <solver> <x>...
  pydovs testsolve [--budget=B] [--odir=D] [--radius=R] [--isp=T] [--proc=Q]
    [--haus] [--gran=G] [(--seed <s> <s> <s> <s> <s> <s>)]
    [(--params <param> <val>)]... <tester> <solver> <x>...
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
  --gran=G                  Number of points at which to compare to the true solution. [default: 5]
  --haus                    Indicates whether to compute Hausdorf distance metrics [default: True]
  -h --help                 Show this screen.
  -v --version              Show version.

Examples:
  pydovs listitems
  pydovs solve ProbTPA RPERLE 4 14
  pydovs solve --budget=100000 --odir=test1 --radius=3 ProbTPB RMINRLE 3 12
  pydovs solve --seed 12345 32123 5322 2 9543 666666666 ProbTPC RPERLE 31 21 11
  pydovs solve --parsim --proc=4 --params betaeps 0.4 ProbTPA RPERLE 30 30
  pydovs solve --params betaeps 0.7 --params betadel 0.5 ProbTPA RPERLE 45 45

Help:
  Use the listitems command to view a list of available solvers, problems, and
  test problems.

  Use solve to generate a solution to <problem> using algorithm <solver>.
  After specifying any desired options, optionally specify algorithm-specific
  parameters and their values. For complex, long-running simulations, specify
  the --mp option to take replications in parallel. Specify the starting
  feasible point <x> as a sequence of spaced integers.

  Use testsolve to generate a solution to a <tester> test problem using
  algorithm <solver>. The listitems command shows which problems have an
  associated tester and how to specify the tester. Testers are problems for
  which a solution is known and implemented. In addition to the regular run
  data, testsolve will generate solution quality metrics against the known
  solution. Testsolve can run independent instances of the chosen algorithm
  by setting the --isp option and run them in parallel by specifying the --proc
  option. The granularity of comparison points is specified using the --gran
  option. For example, if the budget is 10,000 and the granularity is 10, then
  the estimated solution will be compared to the real solution at 1000, 2000,
  ..., and 10,000 simulations. Assuming an appropriate metric, we expect a
  convergent algorithm's estimated solutions to get closer to the known solution
  as the number of simulations increases. Available metrics and their
  suitability are described in the user manual.

  The simulation budget determines how many simulation replications an algorithm
  instance uses to generate a solution, and can be set using --budget. Use
  odir to assign a name to the experiment. A directory will be generated with
  the given name in the working directory. Make sure the user invoking pydovs has
  write access to the working directory. The --seed option requires 6 positive
  integers used as a seed to the mrg32k3a random generator and seeds the
  streams used by pydovs. The neighborhood radius specifies the maximum
  distance between feasible points such that an compliant algorithm considers
  them neighbors. Since algorithms in pydovs are integer-ordered, --radius values
  less than 1 are trivial.
'''
