# import the testsolve functions
from pymoso.chnutils import testsolve
# import the module containing RPERLE
import pymoso.solvers.rperle as rp
# import the MyTester class
from mytester import MyTester

# testsolve needs a "dummy" x0 even if MyTester will generate them
x0 = (1, )
run_data = testsolve(MyTester, rp.RPERLE, x0, isp=100, crn=True, radius=2)

iter5_soln = run_data[11]['itersoln'][4]
isp12_iter5_metric = MyTester.metric(iter5_soln)
