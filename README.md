# pydovs

This project implements the R-PERLE algorithm for solving bi-objective simulation optimization problems on integer lattices and the R-MinRLE algorithm, a benchmark algorithm for solving multi-objective simulation optimization problems on integer lattices. THIS PROJECT IS IN ALPHA! Please email the authors with any issues.

### Reference
If you use this software for work leading to publications, please cite the article in which R-PERLE and R-MinRLE were proposed:

Cooper K, Hunter SR, Nagaraj K (2018) Bi-objective simulation optimization on integer lattices using the epsilon-constraint method in a retrospective approximation framework. http://www.optimization-online.org/DB_HTML/2018/06/6649.html.

We also include an implementation of R-SPLINE, which can be cited as follows:

Wang, Honggang, et al. “Integer-Ordered Simulation Optimization Using R-SPLINE: Retrospective Search with Piecewise-Linear Interpolation and Neighborhood Enumeration.” ACM Transactions on Modeling and Computer Simulation (TOMACS), vol. 23, no. 3, 2013, pp. 1–24.

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
for the official releases or from  
`git clone git@github.rcac.purdue.edu:HunterGroup/pydovs.git`
for the latest version.  
1. Navigate to the newly downloaded project directory containing setup.py and build the binary wheel.  
`python setup.py bdist_wheel`
1. Install the wheel.  
`pip install dist/pydovs-x.x.x-py3-none-any.whl`  
Replace the x.x.x with the correct file name corresponding to the code version. Modify the command to select the particular wheel you've built or downloaded.

### Getting started
For a help file containing all the commands and options, type `pydovs --h`.

### Command help
```
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

Help:
  Use the listitems command to view a list of available solvers, problems, and
  test problems.
```
