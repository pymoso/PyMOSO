"""
The default and description of every parameter a built-in solver
declares in PARAMS, for the README's "Table of Algorithm-Specific
Parameters".

PARAMS holds names only. Which parameters exist and which solvers take
each are read from the solvers themselves (chnbase.accepted_params);
what the code cannot say -- a sentence of description, and the default
written the way a user types it -- is kept here, and
tests/test_readme_param_table.py holds it to the code: the keys must
be exactly the parameters the solvers declare, and each default must
be the one every solver taking it really uses. REQUIRED marks a
parameter a solver refuses to run without.

Rows appear in the README in this order.
"""
REQUIRED = object()

PARAM_DOCS = {
    'mconst': (2, 'Initialize the sample size and subsequent schedule of sample sizes.'),
    'bconst': (8, 'Initialize the search sampling limit and subsequent schedule of limits.'),
    'radius': (1, "Sets radius that determines a point's neighborhood."),
    'bestimprove': (0, 'Set to 1 to search the whole neighborhood for its best point, rather than move to the first improving one.'),
    'betadel': (0.5, 'Roughly, affects how likely it is for RLE to keep its given solution.'),
    'betaeps': (0.5, 'Roughly, affects how likely PE will perform a search from a point.'),
    'lb': (REQUIRED, "Lower bound each feasible point's components may take."),
    'ub': (REQUIRED, "Upper bound each feasible point's components may take."),
    'numsamples': (8, 'Number of feasible points to sample per iteration.'),
    'subregions': (2, 'Number of subregions to branch each region into.'),
    'alpha': (0.05, 'Overall confidence parameter.'),
    'delta': (0.1, 'Sampling ratio used for subregion elimination.'),
    'R0': (20, 'Initial number of replications taken per point.'),
}
