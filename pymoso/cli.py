"""
pymoso

Command-line interface for solving MOSO problems (`solve`), testing MOSO
algorithms (`testsolve`), and listing the solvers/problems/testers bundled
with PyMOSO (`listitems`).

Run `pymoso --help` for the top-level command list, or e.g.
`pymoso solve --help` for a specific command's options.
"""

import argparse
from inspect import getmembers, isclass
from . import __version__ as VERSION
from .prng import registry


EPILOG = """
Examples:
  pymoso listitems
  pymoso solve ProbTPA RPERLE 4 14
  pymoso solve --budget=100000 --odir=test1  ProbTPB RMINRLE 3 12
  pymoso solve --seed 12345,32123,5322,2,9543,666666666 ProbTPC RPERLE 5 5 5
  pymoso solve --simpar=4 --param betaeps 0.4 ProbTPA RPERLE 30 30
  pymoso solve --param radius 3 ProbTPA RPERLE 45 45
  pymoso testsolve --isp=16 --proc=4 TPATester RPERLE
  pymoso testsolve --isp=20 --proc=10 --metric --crn TPBTester RMINRLE 9 9

Help:
  Use the listitems command to view a list of available solvers, problems, and
  test problems.
"""


def positive_int(value):
    """
    argparse type= validator: accept only positive integers. Used for
    --budget/--simpar/--isp/--proc so a non-positive process/replication
    count is rejected at the CLI boundary instead of reaching mp.Pool
    (which raises an opaque error for a non-positive process count) or
    another downstream crash. Replaces the separate
    basecomm.validate_positive_int check from commit 82c177b.

    Parameters
    ----------
    value : str

    Returns
    -------
    int
    """
    try:
        ivalue = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError('invalid int value: {0!r}'.format(value))
    if ivalue < 1:
        raise argparse.ArgumentTypeError('must be a positive integer, got {0}'.format(ivalue))
    return ivalue


def _add_common_options(subp):
    """Options shared by solve and testsolve."""
    subp.add_argument('--budget', type=positive_int, default=200,
                       help='Set the simulation budget [default: 200]')
    subp.add_argument('--odir', default='testrun',
                       help='Set the output file directory name. [default: testrun]')
    subp.add_argument('--crn', action='store_true',
                       help='Set if common random numbers are desired. Only mrg32k3a and '
                            'mrg31k3p support --crn; philox4x32 does not (see --generator).')
    # §3.7/§12 step 6b: one comma-separated token, not nargs='+' -- an
    # unbounded nargs='+' greedily consumes every following argv token,
    # including the required <problem>/<solver>/<x> positionals,
    # whenever --seed precedes them (confirmed directly: "pymoso solve
    # --seed 1 2 3 4 5 6 ProbTPA RPERLE 4 14" failed parsing entirely
    # under nargs='+', the exact form this project's own examples have
    # always used). A single token can never swallow a neighboring
    # positional regardless of position, so --seed stays order-
    # independent like every other option. Arity is still generator-
    # specific (6 integers for the MRG family, 2 for philox4x32), and
    # argparse parses before --generator's own selection is known, so
    # it cannot validate arity itself -- the selected generator's own
    # validate_seed does that, once selection resolves (commands/
    # solve.py, commands/testsolve.py) -- a bad --seed still fails
    # before any simulation work starts, just not inside argparse.
    subp.add_argument('--seed', metavar='<s>',
                       help='Set the random number seed, as comma-separated integers with no '
                            'spaces -- 6 for mrg32k3a/mrg31k3p, 2 for philox4x32 (see '
                            '--generator), e.g. --seed 12345,32123,5322,2,9543,666666666. '
                            'Arity and content are validated against whichever generator is '
                            'selected.')
    subp.add_argument('--generator', choices=sorted(registry.GENERATORS), default=registry.DEFAULT_GENERATOR,
                       help='Set the pseudo-random number generator [default: {0}]. Only '
                            'mrg32k3a and mrg31k3p support --crn; philox4x32 does not (its own '
                            'CRN mechanism does not exist yet -- see '
                            'docs/rng-interface-design.md).'.format(registry.DEFAULT_GENERATOR))
    subp.add_argument('--param', nargs=2, action='append', metavar=('<param>', '<val>'),
                       help='Specify a solver-specific parameter <param> <val>. Repeatable.')


