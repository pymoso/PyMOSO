'''
Example code snippets useful when implementing algorithms in PyMOSO,
for use in RLESolver/RASolver-derived solvers. They form one
continuous narrative sharing variables (x, nbors, sorted_feas, xmin,
nondom) across sub-sections, meant to be read and copied in order into
a solver method body -- 'self' below is a live RASolver/RLESolver
instance mid-iteration, not defined in this file itself.

Four fixes relative to the original README snippets, since each would
fail (or silently misbehave) if run exactly as first written:
- "Find Neighbors and Take Simulation Replications" used an undefined
  x0 where the running example has x (the point estimated in "Take
  Simulation Replications at a Point"); fixed to x.
- "Select the Minimizer and its Value" computed fxmin = self.gbar[x]
  right after xmin = sorted_feas[0] -- self.gbar[x] does not fail (x
  is still in scope from the earlier section), so this ran without
  error but silently returned x's own value rather than the minimizer
  just found, contrary to the section title. Fixed to self.gbar[xmin].
- "Find the Non-Dominated Points in a Dictionary" imported from
  chnutils instead of pymoso.chnutils (raises ModuleNotFoundError).
- "Randomly Select Points in a Set" always sampled 5 points, but the
  number of non-dominated points depends on the oracle/starting
  point/search trajectory and can be fewer than 5 -- raising
  ValueError. Fixed to min(5, len(nondom)).
'''

##### Take Simulation Replications at a Point
from pymoso.chnutils import get_nbors
# pretend x has not yet been visited in this RA iteration and is feasible
x = (1, 1, 1)

# self.m is the sample size of the current RA iteration
m = self.m
# self.num_calls is the cumulative number of simulations used till now
start_num_calls = self.num_calls
# use estimate to sample x and put results in self.gbar and self.sehat
isfeas, fx, se = self.estimate(x)
calls_used = self.num_calls - start_num_calls
print(m == calls_used) # True
print(fx == self.gbar[x]) # True
print(se == self.sehat[x]) # True

# estimate will not simulate again in subsequent visits to a point
start_num_calls = self.num_calls
isfeas, fx, se = self.estimate(x)
calls_used = self.num_calls - start_num_calls
print(calls_used == 0) # True

##### Find Neighbors and Take Simulation Replications
# neighborhood radiuss
r = self.nbor_rad
nbors = get_nbors(x, r)
self.upsample(nbors)
for n in nbors:
  print(n in self.gbar) # True if n feasible else False

# upsample also returns the feasible subset
nbors = self.upsample(nbors)

##### Argsort a Dictionary of Points
# 0 index for first objective
sorted_feas = sorted(nbors | {x}, key=lambda t: self.gbar[t][0])

##### Select the Minimizer and its Value
xmin = sorted_feas[0]
fxmin = self.gbar[xmin]

##### Use SPLINE to Retrive a Local Minimizer
# no constraints and minimize the 2nd objective
x0 = (2, 2, 2)
isfeas, fx, sex = self.estimate(x0)
# the suppressed value is the set visited along SPLINE's trajectory
_, xmin, fxmin, sexmin = self.spline(x0, float('inf'), 1, 0)
print(self.gbar[xmin] == fxmin) # True

##### Find the Non-Dominated Points in a Dictionary
from pymoso.chnutils import get_nondom
nondom = get_nondom(self.gbar)

##### Randomly Select Points in a Set
solver_rng = self.sprn
# pick up to 5 points -- returns a list, not a set.
ran_pts = solver_rng.sample(list(nondom), min(5, len(nondom)))
one_in_five = solver_rng.choice(ran_pts)
