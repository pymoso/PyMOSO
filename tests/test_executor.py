"""
The executor interface (pymoso/executor.py): work as data, problems as
handles, one lifecycle -- and a serial backend that reproduces what
Oracle.hit() did inline before it existed.

What these tests pin is the contract a second backend will have to
meet, stated against the serial one: a replication's outcome is a
function of its problem, point and coordinate, and of nothing else.
"""
import dataclasses
import multiprocessing
import pickle
import sys

import pytest

from pymoso import executor as ex
from pymoso.chnbase import Oracle
from pymoso.executor import (
    ClassHandle, ClassRef, Executor, InProcessHandle, PoolExecutor, ProblemHandle, Replication,
    ReplicationBlock, SerialExecutor, split_blocks,
)
from pymoso.prng import base as prng_base
from pymoso.prng import mrg32k3a, mrg31k3p, philox4x32
from pymoso.problems.probtpa import ProbTPA
from pymoso.solvers.rperle import RPERLE
from pymoso.testers.tpatester import TPATester

import _executor_problems as problems

ALL = [("mrg32k3a", mrg32k3a), ("mrg31k3p", mrg31k3p), ("philox4x32", philox4x32)]
generators = pytest.mark.parametrize("name,backend", ALL, ids=[n for n, _ in ALL])


class FirstDraw(Oracle):
    """g() returns, and logs, the first value of the stream it is
    handed: equal exactly when two replications start at the same
    position."""

    def __init__(self, rng):
        self.num_obj = 1
        self.dim = 1
        self.log = []
        super().__init__(rng)

    def g(self, x, rng):
        u = rng.random()
        self.log.append((x, u))
        return True, (u,)


def _first(backend, root, stream, offset):
    return prng_base.ensure_random_compatible(backend.stream_at(root, stream, offset)).random()


def _oracle(backend, crn=False):
    orc = FirstDraw(backend.stream_at(backend.DEFAULT_SEED, 0, 0))
    orc.set_crnflag(crn)
    orc.simpar = 1
    return orc


def _root(backend):
    return backend.stream_at(backend.DEFAULT_SEED, 0, 0).root_seed()


# ---------------------------------------------------------------------------
# Work is data
# ---------------------------------------------------------------------------

def test_a_block_is_immutable_picklable_plain_data():
    block = ReplicationBlock(x=(3, 4), root=(1, 2, 3, 4, 5, 6), stream=7, offset=1 << 60, stride=1 << 14, count=5)
    assert pickle.loads(pickle.dumps(block)) == block
    with pytest.raises(dataclasses.FrozenInstanceError):
        block.count = 6
    assert all(isinstance(v, (int, tuple)) for v in dataclasses.astuple(block))


@generators
def test_each_replication_draws_at_root_stream_offset_plus_i_strides(name, backend):
    orc = _oracle(backend)
    root = _root(backend)
    block = ReplicationBlock(x=(9,), root=root, stream=3, offset=5 * backend.REPL_RESERVE_STRIDE,
                             stride=backend.REPL_RESERVE_STRIDE, count=4)
    with SerialExecutor().open(InProcessHandle(orc), name) as executor:
        (results,) = executor.run([block])
    expected = [_first(backend, root, 3, block.offset + i * block.stride) for i in range(4)]
    assert [r.objectives[0] for r in results] == expected
    assert all(isinstance(r, Replication) and r.isfeas and r.raw_consumed >= 1 for r in results)
    assert [x for x, _ in orc.log] == [(9,)] * 4


