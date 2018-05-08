# iosimopt

This project implements integer-ordered multi-objective simulation-optimization algorithms and a small problem testbed with integrated mrg32k3a pseudo-random number generation for comparison. Features include a full CLI based on docopt, a limited object-oriented API, and plotting via matplotlib.

Present algorithms:
RPERLE, Retrospective - Partitioned Epsilon-constraint with Relaxed Local Enumeration
MO-COMPASS, Multi-objective Convergent Optimization via Most-Promising-Area Stochastic Search

Requirements: Python 3.5+

Installation:
Download the Python wheel file from the releases page and install using pip or pip3.

pip3 install iosimopt-0.0.6-py3-none-any.whl

Installation from source:
In the source directory, build the wheel using

python3 setup.py bdist_wheel

and install using pip as above (it will be in dist directory) or

python3 setup.py install
