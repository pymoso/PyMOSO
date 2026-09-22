"""
Variant 4, bundled form: receives JSON on stdin with MULTIPLE files'
source ({"files": {"customprob": "...", "helper": "..."}, "entry":
"customprob", "class_name": "...", "seed": [...], "x": [...]}) and
registers each into sys.modules as a real (in-memory) module before
exec'ing the entry file, so `from helper import ...` resolves against
the shipped source rather than the filesystem.

Still no filesystem access to the original fixture directory -- same
launch discipline as child_source.py.
"""
import sys
import json
import types


def main():
    data = json.loads(sys.stdin.read())
    files = data["files"]
    entry = data["entry"]

    # Register every shipped file as a real module first, so imports
    # between them resolve via sys.modules regardless of exec order.
    modules = {}
    for name in files:
        mod = types.ModuleType(name)
        mod.__file__ = f"<reconstructed:{name}.py>"
        sys.modules[name] = mod
        modules[name] = mod

    for name, source in files.items():
        code = compile(source, f"<reconstructed:{name}.py>", "exec")
        exec(code, modules[name].__dict__)

    cls = getattr(modules[entry], data["class_name"])

    from pymoso.prng.mrg32k3a import MRG32k3a
    rng = MRG32k3a(tuple(data["seed"]))
    orc = cls(rng)
    isfeas, obj = orc.g(tuple(data["x"]), rng)
    result = {
        "isfeas": isfeas,
        "obj": list(obj) if obj else obj,
        "end_seed": list(rng.get_seed()),
    }
    print(json.dumps(result))


if __name__ == '__main__':
    main()