@generators
def test_results_do_not_depend_on_grouping_or_order_of_blocks(name, backend):
    """The property cross-hit batching rests on."""
    root = _root(backend)
    stride = backend.REPL_RESERVE_STRIDE
    blocks = [ReplicationBlock((i,), root, s, off * stride, stride, n)
              for i, (s, off, n) in enumerate([(0, 0, 3), (0, 100, 2), (2, 7, 4), (1, 0, 1), (0, 50, 3)])]

    def objectives(results):
        return [[r.objectives for r in one] for one in results]

    with SerialExecutor().open(InProcessHandle(_oracle(backend)), name) as executor:
        together = objectives(executor.run(blocks))
    with SerialExecutor().open(InProcessHandle(_oracle(backend)), name) as executor:
        one_at_a_time = [objectives(executor.run([b]))[0] for b in blocks]
    with SerialExecutor().open(InProcessHandle(_oracle(backend)), name) as executor:
        backwards = objectives(executor.run(blocks[::-1]))[::-1]
    assert together == one_at_a_time == backwards
    flat = [o for block in together for o in block]
    assert len(set(flat)) == len(flat)


def test_run_returns_one_list_per_block_in_order_and_handles_no_blocks():
    root = _root(mrg32k3a)
    with SerialExecutor().open(InProcessHandle(_oracle(mrg32k3a)), "mrg32k3a") as executor:
        assert executor.run([]) == []
        results = executor.run([ReplicationBlock((1,), root, 0, 0, 1 << 14, 2),
                                ReplicationBlock((2,), root, 0, 1 << 20, 1 << 14, 5)])
    assert [len(r) for r in results] == [2, 5]


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

def test_lifecycle_open_run_close():
    executor = SerialExecutor()
    block = ReplicationBlock((1,), _root(mrg32k3a), 0, 0, 1 << 14, 1)
    with pytest.raises(RuntimeError):
        executor.run([block])                                   # not open
    executor.close()                                            # closing a closed executor is fine
    assert executor.open(InProcessHandle(_oracle(mrg32k3a)), "mrg32k3a") is executor
    with pytest.raises(RuntimeError):
        executor.open(InProcessHandle(_oracle(mrg32k3a)), "mrg32k3a")   # already open
    assert len(executor.run([block])[0]) == 1
    executor.close()
    executor.close()
    with pytest.raises(RuntimeError):
        executor.run([block])
    executor.open(InProcessHandle(_oracle(mrg32k3a)), "mrg32k3a")       # reusable after close
    executor.close()


def test_context_manager_closes_even_when_the_block_raises():
    class Boom(FirstDraw):
        def g(self, x, rng):
            raise ZeroDivisionError("boom")

    executor = SerialExecutor()
    block = ReplicationBlock((1,), _root(mrg32k3a), 0, 0, 1 << 14, 1)
    with pytest.raises(ZeroDivisionError, match="boom"):        # the exception itself, in the caller
        with executor.open(InProcessHandle(Boom(mrg32k3a.MRG32k3a(mrg32k3a.DEFAULT_SEED))), "mrg32k3a"):
            executor.run([block])
    with pytest.raises(RuntimeError):
        executor.run([block])                                   # closed by the with-block


def test_unknown_generator_is_refused_at_open():
    with pytest.raises(KeyError):
        SerialExecutor().open(InProcessHandle(_oracle(mrg32k3a)), "not-a-generator")


def test_serial_executor_implements_the_interface():
    assert issubclass(SerialExecutor, Executor)
    for method in ("open", "run", "close", "__enter__", "__exit__"):
        assert callable(getattr(SerialExecutor, method))


# ---------------------------------------------------------------------------
# The draw reserve is the block's stride, on every backend
# ---------------------------------------------------------------------------

def test_a_replication_that_overdraws_its_stride_raises_before_the_next_one_runs():
    class Greedy(FirstDraw):
        def g(self, x, rng):
            for _ in range(9):
                rng.random()
            self.log.append(x)
            return True, (0.0,)

    orc = Greedy(mrg32k3a.MRG32k3a(mrg32k3a.DEFAULT_SEED))
    root = _root(mrg32k3a)
    with SerialExecutor().open(InProcessHandle(orc), "mrg32k3a") as executor:
        executor.run([ReplicationBlock((1,), root, 0, 0, 9, 2)])            # exactly its reserve: fine
        assert len(orc.log) == 2
        with pytest.raises(prng_base.ReplicationDrawOverflow):
            executor.run([ReplicationBlock((1,), root, 0, 0, 8, 2)])
    assert len(orc.log) == 3                                    # stopped after the first overdrawn replication


