#!/usr/bin/env python
"""
Lay a run's pseudo-random streams out from its seed.

A run has roles -- an oracle, a solver, and for `testsolve` a starting
point and one of each per independent sample path -- and every role
gets a stream of its own, computed from the seed and the role's
position. `Oracle` does the same one level down, for the replications
within its own stream. `pymoso.chnutils` offers each of these under
its own name.

Listing
--------------
get_testsolve_prnstreams
get_path_prnstreams
get_solv_prnstreams
check_role_draws
"""
from .prng import registry
from .prng.base import one_past, ensure_random_compatible, IspOverflow, RoleDrawOverflow


def get_testsolve_prnstreams(num_trials, iseed, backend):
    """
    Create the set of random number stream generators with which to test
    a MOSO algorithm.

    Parameters
    ----------
    num_trials : int
        Number of independent sample paths of Oracles to test an
        algorithm
    iseed : tuple of int
        Starting seed from which to create the generators, in the
        selected `backend`'s own shape (§3.7)
    backend : module
        The selected generator's own module (registry.get_generator),
        §12 step 6b -- was hardcoded to pymoso.prng.mrg32k3a before
        this step.

    Returns
    -------
    orcprn_lst : list of Stream objects
        Unwrapped -- each becomes a path's own Oracle.rng, and
        Oracle.set_crnflag()'s own backend_for_stream lookup needs the
        real backend instance.
    solprn_lst : list of random.Random
        Each wrapped with ensure_random_compatible if not already one
        -- handed to a path's solver as `sprn`/`solvprn` (§3.6).
    xprn : random.Random
        Wrapped with ensure_random_compatible if not already one --
        handed to a tester's own get_ranx0(rng) (§3.6).
    iseed : tuple of int
        The reservation-based "next isp slot" seed -- kept for callers
        that only need a cheap, always-available independent seed and
        don't need it to reflect actual consumption. testsolve()'s own
        reported endseed no longer uses this value as of docs/rng-
        interface-design.md §12 step 8 stage 2 -- it's recomputed from
        each path's real high-water mark after solving, using orc_root
        below.
    orc_root : tuple of int
        The oracle role's own root seed, shared across every path
        (path t's own root is `stream_at(orc_root, t*ISP_STREAM_SPAN, 0)`,
        §12 step 6c -- the same position `jump_seed_n(orc_root,
        t*ISP_STRIDE)` always reached).
        Exposed so a caller can combine per-path high-water marks
        (Oracle.get_high_water_mark()) into one real endseed after
        solving -- see testsolve()'s own use of this.

    Notes
    -----
    Each path's oracle stream is computed directly from `isp` via
    ISP_STRIDE (docs/rng-interface-design.md §6/§12 step 4b) -- no
    per-path reservation walk (formerly MAX_RI-sized) exists to overrun,
    so deriving path 5's stream costs the same O(log(index)) matrix-
    power work whether path 5 is requested first, last, or alone,
    regardless of how many iterations any other path used.

    Layout, in whole streams from `iseed` (KNOWN_ISSUES.md issue 10):

    - slot 0, stream 0: the x0 stream;
    - slot 0, stream 1 + t: path t's solver stream;
    - slot t + 1: path t's oracle slot (ISP_STREAM_SPAN streams --
      iterations below ISP_ITER_MARGIN, the sync zone above).

    No role's streams depend on `num_trials`, so path t is the same run
    whether 10 paths are requested or 1,000. Each zone has a boundary
    that raises: `num_trials` past the generator's own ISP_MAX_PATHS
    (IspOverflow, here); a solver or x0 stream drawing more than one
    stream holds (RoleDrawOverflow, check_role_draws); and the oracle
    slot's own iteration/sync/replication limits (oracle.py).

    Raises
    ------
    IspOverflow
    """
    # Checked before anything is built: past ISP_MAX_PATHS the solver
    # zone (slot 0) or the generator's own stream capacity is exhausted.
    if num_trials > backend.ISP_MAX_PATHS:
        raise IspOverflow(
            '{0} independent sample paths requested, but the stream '
            'layout holds at most {1} under {2}. See KNOWN_ISSUES.md '
            'issue 10.'.format(num_trials, backend.ISP_MAX_PATHS, registry.GENERATOR_NAMES[backend])
        )
    root = iseed
    span = backend.ISP_STREAM_SPAN
    # Slot 0, stream 0: the x0 role. ensure_random_compatible: xprn is
    # handed straight to a tester's own get_ranx0(rng) (§3.6, "an
    # rng-shaped object") -- every built-in tester's get_ranx0 calls
    # rng.choice(...), which a raw Philox stream doesn't have.
    xprn = ensure_random_compatible(backend.stream_at(root, 0, 0))
    # Slot 0, streams 1..num_trials: the solver role, one stream per
    # path. Built by stepping one stream at a time from the root (a
    # cached jump for the MRG family) -- the same positions
    # stream_at(root, 1 + t, 0) names, without a full jump from the root
    # per path. Each list entry is wrapped for solver code (MOCOMPASS/
    # MOPBnB's own sprn.sample(...) calls, §3.6); the chain itself uses
    # the unwrapped stream's root_seed().
    solprn_lst = []
    step_seed = root
    for t in range(num_trials):
        solprn = backend.stream_at(step_seed, 1, 0)
        step_seed = solprn.root_seed()
        solprn_lst.append(ensure_random_compatible(solprn))
    # Slots 1..num_trials: the oracle role, path t in slot t + 1. Its
    # root is a fixed position -- the start of slot 1 -- not "wherever
    # the last solver stream ended up", which is what made path 0's
    # oracle stream coincide with the last path's solver stream, and
    # what made every path's oracle streams move whenever num_trials
    # changed (KNOWN_ISSUES.md issue 10, both parts).
    orc_root = backend.stream_at(root, span, 0).root_seed()
    orcprn_lst = [backend.stream_at(orc_root, t * span, 0) for t in range(num_trials)]
    # The next independent stream past every path actually reserved:
    # the start of the slot path `num_trials` would own.
    iseed = backend.stream_at(orc_root, num_trials * span, 0).root_seed()
    return orcprn_lst, solprn_lst, xprn, iseed, orc_root


