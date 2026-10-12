"""
The sync zone lives inside each isp path's own slot, and every
coordinate axis raises at its boundary instead of running into a
neighbour's territory.

Before this file's fix, an Oracle's sync zone began at SYNC_ROLE_OFFSET
= 2**175, measured from that Oracle's own root -- but one isp path's
whole slot is only ISP_STRIDE = 2**159 wide. So path t's sync
coordinates lay 2**16 slots above its own, inside the default zone of
path t + 65,536, and two paths' sync zones coincided wherever their
sync values differed by 2**51. Nothing in tree reached either case, but
independence between paths rested on that arithmetic, not on the
layout. Every test here was observed failing against that layout before
the fix landed (docs/rng-interface-design.md, the SYNC_ROLE_OFFSET/
ISP_STRIDE entry).
"""
import pytest

from pymoso.chnbase import Oracle
from pymoso.chnutils import get_testsolve_prnstreams
from pymoso.prng import mrg32k3a, mrg31k3p, philox4x32
from pymoso.prng import base as prng_base

MRG_FAMILY = [mrg32k3a, mrg31k3p]
ALL_BACKENDS = [mrg32k3a, mrg31k3p, philox4x32]


def _ids(backends):
    return [b.__name__.rsplit(".", 1)[-1] for b in backends]


class SeedRecordingOracle(Oracle):
    """Logs the first value each replication's stream produces -- equal
    exactly when two replications were handed the same stream position,
    and available on every generator (g() is only promised an
    rng-shaped object, not get_seed())."""

    def __init__(self, rng):
        self.num_obj = 1
        self.dim = 1
        self.log = []
        super().__init__(rng)

    def g(self, x, rng):
        self.log.append(rng.random())
        return True, (0.0,)


def _path_oracles(backend, isp, crn=False):
    orcstreams, _, _, _, orc_root = get_testsolve_prnstreams(isp, backend.DEFAULT_SEED, backend)
    orcs = []
    for stream in orcstreams:
        orc = SeedRecordingOracle(stream)
        orc.set_crnflag(crn)
        orc.simpar = 1
        orcs.append(orc)
    return orcs, orc_root


def _slot_width(backend):
    """Streams in one isp path's slot: how far apart consecutive paths'
    own roots are."""
    span = getattr(backend, "ISP_STREAM_SPAN", None)
    if span is not None:
        return span
    return backend.ISP_STRIDE // backend.ITER_STRIDE   # the pre-fix spelling, MRG family


# ---------------------------------------------------------------------------
# Nesting
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("backend", ALL_BACKENDS, ids=_ids(ALL_BACKENDS))
def test_sync_zone_starts_and_ends_inside_the_path_slot(backend):
    assert 0 < backend.SYNC_ZONE_STREAM_START < backend.ISP_STREAM_SPAN
    assert backend.ISP_ITER_MARGIN == backend.SYNC_ZONE_STREAM_START


@pytest.mark.parametrize("backend", ALL_BACKENDS, ids=_ids(ALL_BACKENDS))
@pytest.mark.parametrize("fraction", [0, 1, 7, "stream_boundary", "middle", "last"])
def test_a_sync_hit_stays_inside_its_own_paths_slot(backend, fraction):
    sync = {"stream_boundary": backend.SYNC_PER_STREAM, "middle": backend.SYNC_CAPACITY // 2,
            "last": backend.SYNC_CAPACITY - 1}.get(fraction, fraction)
    (orc,), _ = _path_oracles(backend, 1)
    orc.hit((3,), 2, sync=sync)
    stream, _ = orc.get_high_water_mark()
    assert backend.SYNC_ZONE_STREAM_START <= stream < _slot_width(backend)


@pytest.mark.parametrize("backend", MRG_FAMILY, ids=_ids(MRG_FAMILY))
def test_the_old_cross_path_sync_collision_is_gone(backend):
    """Path 0 at sync=2**51 used to be handed exactly the seed path 1
    got at sync=0. Path 0 must now either refuse that sync value or
    draw from somewhere else."""
    (orc0, orc1), _ = _path_oracles(backend, 2)
    orc1.hit((3,), 1, sync=0)
    try:
        orc0.hit((3,), 1, sync=2 ** 51)
    except ValueError:
        return
    assert orc0.log[-1] != orc1.log[-1]