# ---------------------------------------------------------------------------
# The base-stream cache
# ---------------------------------------------------------------------------

def test_one_full_jump_per_stream_serves_every_block_on_it(monkeypatch):
    calls = []
    real = mrg32k3a.stream_at
    monkeypatch.setattr(mrg32k3a, "stream_at", lambda seed, stream, offset: (calls.append((stream, offset)), real(seed, stream, offset))[1])
    root = _root(mrg32k3a)
    orc = _oracle(mrg32k3a)
    calls.clear()
    with SerialExecutor().open(InProcessHandle(orc), "mrg32k3a") as executor:
        for off in (0, 3, 9, 0):
            executor.run([ReplicationBlock((1,), root, 5, off * (1 << 14), 1 << 14, 2)])
        assert calls == [(5, 0)]
        executor.run([ReplicationBlock((1,), root, 6, 0, 1 << 14, 1)])
        executor.run([ReplicationBlock((1,), root, 5, 0, 1 << 14, 1)])     # still cached
        assert calls == [(5, 0), (6, 0)]


def test_the_cache_is_bounded():
    root = _root(mrg32k3a)
    with SerialExecutor().open(InProcessHandle(_oracle(mrg32k3a)), "mrg32k3a") as executor:
        for stream in range(20):
            executor.run([ReplicationBlock((1,), root, stream, 0, 1 << 14, 1)])
        assert len(executor._bases) == SerialExecutor._BASE_CACHE_SIZE


@generators
def test_a_cached_base_stream_is_never_drawn_from(name, backend):
    """Two identical blocks give identical draws: nothing run earlier
    moved the stream the second one started from."""
    root = _root(backend)
    block = ReplicationBlock((1,), root, 2, 0, backend.REPL_STRIDE, 3)
    with SerialExecutor().open(InProcessHandle(_oracle(backend)), name) as executor:
        first = executor.run([block])
        second = executor.run([block])
    assert first == second


# ---------------------------------------------------------------------------
# Problem handles
# ---------------------------------------------------------------------------

def test_in_process_handle_calls_the_live_instance_and_is_not_transportable():
    orc = _oracle(mrg32k3a)
    handle = InProcessHandle(orc)
    assert isinstance(handle, ProblemHandle) and handle.transportable is False
    with SerialExecutor().open(handle, "mrg32k3a") as executor:
        executor.run([ReplicationBlock((1,), _root(mrg32k3a), 0, 0, 1 << 14, 2)])
        orc.g = lambda x, rng: (False, ("replaced",))           # looked up at call time
        (again,) = executor.run([ReplicationBlock((1,), _root(mrg32k3a), 0, 0, 1 << 14, 1)])
    assert len(orc.log) == 2
    assert again[0].isfeas is False and again[0].objectives == ("replaced",)


@generators
def test_class_handle_gives_the_same_results_as_the_live_instance(name, backend):
    """A stateless problem simulated from its class (a fresh instance
    per replication, as a worker would) matches the same blocks run
    against a live instance -- and the handle survives pickling."""
    root = _root(backend)
    blocks = [ReplicationBlock((40, 40), root, 0, 0, backend.REPL_RESERVE_STRIDE, 3),
              ReplicationBlock((12, 7), root, 1, 9 * backend.REPL_RESERVE_STRIDE, backend.REPL_RESERVE_STRIDE, 2)]
    live = ProbTPA(backend.stream_at(backend.DEFAULT_SEED, 0, 0))
    live.set_crnflag(False)
    with SerialExecutor().open(InProcessHandle(live), name) as executor:
        expected = executor.run(blocks)
    handle = pickle.loads(pickle.dumps(ClassHandle(ProbTPA)))
    assert handle.transportable is True and handle.load() is ProbTPA
    with SerialExecutor().open(handle, name) as executor:
        assert executor.run(blocks) == expected