def _testsolve_roots(num_trials, iseed, backend):
    """
    What testsolve() itself needs from the stream layout
    (get_testsolve_prnstreams documents it): the x0 stream and the
    oracle role's root. Each path's own two streams are built where the
    path runs (get_path_prnstreams).

    Returns
    -------
    xprn : random.Random
    orc_root : tuple of int

    Raises
    ------
    IspOverflow
    """
    if num_trials > backend.ISP_MAX_PATHS:
        raise IspOverflow(
            '{0} independent sample paths requested, but the stream '
            'layout holds at most {1} under {2}. See KNOWN_ISSUES.md '
            'issue 10.'.format(num_trials, backend.ISP_MAX_PATHS, registry.GENERATOR_NAMES[backend])
        )
    xprn = ensure_random_compatible(backend.stream_at(iseed, 0, 0))
    orc_root = backend.stream_at(iseed, backend.ISP_STREAM_SPAN, 0).root_seed()
    return xprn, orc_root

def _testsolve_endseed(res, isp, orc_root, backend):
    """
    The end seed of a `testsolve` run: one past the furthest position
    any of its sample paths' oracles reached.

    Parameters
    ----------
    res : dict
        {path int : that path's result dict}, as `run_paths` returns.
        Only `'oracle_high_water_mark'` is read.
    isp : int
        The number of sample paths.
    orc_root : tuple of int
        The seed the paths' oracle streams are laid out from
        (`_testsolve_roots`).
    backend : module
        The selected generator's own module.

    Returns
    -------
    tuple of int
        `orc_root` itself if no path's oracle was touched.
    """
    # docs/rng-interface-design.md §12 step 8 stage 2 / §12 step 6c: the
    # real endseed, aggregated across every isp path's own oracle-role
    # high-water mark (crossing the --proc worker boundary via each
    # path's own result dict -- see Oracle.get_high_water_mark()'s
    # docstring for why a dict field: under --proc the Oracle that ran
    # a path lived in a worker and never existed in this process).
    #
    # Path t's own Oracle stream is relative to `orc_root + t*ISP_STRIDE`
    # (get_testsolve_prnstreams's own construction); since
    # ISP_STRIDE == ISP_STREAM_SPAN*ITER_STRIDE exactly, path t's own
    # (oracle_stream, oracle_offset) composes additively into the shared
    # root's own stream units: t*ISP_STREAM_SPAN + oracle_stream,
    # oracle_offset unchanged -- the same composition Oracle.get_endseed()
    # itself relies on, one level up. Reduces to exactly the same flat
    # value the pre-split code computed (t*ISP_STRIDE + oracle_flat), so
    # this is a relabeling here too, not new arithmetic.
    #
    # The "+1 with carry" (base.one_past) happens once, at the very end,
    # against the *winning* path's own raw oracle_stream/family capacity
    # -- not against the combined value -- for the same reason
    # Oracle.get_endseed() itself carries against its own local stream:
    # the family boundary (ISP_ITER_MARGIN in the default zone,
    # ISP_STREAM_SPAN in the sync zone) is a property of that one Oracle's own coordinate space, not
    # of the combined isp-relative value.
    touches = []
    for t in range(isp):
        hwm = res[t]['oracle_high_water_mark']
        if hwm is None:
            continue
        oracle_stream, oracle_offset = hwm
        touches.append((t * backend.ISP_STREAM_SPAN + oracle_stream, oracle_offset, t, oracle_stream))
    if not touches:
        endseed = orc_root
    else:
        _, offset, t, oracle_stream = max(touches)
        family_capacity = backend.ISP_ITER_MARGIN if oracle_stream < backend.SYNC_ZONE_STREAM_START else backend.ISP_STREAM_SPAN
        carried_stream, carried_offset = one_past(
            oracle_stream, offset, offset_capacity=backend.OFFSET_CAPACITY, stream_family_capacity=family_capacity
        )
        overall_stream = t * backend.ISP_STREAM_SPAN + carried_stream
        endseed = backend.stream_at(orc_root, overall_stream, carried_offset).get_seed()
    return endseed


