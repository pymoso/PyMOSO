# import the testsolve functions
from pychn.chnutils import testsolve
# import the module containing RPERLE
import pychn.solvers.rperle as rp
# import the MyTester class
from mytester import MyTester

# choose a feasible starting point of MyProblem
x0 = (-97,)
run_data = testsolve(MyTester, rp.RPERLE, x0)
print(run_data)