def test_class_handle_refuses_a_class_with_no_source(monkeypatch):
    monkeypatch.setitem(sys.modules, 'cloudpickle', None)       # as where the `notebook` extra is not installed
    namespace = {}
    exec("from pymoso.chnbase import Oracle\nclass Interactive(Oracle):\n    pass\n", namespace)
    with pytest.raises(ValueError, match="no locatable source") as refused:
        ClassHandle(namespace["Interactive"])
    assert "pymoso[notebook]" in str(refused.value)


def test_transport_functions_are_no_longer_importable_from_chnbase():
    """They were, from Phase 2 until Phase 5, as a leftover of having
    been written there. Removed deliberately; pymoso.executor is where
    they are."""
    from pymoso import chnbase
    assert not hasattr(chnbase, "build_transport_descriptor")
    assert not hasattr(chnbase, "reconstruct_transport_descriptor")


# ---------------------------------------------------------------------------
# Oracle.hit() goes through it
# ---------------------------------------------------------------------------

@generators
@pytest.mark.parametrize("mode", ["default", "crn", "sync", "visit"])
def test_hit_describes_its_work_as_one_block_and_runs_it_on_the_executor(name, backend, mode, monkeypatch):
    seen = []
    real_run = SerialExecutor.run
    monkeypatch.setattr(SerialExecutor, "run", lambda self, blocks: (seen.append(list(blocks)), real_run(self, blocks))[1])
    orc = _oracle(backend, crn=(mode == "crn"))
    kwargs = {"sync": {"sync": 3}, "visit": {"visit": 2}}.get(mode, {})
    orc.hit((5,), 4, **kwargs)
    assert len(seen) == 1 and len(seen[0]) == 1
    block = seen[0][0]
    assert (block.x, block.root, block.count) == ((5,), orc._orc_root, 4)
    expected = [_first(backend, block.root, block.stream, block.offset + i * block.stride) for i in range(4)]
    assert [u for _, u in orc.log] == expected
    assert block.stride == (backend.REPL_RESERVE_STRIDE if mode in ("default", "visit") else backend.REPL_STRIDE)


def test_an_oracle_stays_picklable_after_it_has_run_something():
    """testsolve() pickles Oracles into workers; one that has already
    opened its executor must still pickle."""
    orc = ProbTPA(mrg32k3a.MRG32k3a(mrg32k3a.DEFAULT_SEED))
    orc.set_crnflag(False)
    orc.simpar = 1
    before = orc.hit((40, 40), 3)
    clone = pickle.loads(pickle.dumps(orc))
    assert clone.hit((40, 41), 2) == orc.hit((40, 41), 2)
    assert before[0] is True


def test_mp_cleanup_closes_the_executor_and_a_later_hit_reopens_it():
    orc = _oracle(mrg32k3a)
    orc.hit((1,), 1)
    first = orc._executor
    assert first is not None
    orc.mp_cleanup()
    assert orc._executor is None
    orc.hit((2,), 1)
    assert orc._executor is not None and orc._executor is not first


# ---------------------------------------------------------------------------
# Classes in transportable form
# ---------------------------------------------------------------------------

def test_a_class_ref_carries_any_importable_class_and_survives_pickling():
    for cls in (ProbTPA, RPERLE, TPATester):
        ref = pickle.loads(pickle.dumps(ClassRef(cls)))
        assert ref.load() is cls and ref.name == cls.__name__


def test_a_class_defined_inside_a_function_is_refused_before_any_worker_exists(monkeypatch):
    """It has a source file, so the older check let it through; under
    fork it would even work. It cannot be found again by name. (With
    cloudpickle it travels by value: test_by_value_transport.py.)"""
    monkeypatch.setitem(sys.modules, 'cloudpickle', None)       # as where the `notebook` extra is not installed
    def make():
        class Local(Oracle):
            pass
        return Local

    with pytest.raises(ValueError, match="cannot be sent to a worker process"):
        ClassRef(make())
    with pytest.raises(ValueError, match="cannot be sent to a worker process"):
        ClassHandle(make())


# ---------------------------------------------------------------------------
# Splitting blocks into chunks of replications
# ---------------------------------------------------------------------------

