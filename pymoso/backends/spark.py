"""
Run PyMOSO's pooled work on a Spark cluster.

    from pymoso.backends.spark import SparkBackend
    from pymoso.chnutils import testsolve, solve

    backend = SparkBackend(spark)          # the session a notebook already has

    # Independent sample paths, one Spark task each. This is what Spark
    # is good at here: paths are long, independent, and tiny to send.
    results, end_seed = testsolve(MyTester, RPERLE, x0, isp=200, budget=5000, backend=backend)

    # One solve(), its replications spread over the cluster. READ THE
    # WARNING BELOW FIRST.
    solution, end_seed = solve(MyProblem, RPERLE, x0, budget=5000, simpar=16, backend=backend)

Results are identical to the same call without `backend=`: a task
computes its random-number streams from the coordinates it carries,
wherever it runs.

**`solve(simpar=N, backend=...)` is slower than plain `solve()` unless
one replication of your simulation costs roughly 100 ms or more, and
it tops out at a few times faster however large the cluster is.**
Every call a solver makes to the oracle becomes one Spark job, and a
Spark job cost 130-310 ms on the Databricks clusters this was
measured on. Three clusters, RPERLE, `simpar=6`:

    cost of one replication     speedup over plain solve()
    20-28 ms                    0.5x to 1.0x  (slower, or no gain)
    83-112 ms                   1.8x to 2.9x
    0.4-0.5 s                   3.7x to 4.1x
    1.5-1.7 s                   4.0x to 4.7x  (up to 6x at simpar=32)

The ceiling is the solver's, not Spark's: an RA solver asks for a
handful of replications at a time and waits for the answer
(docs/simpar-ceiling.md). `simpar` above about 6 gained nothing
until a replication cost over a second. For a cheap simulation use
`simpar=N` without a backend, or nothing. Nothing in pymoso will tell
you during a run that dispatch is losing: time a short run both ways.
docs/spark-backend.md has the measurements and the design.

What the cluster needs: the same version of pymoso on the executors
as on the driver (checked on every task), the same Python minor
version (Spark requires it), and cloudpickle if any of your classes
are not part of pymoso -- which they are, in practice. On Databricks
install `pymoso[notebook]`, not `pymoso[spark]`: the runtime provides
Spark, and installing PyPI's pyspark over it is not something to do.

What reaches the executors: your problem, tester and solver classes,
by value, with the functions and constants of the module or notebook
that defines them. What does not: modules those classes import (they
must be installed there), files they open, and anything that cannot
be pickled -- in particular the Spark session itself, which a `g()`
cannot use.

A cluster does not change what limits the built-in RA solvers in high
dimension: on the default generator, the cost of positioning each
block's random-number stream (use `generator='philox4x32'`), and a
budget that one RA iteration can overrun many times over
(KNOWN_ISSUES.md issue 16). docs/spark-backend.md, "High dimension".
"""
from .remote import RemoteBackend, run_task
from .. import __version__


class SparkBackend(RemoteBackend):
    """
    A backend that runs each task as one Spark task. See the module
    docstring before using it with `solve()`.

    Parameters
    ----------
    spark : pyspark.sql.SparkSession
        A classic session or a Spark Connect one.

    Notes
    -----
    Built on `spark.range(n, numPartitions=n)` and a plain Python UDF,
    not on `sparkContext.parallelize`. A Spark Connect session has no
    `sparkContext` at all -- no RDDs, no broadcast variables -- and
    Spark Connect is what Databricks serverless and shared-access
    clusters provide (that last from memory, not checked against a
    Databricks runtime; the absence of `sparkContext` under Connect is
    verified in tests/test_spark_backend.py). The DataFrame route is
    the one that exists on both. `range` with as many partitions as
    rows puts exactly one task's index in each partition.

    The tasks' payloads travel inside the UDF's closure, so every task
    receives all of them. They are small -- a sample path is a few
    hundred bytes, a replication block less -- except for
    `par_diff`'s, which carry each path's results.
    """

    def __init__(self, spark):
        super().__init__()
        self.spark = spark

    def dispatch(self, init_payload, payloads):
        from pyspark.sql.functions import udf
        from pyspark.sql.types import BinaryType

        version = __version__

        def run(index):
            return run_task(init_payload, payloads[index], version)

        # useArrow=False: no pandas or pyarrow needed on the executors,
        # and nothing here would gain from them.
        column = udf(run, BinaryType(), useArrow=False)('id').alias('answer')
        count = len(payloads)
        try:
            rows = self.spark.range(count, numPartitions=count).select('id', column).collect()
        except Exception as e:
            raise RuntimeError(
                'the Spark job failed outside PyMOSO\'s own task code, so there is '
                'no task error to report -- see the cause above. The usual reasons: '
                'pymoso is not installed on the executors, or is a version without '
                'pymoso.backends; cloudpickle is not installed there; or the '
                'executors run a different Python minor version from the driver.'
            ) from e
        answers = [None] * count
        for row in rows:
            answers[row['id']] = bytes(row['answer'])
        return answers
