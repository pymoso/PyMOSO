"""statistics.mean and variance on fixed random data, as hex: which
Python version changed variance(data, xbar). Measurement only."""
import random, statistics, hashlib, sys
r = random.Random(1)
out_m, out_v, out_v2 = [], [], []
for _ in range(20000):
    n = r.choice([2, 3, 5, 10, 30, 100])
    xs = [r.gauss(10, 3) for _ in range(n)]
    m = statistics.mean(xs)
    out_m.append(m.hex()); out_v.append(statistics.variance(xs, m).hex()); out_v2.append(statistics.variance(xs).hex())
for name, o in [('mean', out_m), ('variance(xs, m)', out_v), ('variance(xs)', out_v2)]:
    print(name, hashlib.sha256(''.join(o).encode()).hexdigest()[:16])
import json; json.dump([out_m, out_v, out_v2], open(sys.argv[1], 'w'))
