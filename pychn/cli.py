"""
ioboso

Usage:
  ioboso solve <problem> <solver> [--budget=b] [--trials=t] [--name=n] [<param> <val>]...
  ioboso testsolve <tester> <solver> [--budget=b] [--trials=t] [--name=n] [--incr=i] [<param> <val>]...
  ioboso -h | --help
  ioboso --version

Options:
  --budget=b                Simulation budget [default: 50000]
  --trials=t                Number of instances to solve. [default: 1]
  --name=n                  A name to assign to the output. [default: testrun]
  -h --help                 Show this screen.
  --version                 Show version.

Examples:
  ioboso solve ProbTPA RPERLE
  ioboso solve ProbTPB RRLE --budget=100000 --trials=20 --name=tp1bexperiment
  ioboso testsolve TPCTester RMINRLE --budget=10000 --incr=100

Help:
  Use solve to generate a solution to <problem> using algorithm <solver>. Test
  solve is similar but the solution is known in advance so peformance data
  is generated.

  The budget --budget indicate how many simulations of <problem> the algorithm
  <solver> is allowed to run. Trials --trials is the number of times to solve
  the problem using a random starting point and independent random number
  streams.
"""


from inspect import getmembers, isclass

from docopt import docopt

from . import __version__ as VERSION


def main():
    """Main CLI entrypoint."""
    import pychn.commands
    options = docopt(__doc__, version=VERSION)

    # Here we'll try to dynamically match the command the user is trying to run
    # with a pre-defined command class we've already created.
    for (k, v) in options.items():
        if hasattr(pychn.commands, k) and v:
            commod = getattr(pychn.commands, k)
            comclasses = getmembers(commod, isclass)
            comclass = [cmcls[1] for cmcls in comclasses if cmcls[0] != 'BaseComm'][0]
            cominst = comclass(options)
            cominst.run()
