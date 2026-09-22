"""Display all solvers, problems, and test problems"""

from .basecomm import *
import textwrap
from inspect import getdoc, getmembers, isclass

# plus your existing imports of problems, solvers, testers, and BaseComm

DESC_WIDTH = 60
GAP = '  '


def _summary(cls):
    """Return the first paragraph of a class docstring, joined into one line."""
    doc = getdoc(cls)
    if not doc:
        return ''
    first_paragraph = doc.split('\n\n', 1)[0]
    return ' '.join(first_paragraph.split())


def _print_table(headers, rows, widths):
    """Print an aligned table, wrapping the description (second) column."""
    def fmt(cells):
        return GAP.join(f'{c:{w}}' for c, w in zip(cells, widths)).rstrip()

    print()
    print(fmt(headers))
    print(fmt(['*' * w for w in widths]))
    for row in rows:
        lines = textwrap.wrap(row[1], widths[1]) or ['']
        for i, line in enumerate(lines):
            cells = list(row) if i == 0 else [''] * len(row)
            cells[1] = line
            print(fmt(cells))


class ListItems(BaseComm):
    """
    Implements the CLI command listitems.

    See also
    --------
    BaseComm
    """
    def run(self):
        """
        Print the list of solvers, problems, and testers that are
        included in PyMOSO.
        """
        solvclasses = getmembers(solvers, isclass)
        probclasses = getmembers(problems, isclass)
        testclasses = getmembers(testers, isclass)

        # map each oracle class to the first tester (alphabetically) that
        # targets exactly that class, not a parent of it
        tested_by = {}
        for tname, tcls in testclasses:
            tested_by.setdefault(tcls().ranorc, tname)

        tester_header = 'Test Name (if available)'
        name_width = max(len(name) for name, _ in solvclasses + probclasses)
        name_width = max(name_width, len('Problems'))
        tester_width = max([len(tester_header)] + [len(t) for t in tested_by.values()])

        solver_rows = [(name, _summary(cls)) for name, cls in solvclasses]
        _print_table(('Solver', 'Description'), solver_rows,
                     (name_width, DESC_WIDTH))

        problem_rows = [(name, _summary(cls), tested_by.get(cls, ''))
                        for name, cls in probclasses]
        _print_table(('Problems', 'Description', tester_header), problem_rows,
                     (name_width, DESC_WIDTH, tester_width))