def _replications(blocks):
    """Every replication of `blocks` as (x, stream, offset), in order."""
    return [(b.x, b.stream, b.offset + i * b.stride) for b in blocks for i in range(b.count)]


@pytest.mark.parametrize("counts", [[5], [1], [3, 4], [1, 1, 1, 1, 1, 1, 1], [7, 1, 2], [2, 9, 1, 1, 6]])
@pytest.mark.parametrize("parts", [1, 2, 3, 4, 6, 50])
def test_split_blocks_is_the_same_replications_in_even_chunks(counts, parts):
    root = _root(mrg32k3a)
    blocks = [ReplicationBlock((i,), root, i % 2, 1000 * i, 16, n) for i, n in enumerate(counts)]
    chunks, owners = split_blocks(blocks, parts)
    total = sum(counts)
    assert len(chunks) == min(parts, total)
    assert _replications([piece for chunk in chunks for piece in chunk]) == _replications(blocks)
    sizes = [sum(piece.count for piece in chunk) for chunk in chunks]
    assert max(sizes) - min(sizes) <= 1 and all(piece.count >= 1 for chunk in chunks for piece in chunk)
    for chunk, owner in zip(chunks, owners):
        assert [piece.x for piece in chunk] == [blocks[i].x for i in owner]


def test_split_blocks_of_nothing_is_nothing():
    assert split_blocks([], 4) == ([], [])


# ---------------------------------------------------------------------------
# The pool backend meets the serial backend's contract
# ---------------------------------------------------------------------------

pool_pytestmark = pytest.mark.timeout(120)
start_methods = pytest.mark.parametrize("method", multiprocessing.get_all_start_methods())


def _pool(workers, method):
    return PoolExecutor(workers, context=multiprocessing.get_context(method))


@pool_pytestmark
@start_methods
@generators
def test_pool_results_equal_serial_results_for_any_worker_count(name, backend, method):
    root = _root(backend)
    stride, wide = backend.REPL_RESERVE_STRIDE, backend.REPL_STRIDE
    blocks = [ReplicationBlock((40, 40), root, 0, 0, stride, 5),
              ReplicationBlock((12, 7), root, 1, 9 * stride, stride, 1),
              ReplicationBlock((3, 3), root, 2, 0, wide, 7),              # a CRN-shaped block
              ReplicationBlock((4, 4), root, 2, 0, wide, 7),
              ReplicationBlock((40, 41), root, 0, 77 * stride, stride, 3)]
    with SerialExecutor().open(ClassHandle(ProbTPA), name) as executor:
        expected = executor.run(blocks)
    for workers in (1, 2, 5):
        with _pool(workers, method).open(ClassHandle(ProbTPA), name) as executor:
            assert executor.run(blocks) == expected
            assert executor.run(blocks[::-1]) == expected[::-1]
            assert executor.run([]) == []
            assert [executor.run([b])[0] for b in blocks] == expected


@pool_pytestmark
def test_pool_lifecycle_and_refusals():
    executor = PoolExecutor(2)
    block = ReplicationBlock((40, 40), _root(mrg32k3a), 0, 0, 1 << 14, 2)
    with pytest.raises(RuntimeError):
        executor.run([block])
    executor.close()
    with pytest.raises(TypeError, match="cannot be sent to another process"):
        executor.open(InProcessHandle(_oracle(mrg32k3a)), "mrg32k3a")
    with pytest.raises(KeyError):
        executor.open(ClassHandle(ProbTPA), "not-a-generator")
    assert executor.open(ClassHandle(ProbTPA), "mrg32k3a") is executor
    with pytest.raises(RuntimeError):
        executor.open(ClassHandle(ProbTPA), "mrg32k3a")
    assert len(executor.run([block])[0]) == 2
    executor.close()
    executor.close()
    with pytest.raises(RuntimeError):
        executor.run([block])
    with pytest.raises(ValueError):
        PoolExecutor(0)
    assert issubclass(PoolExecutor, Executor)


