"""
pymoso

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
  --simpar=P                Set number of parallel processes for simulation replications. [default: 1]
  --isp=T                   Set number of algorithm instances to solve. [default: 1]
  --proc=Q                  Set number of parallel processes for the algorithm instances. [default: 1]
  --metric                  Set if metric computation is desired.
  --seed                    Set the random number seed with 6 spaced integers.
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
"""


from inspect import getmembers, isclass

from docopt import docopt

from . import __version__ as VERSION


def main():
    """Main CLI entrypoint."""
    from . import commands
    options = docopt(__doc__, version=VERSION)
    for (k, v) in options.items():
        if hasattr(commands, k) and v:
            commod = getattr(commands, k)
            comclasses = getmembers(commod, isclass)
            comclass = [cmcls[1] for cmcls in comclasses if cmcls[0] != 'BaseComm' and issubclass(cmcls[1], commands.basecomm.BaseComm)][0]
            cominst = comclass(options)
            cominst.run()