@pytest.mark.parametrize("backend", ALL_BACKENDS, ids=_ids(ALL_BACKENDS))
def test_two_paths_never_share_a_sync_seed_across_a_battery(backend):
    (orc0, orc1), _ = _path_oracles(backend, 2)
    values = sorted({0, 1, 2, backend.SYNC_PER_STREAM, backend.SYNC_PER_STREAM + 1,
                     backend.SYNC_CAPACITY // 2, backend.SYNC_CAPACITY - 1})
    for orc in (orc0, orc1):
        for sync in values:
            orc.hit((3,), 2, sync=sync)
    assert len(set(orc0.log)) == len(orc0.log) == 2 * len(values)
    assert set(orc0.log).isdisjoint(orc1.log)


# ---------------------------------------------------------------------------
# Boundaries raise; nothing wraps or spills
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("backend", ALL_BACKENDS, ids=_ids(ALL_BACKENDS))
def test_sync_value_past_the_zone_raises(backend):
    (orc,), _ = _path_oracles(backend, 1)
    orc.hit((3,), 1, sync=backend.SYNC_CAPACITY - 1)     # last valid value
    with pytest.raises(prng_base.SyncOverflow):
        orc.hit((3,), 1, sync=backend.SYNC_CAPACITY)
    assert len(orc.log) == 1


@pytest.mark.parametrize("backend", ALL_BACKENDS, ids=_ids(ALL_BACKENDS))
@pytest.mark.parametrize("crn", [False, True])
def test_iteration_past_the_default_zone_raises(backend, crn):
    """The halved iteration headroom is a real ceiling: the last valid
    iteration works, the next one raises rather than drawing from the
    sync zone."""
    (orc,), _ = _path_oracles(backend, 1, crn=crn)
    orc._iteration = backend.ISP_ITER_MARGIN - 1
    orc.hit((3,), 1)
    orc._advance_iteration()
    with pytest.raises(prng_base.IterationOverflow):
        orc.hit((3,), 1)
    assert len(orc.log) == 1


@pytest.mark.parametrize("backend", ALL_BACKENDS, ids=_ids(ALL_BACKENDS))
def test_replication_block_must_fit_entirely_default_branch(backend):
    """offset_within_iteration checks the block's first replication
    index; the block's last one has to fit too."""
    (orc,), _ = _path_oracles(backend, 1)
    x = (3,)
    orc._replications_drawn[(x, 0)] = backend.REPL_COUNT_LIMIT - 1
    orc.hit(x, 1)                                         # exactly the last index
    orc._replications_drawn[(x, 0)] = backend.REPL_COUNT_LIMIT - 1
    with pytest.raises(prng_base.ReplicationOverflow):
        orc.hit(x, 2)
    assert len(orc.log) == 1


@pytest.mark.parametrize("backend", ALL_BACKENDS, ids=_ids(ALL_BACKENDS))
def test_sync_zone_endseed_carry_is_bounded_by_the_slot(backend):
    (orc,), _ = _path_oracles(backend, 1)
    orc._high_water_mark = (backend.ISP_STREAM_SPAN - 2, backend.OFFSET_CAPACITY - 1)
    orc.get_endseed()                                     # carries to the slot's last stream
    orc._high_water_mark = (backend.ISP_STREAM_SPAN - 1, backend.OFFSET_CAPACITY - 1)
    with pytest.raises(prng_base.StreamFamilyExceeded):
        orc.get_endseed()


def test_builtin_sample_size_schedule_cannot_approach_the_iteration_ceiling():
    """mrg32k3a.py's sizing comment: with RASolver's own calc_b/calc_m
    (growth 1.2**nu and 1.1**nu), float overflow ends any run before
    nu=4,000 -- five orders of magnitude under the smallest
    ISP_ITER_MARGIN here. The ceiling exists for solvers that bring
    their own schedule."""
    with pytest.raises(OverflowError):
        1.2 ** 3900
    with pytest.raises(OverflowError):
        1.1 ** 7500
    assert 1.2 ** 3800 > 0 and 1.1 ** 7400 > 0
    for backend in ALL_BACKENDS:
        assert backend.ISP_ITER_MARGIN > 100_000 * 4_000


@pytest.mark.parametrize("backend", ALL_BACKENDS, ids=_ids(ALL_BACKENDS))
@pytest.mark.parametrize("mode", ["crn", "sync"])
def test_replication_block_must_fit_entirely_crn_and_sync_branches(backend, mode):
    """CRN and sync blocks always start at replication 0, so the limit
    is on m itself. Checked without running m replications: the raise
    comes before anything is drawn."""
    (orc,), _ = _path_oracles(backend, 1, crn=(mode == "crn"))
    kwargs = {"sync": 3} if mode == "sync" else {}
    with pytest.raises(prng_base.ReplicationOverflow):
        orc.hit((3,), backend.REPL_COUNT_LIMIT + 1, **kwargs)
    assert orc.log == []


@pytest.mark.parametrize("backend", ALL_BACKENDS, ids=_ids(ALL_BACKENDS))
def test_last_crn_replication_ends_exactly_at_the_streams_capacity(backend):
    """The CRN block's own arithmetic at its far end: replication
    REPL_COUNT_LIMIT-1 starts REPL_STRIDE short of OFFSET_CAPACITY or
    earlier, so a full-size block never leaves its stream."""
    last_start = (backend.REPL_COUNT_LIMIT - 1) * backend.REPL_STRIDE
    assert last_start + backend.REPL_STRIDE <= backend.OFFSET_CAPACITY


def test_philox_strides_are_derived_from_its_own_budget_not_copied_from_mrg():
    assert philox4x32.REPL_STRIDE == philox4x32.OFFSET_CAPACITY // philox4x32.REPL_COUNT_LIMIT
    assert philox4x32.REPL_STRIDE != mrg32k3a.REPL_STRIDE
    assert philox4x32.SYNC_PER_STREAM == 1
