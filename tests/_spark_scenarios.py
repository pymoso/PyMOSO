"""
Driver program for tests/test_spark_backend.py: opens one Spark session,
runs every scenario against it, and prints the outcomes as one line of
JSON.

    python -I tests/_spark_scenarios.py classic|connect

A program of its own, not fixtures in the test module, for two
reasons. A classic session and a Spark Connect session cannot exist in
one process, and both are tested. And a Spark driver holds a JVM and
its own threads, which the test process is better off without.

`classic` is `local-cluster[2,1,1024]`: two executor JVMs separate
from the driver, each starting its own Python workers, in Spark's work
directory. `connect` is a local Spark Connect server. In neither do
the Python workers get this program's `sys.path`, so a module in
tests/ is importable here and not there -- the first scenario checks
that, because the others lean on it.
"""
import json
import os
import pathlib
import sys
import tempfile
import warnings

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import _by_value_classes as mine
import pymoso
from pymoso.backends import remote
from pymoso.backends.spark import SparkBackend
from pymoso.chnbase import Oracle
from pymoso.chnutils import par_diff, solve, testsolve
from pymoso.commands.basecomm import load_user_module
from pymoso.solvers.rperle import RPERLE
from pymoso.testers.tpatester import TPATester
from pymoso.problems.probtpa import ProbTPA

SEED = (12345,) * 6
LIMIT = 50


class MainProblem(Oracle):
    """Defined in `__main__`, as a notebook's classes are."""

    def __init__(self, rng):
        self.num_obj = 2
        self.dim = 2
        super().__init__(rng)

    def g(self, x, rng):
        if not all(-LIMIT <= xi <= LIMIT for xi in x):
            return False, ()
        z = rng.normalvariate(0, 1)
        return True, (x[0] ** 2 + x[1] ** 2 + z, (x[0] - 10) ** 2 + (x[1] - 10) ** 2 + z)


class MainTester:
    def __init__(self):
        self.ranorc = MainProblem

    def metric(self, eles):
        return len(eles)


class MainSolver(RPERLE):
    pass


class RaisingProblem(MainProblem):
    def g(self, x, rng):
        raise ZeroDivisionError('g() failed at x={0}'.format(x))


USER_PROBLEM = """
from pymoso.chnbase import Oracle
from helper import penalty

class UserProblem(Oracle):
    def __init__(self, rng):
        self.num_obj = 2
        self.dim = 2
        super().__init__(rng)
    def g(self, x, rng):
        if not all(-50 <= xi <= 50 for xi in x):
            return False, ()
        z = rng.normalvariate(0, 1)
        return True, (x[0] ** 2 + x[1] ** 2 + z, penalty(x) + z)

class UserTester:
    def __init__(self):
        self.ranorc = UserProblem
"""


def open_session(mode):
    from pyspark.sql import SparkSession
    if mode == 'classic':
        builder = SparkSession.builder.master('local-cluster[2,1,1024]')
    else:
        builder = SparkSession.builder.remote('local[2]')
    return builder.config('spark.ui.enabled', 'false').getOrCreate()


def can_executors_import(spark, name):
    from pyspark.sql.functions import udf
    from pyspark.sql.types import BooleanType

    def probe(_):
        import importlib
        try:
            importlib.import_module(name)
        except ImportError:
            return False
        return True

    rows = spark.range(2, numPartitions=2).select(udf(probe, BooleanType(), useArrow=False)('id').alias('ok')).collect()
    return [row['ok'] for row in rows]


def same(make):
    """Whether `make(backend)` equals `make(None)`."""
    def run(backend):
        return make(backend) == make(None)
    return run


