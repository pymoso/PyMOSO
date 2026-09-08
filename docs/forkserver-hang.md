# Python 3.14's forkserver default hangs `--simpar`/`--proc` on user-supplied problem files

Found investigating a hang first seen running the full test suite under
Python 3.14 (`tests/test_readme_cli_examples.py`'s `--simpar`/`--proc`
README examples, which use `pymoso/examples/myproblem.py` and
`mytester.py`). `py-spy dump` on the stuck process, per the discipline
of dumping before assuming a cause, not the multiprocessing-Pool
`--proc=1` observation alone.

## The mechanism

`pymoso/commands/solve.py` (and `commands/testsolve.py`, identically)
loads a user-supplied `<problem>.py`/`<tester>.py` file like this
(`solve.py:39-46`):

```python
mod_name = '.'.join(['pymoso', 'problems', base_mod_name])
spec = importlib.util.spec_from_file_location(mod_name, probarg)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
sys.modules[mod_name] = module
```

No file exists at `pymoso/problems/<base_mod_name>.py` in the installed
package — `mod_name` is a synthetic name, registered into `sys.modules`
purely in-process, at runtime, in whichever process happens to run this
code. This is the documented way a user supplies their own problem or
tester (README, "Writing a Custom `Oracle`" / the `myproblem.py`/
`mytester.py` examples) — not an edge case.

