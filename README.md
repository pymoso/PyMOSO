# pychn

This project implements the R-PERLE algorithm for solving bi-objective simulation optimization problems on integer lattices and the R-MinRLE algorithm, a benchmark algorithm for solving multi-objective simulation optimization problems on integer lattices.

### Reference
If you use this software for work leading to publications, please cite the article in which R-PERLE and R-MinRLE were proposed:

Cooper K, Hunter SR, Nagaraj K (2018) Bi-objective simulation optimization on integer lattices using the epsilon-constraint method in a retrospective approximation framework.

### Install from source
1. Install Python 3.7+ from https://www.python.org/. You should be able to type `python` and `pip` into the terminal. Depending on your system it may be `python3` and `pip3` instead.
1. Download the project either from https://github.rcac.purdue.edu/HunterGroup/pychn/releases or using
 `git clone git@github.rcac.purdue.edu:HunterGroup/pychn.git`.
1. Navigate to the project folder you to and build the binary wheel. The packages docopt, numpy should be installed automatically, but we will install them explicitly.
`pip install wheel numpy docopt`
`python setup.py bdist_wheel`
1. Install the wheel.
`pip install dist/pychn-0.1.0-py3-none-any.whl`

### Install from PyPI
*not yet available*
`pip install pychn`

### Getting started
For a help file containing all the commands and options, type `pychn --h`.

More coming soon.