def main(mode):
    spark = open_session(mode)
    out = {'mode': mode, 'session': type(spark).__module__, 'spark': spark.version}
    try:
        try:
            spark.sparkContext
            out['has_spark_context'] = True
        except Exception:
            out['has_spark_context'] = False
        out['executors_import_pymoso'] = can_executors_import(spark, 'pymoso')
        out['executors_import_tests_module'] = can_executors_import(spark, '_by_value_classes')

        def backend():
            return SparkBackend(spark)

        def paths(tester, solver, x0):
            def make(b):
                kwargs = dict(budget=300, seed=SEED, isp=4)
                if b is not None:
                    kwargs['backend'] = b
                return testsolve(tester, solver, x0, **kwargs)
            return make(backend()) == make(None)

        def replications(problem, solver, x0, crn=False):
            def make(b):
                kwargs = dict(budget=120, seed=SEED, crn=crn)
                if b is not None:
                    kwargs.update(simpar=3, backend=b)
                return solve(problem, solver, x0, **kwargs)
            return make(backend()) == make(None)

        with warnings.catch_warnings():
            warnings.simplefilter('ignore', remote.SlowDispatchWarning)
            out['paths_builtin'] = paths(TPATester, RPERLE, (40, 40))
            out['paths_main'] = paths(MainTester, MainSolver, (20, 20))
            out['paths_driver_only_module'] = paths(mine.DriverOnlyTester, mine.DriverOnlySolver, (20, 20))
            out['replications_builtin'] = replications(ProbTPA, RPERLE, (40, 40))
            out['replications_builtin_crn'] = replications(ProbTPA, RPERLE, (40, 40), crn=True)
            out['replications_main'] = replications(MainProblem, MainSolver, (20, 20))
            out['replications_driver_only_module'] = replications(mine.DriverOnlyProblem, RPERLE, (20, 20))

            with tempfile.TemporaryDirectory() as directory:
                with open(os.path.join(directory, 'userproblem.py'), 'w') as f:
                    f.write(USER_PROBLEM)
                with open(os.path.join(directory, 'helper.py'), 'w') as f:
                    f.write('def penalty(x):\n    return (x[0] - 10) ** 2 + (x[1] - 10) ** 2\n')
                user = load_user_module('pymoso.problems.userproblem', os.path.join(directory, 'userproblem.py'))
                out['paths_user_files'] = paths(user.UserTester, RPERLE, (20, 20))
                out['replications_user_files'] = replications(user.UserProblem, RPERLE, (20, 20))

            res, _ = testsolve(MainTester, MainSolver, (20, 20), budget=300, seed=SEED, isp=3)
            out['metrics'] = par_diff(res, MainTester(), 1, backend=backend()) == par_diff(res, MainTester(), 1)

            def failure(run):
                try:
                    run()
                except Exception as e:
                    chain, link = [], e
                    while link is not None:
                        chain.append(type(link).__name__)
                        link = link.__cause__ or link.__context__
                    return [type(e).__name__, str(e), chain]
                return None

            out['raising_serial'] = failure(lambda: solve(RaisingProblem, RPERLE, (20, 20), budget=100, seed=SEED))
            out['raising_spark'] = failure(
                lambda: solve(RaisingProblem, RPERLE, (20, 20), budget=100, seed=SEED, simpar=2, backend=backend()))

            stale = backend()
            sent = pymoso.backends.spark.__version__
            pymoso.backends.spark.__version__ = '0.0.0-not-this-one'
            try:
                out['version_mismatch'] = failure(
                    lambda: testsolve(TPATester, RPERLE, (40, 40), budget=100, seed=SEED, isp=2, backend=stale))
            finally:
                pymoso.backends.spark.__version__ = sent

        chatty = backend()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            solve(ProbTPA, RPERLE, (40, 40), budget=150, seed=SEED, simpar=3, backend=chatty)
        out['cheap_replications_warned'] = [w.category.__name__ for w in caught if issubclass(w.category, remote.SlowDispatchWarning)]
        out['cheap_replications_jobs'] = chatty.jobs
        out['cheap_replications_ms_per_job'] = round(chatty.dispatch_seconds / chatty.jobs * 1e3, 1)
    finally:
        spark.stop()
    print('PYMOSO-SPARK-SCENARIOS ' + json.dumps(out))


if __name__ == '__main__':
    main(sys.argv[1])
