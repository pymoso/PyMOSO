# import the testsolve functions
from pymoso.chnutils import testsolve
# import the module containing RPERLE
import pymoso.solvers.rperle as rp
# import the MyTester class
from mytester import MyTester

# choose a feasible starting point of MyProblem
x0 = (97,)
run_data = testsolve(MyTester, rp.RPERLE, x0, metric=True, isp=16, proc=4)
