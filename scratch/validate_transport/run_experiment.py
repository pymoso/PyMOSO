"""
Validation experiment for the transportable-data fix options in
docs/forkserver-hang.md (options 4 and 5). Standalone -- does not touch
pymoso itself, only reads it as an installed dependency.

Run once per (fixture, variant) combination, in its own process, to
avoid any cross-fixture sys.modules contamination in the harness itself
(realistic usage only ever loads one custom problem per run anyway).
See run_all.sh for the full matrix.

"Matches exactly" is defined as: identical (isfeas, obj) from g(x, rng)
AND identical rng.get_seed() after the call. A result that matches on
values but leaves the RNG in a different state is reported as a FAIL,
not a pass -- same distinction as docs/end-seed-scope.md's finding.

No shared filesystem for the child: launched with cwd in an unrelated
directory and an env stripped of any path back to the fixture directory
or this script's own directory. Only bytes written to the child's stdin
are available to it.
"""
import sys
import os
import json
import subprocess
import importlib.util

SEED = (12345, 12345, 12345, 12345, 12345, 12345)
X = (7,)

HERE = os.path.dirname(os.path.abspath(__file__))
CHILD_CWD = '/tmp/validate_transport_childcwd'


def pymoso_style_load(mod_name, filepath, allow_sibling_imports=False):
    """
    Exactly commands/solve.py's loading pattern (solve.py:39-46) -- with
    one deliberate deviation, flagged: commands/solve.py never adds the
    custom file's own directory to sys.path, so a multi-file custom
    problem (a sibling `import helper`) fails to load in pymoso's real
    CLI today, in a single process, with no multiprocessing involved at
    all. That's a separate, pre-existing bug from the one this
    experiment is validating a fix for. allow_sibling_imports=True is a
    stand-in so a reference value can still be computed for the
    multi-file fixture, NOT a claim that this is what pymoso does today.
    """
    if allow_sibling_imports:
        sys.path.insert(0, os.path.dirname(filepath))
    try:
        spec = importlib.util.spec_from_file_location(mod_name, filepath)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        sys.modules[mod_name] = module
        return module
    finally:
        if allow_sibling_imports:
            sys.path.remove(os.path.dirname(filepath))


def compute_reference(cls):
    from pymoso.prng.mrg32k3a import MRG32k3a
    rng = MRG32k3a(SEED)
    orc = cls(rng)
    isfeas, obj = orc.g(X, rng)
    return {
        "isfeas": isfeas,
        "obj": list(obj) if obj else obj,
        "end_seed": list(rng.get_seed()),
    }


def clean_env():
    env = {}
    for k in ('PATH', 'HOME', 'LANG', 'LC_ALL'):
        if k in os.environ:
            env[k] = os.environ[k]
    return env


def run_child(child_script, stdin_bytes, python_exe):
    try:
        proc = subprocess.run(
            [python_exe, child_script],
            input=stdin_bytes,
            capture_output=True,
            cwd=CHILD_CWD,
            env=clean_env(),
            timeout=15,
        )
    except subprocess.TimeoutExpired:
        return None, "TIMED OUT after 15s"
    if proc.returncode != 0:
        return None, f"child exited {proc.returncode}, stderr:\n{proc.stderr.decode(errors='replace')}"
    try:
        return json.loads(proc.stdout.decode()), None
    except Exception as e:
        return None, f"could not parse child stdout ({e}): {proc.stdout!r} stderr={proc.stderr.decode(errors='replace')}"


def main():
    fixture_dir = sys.argv[1]     # e.g. fixture_single or fixture_multi
    variant = sys.argv[2]         # 'source' or 'cloudpickle'
    python_exe = sys.argv[3]

    fixture_path = os.path.join(HERE, fixture_dir)
    main_file = os.path.join(fixture_path, 'customprob.py')
    mod_name = 'pymoso.problems.customprob'

    is_multi = (fixture_dir == 'fixture_multi')
    if is_multi:
        # Real pymoso can't load this at all today (see
        # pymoso_style_load's docstring) -- sibling imports allowed here
        # ONLY to compute a reference value for comparison purposes.
        module = pymoso_style_load(mod_name, main_file, allow_sibling_imports=True)
    else:
        module = pymoso_style_load(mod_name, main_file)
    cls = module.MyProblem

    expected = compute_reference(cls)

    if variant == 'source':
        with open(main_file) as f:
            source = f.read()
        payload = json.dumps({
            "source": source,
            "class_name": "MyProblem",
            "seed": list(SEED),
            "x": list(X),
        }).encode()
        child_script = os.path.join(HERE, 'runners', 'child_source.py')
        got, err = run_child(child_script, payload, python_exe)

    elif variant == 'source-bundle':
        # Ship every local .py file in the fixture directory, not just
        # the entry point -- the fix the naive 'source' variant's
        # multi-file failure implies is needed.
        files = {}
        for fname in os.listdir(fixture_path):
            if fname.endswith('.py'):
                with open(os.path.join(fixture_path, fname)) as f:
                    files[fname[:-3]] = f.read()
        payload = json.dumps({
            "files": files,
            "entry": "customprob",
            "class_name": "MyProblem",
            "seed": list(SEED),
            "x": list(X),
        }).encode()
        child_script = os.path.join(HERE, 'runners', 'child_source_bundle.py')
        got, err = run_child(child_script, payload, python_exe)

    elif variant in ('cloudpickle', 'cloudpickle-forced', 'cloudpickle-forced-all'):
        import cloudpickle
        registered = []
        if variant == 'cloudpickle-forced':
            # cloudpickle's default: pickle by reference for anything
            # that looks like an importable module (which our synthetic
            # sys.modules entry does, even though nothing real backs
            # it). register_pickle_by_value forces by-value serialization
            # instead -- explicitly marked "experimental" by cloudpickle
            # itself. Registers ONLY the entry module, deliberately, to
            # see whether that alone is enough for the multi-file case.
            cloudpickle.register_pickle_by_value(module)
            registered.append(module)
        elif variant == 'cloudpickle-forced-all':
            # Registers every local (non-installed) module the entry
            # module pulled in -- the fix this experiment implies
            # cloudpickle actually needs for a multi-file problem: the
            # full transitive closure of locally-loaded modules, not
            # just the entry point.
            cloudpickle.register_pickle_by_value(module)
            registered.append(module)
            if is_multi:
                helper_mod = sys.modules['helper']
                cloudpickle.register_pickle_by_value(helper_mod)
                registered.append(helper_mod)
        blob = cloudpickle.dumps({"cls": cls, "seed": SEED, "x": X})
        for m in registered:
            cloudpickle.unregister_pickle_by_value(m)
        child_script = os.path.join(HERE, 'runners', 'child_cloudpickle.py')
        got, err = run_child(child_script, blob, python_exe)

    else:
        raise ValueError(variant)

    label = f"[{variant} / {fixture_dir}]"
    if err is not None:
        print(f"{label} FAIL")
        print(f"  reason: {err}")
        sys.exit(1)
    elif got == expected:
        print(f"{label} PASS -- {got}")
    else:
        print(f"{label} FAIL -- value/state mismatch")
        print(f"  expected: {expected}")
        print(f"  got:      {got}")
        sys.exit(1)


if __name__ == '__main__':
    main()