def get_path_prnstreams(path, iseed, backend):
    """
    One sample path's two streams, computed from the run's seed and the
    path's index alone -- the same streams get_testsolve_prnstreams
    returns at that index, whatever the number of paths
    (tests/test_path_jobs.py holds the two together). This is what lets
    a worker process be told "path 5" rather than be sent path 5's
    live, seeded objects.

    Parameters
    ----------
    path : int
        Non-negative.
    iseed : tuple of int
        The run's starting seed, in the selected `backend`'s own shape.
    backend : module

    Returns
    -------
    orcstream : Stream object
        Unwrapped; becomes the path's Oracle.rng.
    solvstream : random.Random
        Handed to the path's solver.
    """
    orc_root = backend.stream_at(iseed, backend.ISP_STREAM_SPAN, 0).root_seed()
    orcstream = backend.stream_at(orc_root, path * backend.ISP_STREAM_SPAN, 0)
    solvstream = ensure_random_compatible(backend.stream_at(iseed, 1 + path, 0))
    return orcstream, solvstream


def get_solv_prnstreams(iseed, backend):
    """
    Create a random number stream for the algorithm to use and an
    independent one to do simulations.

    Parameters
    ----------
    iseed : tuple of int
        Starting seed to create the generators, in the selected
        `backend`'s own shape (§3.7)
    backend : module
        The selected generator's own module (registry.get_generator),
        §12 step 6b -- was hardcoded to pymoso.prng.mrg32k3a before
        this step.

    Returns
    -------
    orcstream : Stream object
        Unwrapped -- becomes the Oracle's own `self.rng`, and
        Oracle.set_crnflag()'s own backend_for_stream lookup needs the
        real backend instance, not an adapter.
    solvstream : random.Random
        Wrapped with ensure_random_compatible if the backend's own
        Stream isn't already one -- handed to the solver as `sprn`/
        `solvprn`, documented only as "an rng-shaped object" (§3.6);
        MOCOMPASS/MOPBnB's own `self.sprn.sample(...)` calls need the
        full surface, which a raw Philox stream doesn't have.
    """
    # §12 step 6b: stream_at(iseed, 0, 0)/stream_at(iseed, 1, 0), not
    # backend.MRG32k3a(iseed)/backend.get_next_prnstream(iseed) --
    # identical for the MRG family (confirmed directly: stream_at(seed,
    # 0, 0) == the class constructed directly on that seed, and
    # stream_at(seed, 1, 0) == get_next_prnstream(seed)), and stream_at
    # is the one operation every backend actually has (Philox has
    # neither a raw-seed constructor nor get_next_prnstream/jump-ahead
    # at all).
    solvstream = ensure_random_compatible(backend.stream_at(iseed, 0, 0))
    orcstream = backend.stream_at(iseed, 1, 0)
    return orcstream, solvstream


def check_role_draws(stream, backend, role):
    """
    Raise if a solver-role or x0-role stream drew more raw values than
    one stream holds -- that role's own zone boundary.

    Parameters
    ----------
    stream : object
        The stream the role drew from. Anything without a
        `raw_consumed()` method (a caller's own rng-shaped object) is
        not checked.
    backend : module
        The selected generator's own module.
    role : str
        'solver' or 'x0', for the message.

    Raises
    ------
    RoleDrawOverflow
    """
    raw_consumed = getattr(stream, 'raw_consumed', None)
    if raw_consumed is None:
        return
    drawn = raw_consumed()
    if drawn > backend.OFFSET_CAPACITY:
        raise RoleDrawOverflow(
            'the {0} stream drew {1} raw values, more than the {2} one '
            'stream holds -- it overran its own stream. See '
            'KNOWN_ISSUES.md issue 10.'.format(role, drawn, backend.OFFSET_CAPACITY)
        )
