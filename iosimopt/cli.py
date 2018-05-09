"""
iosimopt

Usage:
  iosimopt solve <problem> <solver> [--budget=b] [--trials=t] [--name=n] [<param> <val>]...
  iosimopt testsolve <tester> <solver> [--budget=b] [--trials=t] [--name=n] [--incr=i] [<param> <val>]...
  iosimopt algcomp <tester> <solver> <solver>... [--budget=b] [--trials=t] [--name=n] [--incr=i]
  iosimopt parcomp <tester> <solver> <param> <val> <val>... [--budget=b] [--trials=t] [--name=n] [--incr=i]
  iosimopt -h | --help
  iosimopt --version

Options:
  --budget=b                Simulation budget [default: 50000]
  --trials=t                Number of instances to solve. [default: 1]
  --name=n                  A name to assign to the output. [default: testrun]
  --incr=i                  Granularity of plotting data. [default: 10000]
  --alg                     Specifies to compare different algorithms.
  --param                   Specifies to compare varying parameters of one algorithm.
  -h --help                 Show this screen.
  --version                 Show version.

Examples:
  iosimopt solve TP1a RPERLE
  iosimopt solve TP1b RRLE --budget=100000 --trials=20 --name=tp1bexperiment
  iosimopt testsolve TP3Tester RPE --budget=10000 --incr=100
  iosimopt algcomp TP1aTester RPERLE MOCOMPASS --budget=1000000
  iosimopt parcomp TP1aTester RPERLE betadel 0.2 0.4 0.6 0.8 --trials=40

Help:
  Use solve to generate a solution to <problem> using algorithm <solver>. Test
  solve is similar but the solution is known in advance so options are available
  to measure and visualize the performanceself.

  The budget --budget indicate how many simulations of <problem> the algorithm
  <solver> is allowed to run. Trials --trials is the number of times to solve
  the problem using a random starting point and independent random number
  streams. Increment --incr corresponds to how many points to generate data for
  when a solution is known (e.g. when using testsolve). --incr should divide
  evenly into --budget.
"""


from inspect import getmembers, isclass

from docopt import docopt

from . import __version__ as VERSION


def main():
    """Main CLI entrypoint."""
    import iosimopt.commands
    options = docopt(__doc__, version=VERSION)

    # Here we'll try to dynamically match the command the user is trying to run
    # with a pre-defined command class we've already created.
    for (k, v) in options.items():
        if hasattr(iosimopt.commands, k) and v:
            commod = getattr(iosimopt.commands, k)
            comclasses = getmembers(commod, isclass)
            comclass = [cmcls[1] for cmcls in comclasses if cmcls[0] != 'BaseComm'][0]
            cominst = comclass(options)
            cominst.run()
