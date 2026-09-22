"""
Variant 4 (source-text reconstruction) child. Receives JSON on stdin:
{"source": "<text of ONE file>", "class_name": "...", "seed": [...], "x": [...]}
Deliberately receives only ONE file's source -- the naive/simplest form
of option 4 as proposed, not a bundle -- so the multi-file fixture's
failure mode (if any) is observed honestly, not engineered around.

No filesystem access to the original fixture directory: this process is
launched with cwd set elsewhere and a stripped sys.path/env, so the only
way it can succeed is with what arrived on stdin.
"""
import sys
import json

def main():
    data = json.loads(sys.stdin.read())
    ns = {"__name__": "reconstructed_customprob", "__file__": "<reconstructed:customprob.py>"}
    code = compile(data["source"], "<reconstructed:customprob.py>", "exec")
    exec(code, ns)
    cls = ns[data["class_name"]]

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