def build_parser():
    """
    Build the pymoso argument parser: subparsers for listitems, solve,
    and testsolve, preserving the invocation syntax of the previous
    docopt-based CLI (see docs/ for the characterization this was
    checked against).
    """
    parser = argparse.ArgumentParser(
        prog='pymoso',
        description=__doc__.strip().splitlines()[0],
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('-v', '--version', action='version', version=VERSION)

    subparsers = parser.add_subparsers(dest='command', required=True, metavar='<command>')

    subparsers.add_parser('listitems', help='List the built-in solvers, problems, and testers.')

    solve_p = subparsers.add_parser('solve', help='Solve a MOSO problem.')
    _add_common_options(solve_p)
    solve_p.add_argument('--simpar', type=positive_int, default=1,
                          help='Set number of parallel processes for simulation replications. [default: 1]')
    solve_p.add_argument('problem', metavar='<problem>')
    solve_p.add_argument('solver', metavar='<solver>')
    solve_p.add_argument('x', metavar='<x>', nargs='+')

    testsolve_p = subparsers.add_parser('testsolve', help='Test a MOSO algorithm on a MOSO problem.')
    _add_common_options(testsolve_p)
    testsolve_p.add_argument('--isp', type=positive_int, default=1,
                              help='Set number of algorithm instances to solve. [default: 1]')
    testsolve_p.add_argument('--proc', type=positive_int, default=1,
                              help='Set number of parallel processes for the algorithm instances. [default: 1]')
    testsolve_p.add_argument('--metric', action='store_true',
                              help='Set if metric computation is desired.')
    testsolve_p.add_argument('tester', metavar='<tester>')
    testsolve_p.add_argument('solver', metavar='<solver>')
    testsolve_p.add_argument('x', metavar='<x>', nargs='*')

    return parser


def _options_for_solve(args):
    """
    Translate argparse's Namespace into the same dict shape
    commands/solve.py already expects (unchanged from the docopt era),
    so that module needs no changes beyond dropping its now-redundant
    int()/validate_positive_int() calls.
    """
    param = args.param or []
    return {
        '--budget': args.budget,
        '--odir': args.odir,
        '--crn': args.crn,
        '--simpar': args.simpar,
        '--generator': args.generator,
        '--seed': args.seed is not None,
        '<s>': args.seed.split(',') if args.seed is not None else [],
        '<problem>': args.problem,
        '<solver>': args.solver,
        '<x>': args.x,
        '<param>': [p[0] for p in param],
        '<val>': [p[1] for p in param],
    }


def _options_for_testsolve(args):
    """Same as _options_for_solve, for commands/testsolve.py."""
    param = args.param or []
    return {
        '--budget': args.budget,
        '--odir': args.odir,
        '--crn': args.crn,
        '--isp': args.isp,
        '--proc': args.proc,
        '--metric': args.metric,
        '--generator': args.generator,
        '--seed': args.seed is not None,
        '<s>': args.seed.split(',') if args.seed is not None else [],
        '<tester>': args.tester,
        '<solver>': args.solver,
        '<x>': args.x,
        '<param>': [p[0] for p in param],
        '<val>': [p[1] for p in param],
    }


def main():
    """
    Main CLI entrypoint.
    """
    from . import commands

    parser = build_parser()
    args = parser.parse_args()

    if args.command == 'solve':
        options = _options_for_solve(args)
    elif args.command == 'testsolve':
        options = _options_for_testsolve(args)
    else:
        options = {}

    commod = getattr(commands, args.command)
    comclasses = getmembers(commod, isclass)
    comclass = [cmcls[1] for cmcls in comclasses if cmcls[0] != 'BaseComm' and issubclass(cmcls[1], commands.basecomm.BaseComm)][0]
    cominst = comclass(options)
    cominst.run()
