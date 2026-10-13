"""
Measure what dispatching costs, when asked.

    from pymoso import dispatch_cost
    from pymoso.backends.spark import SparkBackend

    print(dispatch_cost(MyProblem, (30, 30), replications=8, parts=8,
                        backend=SparkBackend(spark)))

runs one request for replications twice over -- in this process, and
as tasks on the backend -- and reports how long each took.

**What it measures, and what it does not.**

- *One request.* `replications` replications of the one point `x`,
  sent as `parts` tasks in one job. A solver makes many requests, most
  of them a handful of replications (docs/simpar-ceiling.md), and
  waits for each. A whole `solve()` does worse than a large
  `replications` here suggests. To learn what a `solve()` will do,
  measure a request the size your solver makes, or time a short
  `solve()` with and without `backend=`.
- *In place means here.* The first timing is this process on this
  machine, which is what `solve()` without a backend would use. The
  workers may be faster or slower machines; that difference is part
  of what is being measured, not an error in it.
- *Wall time on both sides.* Nothing is measured on the workers, so
  tasks slowing each other down shows up as a slower job, where it
  belongs, and not as extra work done.
- *The first job apart.* It pays for whatever the backend had not yet
  started or loaded, and is reported separately from the rest.
- *This point.* If a replication's cost depends on `x`, so does the
  answer.

**What it costs.** The request is run `jobs + 2` times in all: once in
place, once as the first job, and `jobs` more. That is real
simulation, which is why it happens only when this is called.

It gives numbers. It does not say whether to use the backend: that
depends on what the time is worth, and that is not something this
function knows.
"""
import statistics
import time
from dataclasses import dataclass

from ..executor import ClassHandle, InProcessHandle, PoolExecutor, ReplicationBlock, SerialExecutor
from ..prng import registry


@dataclass(frozen=True)
class DispatchCost:
    """
    What `dispatch_cost` measured. Times are wall-clock seconds, as
    seen from the calling process.

    Attributes
    ----------
    x : tuple
    replications : int
        In the one request that was measured.
    parts : int
        Tasks the request was divided into on the backend, at most.
    backend : str
        The backend's class name.
    in_place_seconds : float
        The request run in the calling process.
    first_job_seconds : float
        The request's first run on the backend.
    job_seconds : tuple of float
        Its later runs on the backend, in order.
    identical : bool
        Whether every run on the backend returned exactly what the run
        in place returned. Anything but True is a defect in the
        backend or a simulation that is not a function of its stream.
    """
    x: tuple
    replications: int
    parts: int
    backend: str
    in_place_seconds: float
    first_job_seconds: float
    job_seconds: tuple
    identical: bool

    @property
    def per_replication_seconds(self):
        """`in_place_seconds` over `replications`."""
        return self.in_place_seconds / self.replications

    @property
    def median_job_seconds(self):
        return statistics.median(self.job_seconds)

    @property
    def ratio(self):
        """`in_place_seconds` over `median_job_seconds`: how many
        times longer the request took in place than as a job."""
        return self.in_place_seconds / self.median_job_seconds

    def __str__(self):
        return (
            '{0} replications of x={1} as one request\n'
            'in place, in this process: {2:.4f} s ({3:.2f} ms per replication)\n'
            'as up to {4} tasks on {5}: first job {6:.4f} s; next {7}: median {8:.4f} s (min {9:.4f}, max {10:.4f})\n'
            'in place / median job: {11:.2f}; results identical: {12}'
        ).format(
            self.replications, self.x, self.in_place_seconds, self.per_replication_seconds * 1e3,
            self.parts, self.backend, self.first_job_seconds, len(self.job_seconds),
            self.median_job_seconds, min(self.job_seconds), max(self.job_seconds),
            self.ratio, 'yes' if self.identical else 'NO',
        )


def dispatch_cost(problem, x, *, replications, parts, backend, jobs=5, generator=registry.DEFAULT_GENERATOR):
    """
    Time one request for replications in place and on a backend. See
    the module docstring for what that does and does not tell you.

    Parameters
    ----------
    problem : chnbase.Oracle class
    x : sequence of int
        The point to simulate.
    replications : int
        How many replications the request carries. No default: it is
        a statement about what your solver asks for.
    parts : int
        How many tasks to divide it into on the backend, as `simpar`
        would. No default.
    backend : backend
        Where the tasks run (`pool.LocalBackend` describes what a
        backend is). No default.
    jobs : int
        Runs on the backend after the first. Default 5.
    generator : str
        A registered generator name.

    Returns
    -------
    DispatchCost
        `print()` it for a four-line report.

    Raises
    ------
    ValueError
        `replications`, `parts` or `jobs` is less than 1, or the
        problem class cannot be sent to the backend
        (`executor.ClassRef`).
    """
    for name, value in (('replications', replications), ('parts', parts), ('jobs', jobs)):
        if value < 1:
            raise ValueError('{0} must be at least 1, got {1}'.format(name, value))
    mod = registry.get_generator(generator)
    x = tuple(x)
    stream = mod.stream_at(mod.DEFAULT_SEED, 0, 0)
    block = ReplicationBlock(x, stream.root_seed(), 1, 0, mod.REPL_RESERVE_STRIDE, replications)
    handle = ClassHandle(problem, remote=getattr(backend, 'remote', False))

    def timed(executor):
        started = time.perf_counter()
        result = executor.run([block])
        return time.perf_counter() - started, result

    with SerialExecutor().open(InProcessHandle(problem(stream)), generator) as executor:
        in_place_seconds, expected = timed(executor)
    with PoolExecutor(parts, backend=backend).open(handle, generator) as executor:
        first_job_seconds, result = timed(executor)
        identical = result == expected
        job_seconds = []
        for _ in range(jobs):
            seconds, result = timed(executor)
            job_seconds.append(seconds)
            identical = identical and result == expected
    return DispatchCost(
        x=x, replications=replications, parts=parts, backend=type(backend).__name__,
        in_place_seconds=in_place_seconds, first_job_seconds=first_job_seconds,
        job_seconds=tuple(job_seconds), identical=identical,
    )
