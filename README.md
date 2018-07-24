# pychn

This project implements the R-PERLE algorithm for solving bi-objective simulation optimization problems on integer lattices and the R-MinRLE algorithm, a benchmark algorithm for solving multi-objective simulation optimization problems on integer lattices.

### Reference
If you use this software for work leading to publications, please cite the article in which R-PERLE and R-MinRLE were proposed:

Cooper K, Hunter SR, Nagaraj K (2018) Bi-objective simulation optimization on integer lattices using the epsilon-constraint method in a retrospective approximation framework.

### Build and installation for MacOSX and Linux
You'll need to install the latest Python 3 from https://www.python.org/ and make sure it's in your path.  For the following commands, you'll use `python` or `python3` and `pip` or `pip3` depending on your specific installation. Then download the code and go to the directory containing setup.py.
First, make sure you have wheel installed: `pip3 install wheel` and then build the binary with `python3 setup.py bdist_wheel`.
Since the wheel is universal you can alternatively just download it from https://github.rcac.purdue.edu/HunterGroup/pychn/releases.
Finally, install the wheel using `pip3 install dist/pychn-0.0.7-py3-none-any.whl` but remember to change 0.0.7 to the correct version.

### Getting started
For a help file containing all the commands and options, type `pychn --h`.

More coming soon.