@pool_pytestmark
@start_methods
def test_an_exception_in_g_is_raised_in_the_caller_as_itself_not_a_hang(method):
    """KNOWN_ISSUES.md issue 15, at the executor."""
    root = _root(mrg32k3a)
    fine = ReplicationBlock((1,), root, 0, 0, 1 << 14, 4)
    bad = ReplicationBlock((13,), root, 0, 1 << 20, 1 << 14, 4)
    with _pool(2, method).open(ClassHandle(problems.RaisesAtThirteen), "mrg32k3a") as executor:
        with pytest.raises(ZeroDivisionError, match=r"boom at \(13,\)"):
            executor.run([fine, bad, fine])
        assert len(executor.run([fine])[0]) == 4        # and the executor still works


@pool_pytestmark
@start_methods
def test_the_draw_reserve_is_enforced_in_the_worker(method):
    """The mechanism this replaced could not check it under --simpar."""
    root = _root(mrg32k3a)
    with _pool(2, method).open(ClassHandle(problems.DrawsNine), "mrg32k3a") as executor:
        assert len(executor.run([ReplicationBlock((1,), root, 0, 0, 9, 4)])[0]) == 4
        with pytest.raises(prng_base.ReplicationDrawOverflow):
            executor.run([ReplicationBlock((1,), root, 0, 0, 8, 4)])


@pool_pytestmark
@start_methods
def test_a_problem_that_cannot_be_loaded_in_a_worker_fails_at_open(method):
    """KNOWN_ISSUES.md issue 7's failure class: the worker cannot build
    the problem. It has to be an error at open, not a hang at the first
    replication."""
    handle = ClassHandle(ProbTPA)
    handle._ref.descriptor = {"files": {"broken": "import a_module_that_does_not_exist\n"},
                              "entry": "broken", "class_name": "Nothing"}
    with pytest.raises(ImportError, match="Could not resolve import order"):
        _pool(2, method).open(handle, "mrg32k3a")


# ---------------------------------------------------------------------------
# Oracle.set_simpar selects the backend
# ---------------------------------------------------------------------------

@pool_pytestmark
@generators
@pytest.mark.parametrize("crn", [False, True])
def test_hit_under_simpar_equals_hit_serially(name, backend, crn):
    def run(simpar):
        orc = ProbTPA(backend.stream_at(backend.DEFAULT_SEED, 0, 0))
        orc.set_crnflag(crn)
        with orc.set_simpar(simpar):
            out = [orc.hit((40, 40), 5), orc.hit((41, 40), 1), orc.hit((40, 40), 3), orc.hit((7, 9), 4, sync=2)]
            return out, orc.get_endseed()
    assert run(3) == run(1)


@pool_pytestmark
def test_set_simpar_owns_its_workers_on_every_exit_path():
    orc = ProbTPA(mrg32k3a.MRG32k3a(mrg32k3a.DEFAULT_SEED))
    orc.set_crnflag(False)
    with pytest.raises(KeyError):
        with orc.set_simpar(2):
            orc.hit((40, 40), 2)
            processes = [w.process for w in orc._executor._pool._workers]
            assert len(processes) == 2 and all(p.is_alive() for p in processes)
            raise KeyError("leaving")
    assert orc._executor is None
    assert not any(p.is_alive() for p in processes)
    orc.set_simpar(2)
    orc.hit((40, 40), 2)
    processes = [w.process for w in orc._executor._pool._workers]
    orc.mp_cleanup()
    assert not any(p.is_alive() for p in processes)
    clone = pickle.loads(pickle.dumps(orc))             # no processes travel with a copy
    assert clone._executor is None


def test_set_simpar_refuses_an_untransportable_class_before_starting_anything(monkeypatch):
    monkeypatch.setitem(sys.modules, 'cloudpickle', None)       # as where the `notebook` extra is not installed
    namespace = {}
    exec("from pymoso.chnbase import Oracle\nclass Interactive(Oracle):\n    pass\n", namespace)
    orc = namespace["Interactive"](mrg32k3a.MRG32k3a(mrg32k3a.DEFAULT_SEED))
    with pytest.raises(ValueError, match="no locatable source"):
        orc.set_simpar(2)
    orc.set_simpar(1)                                   # serially it is fine
