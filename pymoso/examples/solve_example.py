# import the solve function
from pymoso.chnutils import solve
# import the module containing the RPERLE implementation
import pymoso.solvers.rperle as rp
# import MyProblem - myproblem.py should usually be in the script directory
import myproblem as mp

# specify an x0. In MyProblem, it is a tuple of length 1
x0 = (97,)
soln = solve(mp.MyProblem, rp.RPERLE, x0)
print(soln)

# example for specifying budget and seed
budget=10000
seed = (111, 222, 333, 444, 555, 666)
soln1 = solve(mp.MyProblem, rp.RPERLE, x0, budget=budget, seed=seed)

# specify crn and simpar
soln2 = solve(mp.MyProblem, rp.RPERLE, x0, crn=True, simpar=4)

# specify algorithm specific parameters
soln3 = solve(mp.MyProblem, rp.RPERLE, x0, radius=2, betaeps=0.3, betadel=0.4)

# mix them
soln4 = solve(mp.MyProblem, rp.RPERLE, x0, crn=True, seed=seed, radius=5)
