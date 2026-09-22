"""
Variant 5 (cloudpickle by-value) child. Receives a single cloudpickle
blob on stdin (binary), carrying {"cls": <class>, "seed": ..., "x": ...}.
No forced by-value registration is done on the sending side beyond
cloudpickle's own default behavior -- testing what cloudpickle does out
of the box, not what it can be coerced into doing.

No filesystem access to the original fixture directory: launched with
cwd elsewhere and a stripped sys.path/env, same as child_source.py.
"""
import sys
import json
import cloudpickle

def main():
    payload = cloudpickle.loads(sys.stdin.buffer.read())
    cls = payload["cls"]
    seed = payload["seed"]
    x = payload["x"]

    from pymoso.prng.mrg32k3a import MRG32k3a
    rng = MRG32k3a(tuple(seed))
    orc = cls(rng)
    isfeas, obj = orc.g(tuple(x), rng)
    result = {
        "isfeas": isfeas,
        "obj": list(obj) if obj else obj,
        "end_seed": list(rng.get_seed()),
    }
    print(json.dumps(result))

if __name__ == '__main__':
    main()
