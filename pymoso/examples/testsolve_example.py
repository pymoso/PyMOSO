# import the testsolve functions
from pymoso.chnutils import testsolve
# import the module containing RPERLE
import pymoso.solvers.rperle as rp
# import the MyTester class
from mytester import MyTester

# testsolve always requires an x0 positionally, even though it is only
# actually used when ranx0=True is passed (otherwise every independent
# sample path uses this x0 unchanged); MyTester can generate its own
# per sample path via get_ranx0 if you pass ranx0=True below.
x0 = (1, )
run_data = testsolve(MyTester, rp.RPERLE, x0, isp=100, crn=True, radius=2)

iter5_soln = run_data[0][11]['itersoln'][4]
isp12_iter5_metric = MyTester().metric(iter5_soln)