`--simpar`/`--proc` then dispatch simulation work through a
`multiprocessing.Queue` (`Oracle.set_simpar`, `chnbase.py:1051-1076`,
raw `Process`+`Queue`) or `multiprocessing.Pool` (`chnutils.par_runs`,
used by `testsolve()` unconditionally, even at `--proc=1`). Either way,
the job handed to a worker carries the problem/tester *class* by
reference (e.g. `mp_replicate`'s `orccls` argument, `chnbase.py:26`);
unpickling that reference in the worker re-imports `mod_name`.

Under `fork`, that's harmless: a forked child inherits the parent's
`sys.modules` via copy-on-write, synthetic entry included. Under
`forkserver`, each worker starts from the forkserver's own state and
genuinely re-imports the name — which fails, since no real file backs
it:

```
ModuleNotFoundError: No module named 'pymoso.problems.customprob'
```

`multiprocessing` does not propagate a crashed worker's exception to
the parent. The parent just blocks forever in whichever `.get()` was
waiting for that worker's result — confirmed directly by `py-spy dump`
on the actually-hung process:

```
Thread 61066 (idle)
    _recv (multiprocessing/connection.py:416)
    _recv_bytes (multiprocessing/connection.py:451)
    recv_bytes (multiprocessing/connection.py:226)
    get (multiprocessing/queues.py:101)
    hit (pymoso/chnbase.py:1255)
    ...
```

**Why this is 3.14-specific:** confirmed directly, `multiprocessing.get_start_method()`
on this machine:

| Python | default start method |
|---|---|
| 3.10 | fork |
| 3.11 | fork |
| 3.12 | fork |
| 3.13 | fork |
| 3.14 | forkserver |

CPython changed the default on Linux for 3.14. Nothing in pymoso
changed; the ground under it moved.

## Minimal reproduction

Independent of pymoso, mirroring only the two things that matter —
`commands/solve.py`'s exact synthetic `sys.modules` registration
pattern, and a `Process`+`Queue` pair matching `Oracle.set_simpar`:

```python
import sys, importlib.util
import multiprocessing as mp

def mp_worker(input, output):
    for func, args in iter(input.get, 'STOP'):
        output.put(func(*args))

def call_compute(cls, x):
    return cls().compute(x)

def main(start_method):
    mod_name = 'pymoso.problems.customprob'
    spec = importlib.util.spec_from_file_location(mod_name, '/tmp/repro2/customprob.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sys.modules[mod_name] = module
    Thing = module.Thing

    ctx = mp.get_context(start_method)
    req_q, res_q = ctx.Queue(), ctx.Queue()
    procs = [ctx.Process(target=mp_worker, args=(req_q, res_q)) for _ in range(4)]
    for p in procs: p.start()
    for i in range(8): req_q.put((call_compute, Thing, i))
    # forkserver: every worker crashes on unpickle; 0/8 results, 10s timeout each
    # fork:       8/8 results, instant
```

Result: under `forkserver`, all four workers crash immediately
(`ModuleNotFoundError: No module named 'pymoso.problems.customprob'`,
printed to stderr, never seen by the parent); 0 of 8 results delivered,
each `.get()` timing out. Under `fork`, 8/8 results, instant. This
reproduces the failure mode exactly, with no pymoso code involved —
it's a property of "register a module synthetically in `sys.modules`,
then have a `forkserver`-spawned child unpickle a reference into it,"
full stop.

## What this does and doesn't affect

Only the dynamic-file-loading path — `pymoso solve/testsolve <file>.py
...` — combined with `--simpar` or `--proc` (either value, since
`testsolve` always goes through `Pool`). Built-in problems/testers
(`ProbTPA`, `TPATester`, etc.), imported normally from the installed
`pymoso.problems`/`pymoso.testers` packages, are real importable
modules and are not affected — a `forkserver` worker can `import
pymoso.problems.probtpa` from scratch just fine.

But the dynamic-file-loading path *is* the documented way a user
supplies their own problem — the whole point of the package for anyone
not just running the four bundled test problems. This hits exactly the
users not running built-in test problems, not an unusual corner.

Confirmed present in a real PyPI 1.0.8 install, byte-identical
mechanism (`sys.modules[mod_name] = module` in both `solve.py` and
`testsolve.py`, `Process`/`Pool` unchanged) — not something this
migration introduced. Anyone running 1.0.8 (or any other 1.x) with a
custom problem file, `--simpar`, or `--proc`, on Python 3.14+, hits
this today.

## Why `ctx = get_context('fork')` is a workaround, not a fix

Forcing `fork` everywhere `pymoso` creates a `Process`/`Pool` would
make this specific hang go away, and it would be tempting to stop
there. Don't: forking a process that holds threads or locks can
deadlock the *child* (a lock held by a thread that doesn't exist in the
forked child, because only the calling thread survives `fork()`, stays
locked forever) — this is precisely the class of bug CPython changed
the default to avoid. Pinning `fork` back doesn't fix the underlying
problem, it re-opts into the hazard the 3.14 change exists to close,
and stays fragile against whatever Python does next (`fork` is
documented as unsafe on macOS already and disallowed by default there
since 3.8; nothing guarantees it stays available on Linux either).
Fine as a short-term unblock if one is needed; not a design to settle
on.

## This is a prerequisite for the Spark goal, not a detour

A Spark worker is a fresh process on a *different machine* — strictly
worse than `forkserver` for this purpose: no shared filesystem access
to `probarg`'s original path, and certainly no inherited `sys.modules`
of any kind, synthetic or otherwise. Whatever fixes this needs to fix
it in a way that also works when the worker isn't even on the same
machine.

The requirement this implies: a worker must be able to reconstruct the
problem from **transportable data** — a file path (if shared storage
can be assumed), a module spec plus source text, or similar — not from
a class *reference* that depends on the parent process's `sys.modules`
state existing somewhere the worker can reach it. To be explicit about
a distinction that's easy to blur: the fix is not "make the class
pickle correctly" (e.g. registering `__reduce__`, or getting
`cloudpickle` to serialize the class by value instead of by reference).
That would paper over *this* symptom on a single machine while leaving
the actual constraint — a worker needs enough self-contained
information to construct the problem without depending on the parent's
process state — unaddressed for the case that actually matters later.
"Serialize the problem" means ship what a worker needs to reconstruct
it from scratch, not make a reference to living parent-process state
survive transport.

## Fourth multiprocessing lifecycle finding

In order found on this project:

1. `--simpar` worker-leak on the error path (fixed this migration,
   `Oracle` is now a context manager — `KNOWN_ISSUES.md`, "Fixed on
   this branch").
2. `testsolve`'s `--proc` path spawns by a different mechanism
   (`Pool`, unconditionally, even at `--proc=1`) than `--simpar`
   (raw `Process`), and has not been checked for the same
   exception-safety gap (`CLAUDE.md`, "Known open items").
3. This hang.
4. The orphan leak below — `mp_cleanup()` only runs via the context
   manager's `__exit__`, which never fires if the parent itself is
   killed externally rather than exiting normally (observed directly
   while investigating this hang: worker/forkserver processes from an
   earlier killed test run were still alive 45+ minutes later).

Four separate findings in one package's multiprocessing layer is not
four independent bugs to patch individually — it's an argument about
the design (ad hoc `Process`/`Queue`/`Pool` construction scattered
across `chnbase.py`/`chnutils.py`, each with its own lifecycle and
error-handling story) rather than about any one instance. Belongs in
the case for an executor rework, not as four separate point fixes.

No fix proposed or written here, per instruction — diagnosis only.
