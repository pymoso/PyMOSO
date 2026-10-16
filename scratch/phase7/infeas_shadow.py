# Scratch only: Phase 7 step 1b. Remember oracle-infeasible points within
# an RA iteration, in every interpreter of this venv (a .pth loads it, so
# -I subprocesses get it too).
import os
if os.environ.get('INFEAS_SHADOW') == '1':
    import pymoso.chnbase as chnbase
    def _log(x):
        path = os.environ.get('INFEAS_SHADOW_LOG')
        if path:
            with open(path, 'a') as f:
                f.write('{0} {1}\n'.format(os.getpid(), x))

    _EST = chnbase.RASolver.estimate
    _EM = chnbase.RASolver.estimate_many

    def estimate(self, x, con=float('inf'), nobj=0):
        if x in self.gbar:
            return _EST(self, x, con, nobj)
        memo = self.__dict__.setdefault('_infeas_memo', {})
        key = (getattr(self, 'nu', None), x)
        if key in memo:
            _log(x)
            return memo[key]
        out = _EST(self, x, con, nobj)
        if not out[0] and x not in self.gbar:
            memo[key] = out
        return out

    def estimate_many(self, points):
        points = list(points)
        memo = self.__dict__.setdefault('_infeas_memo', {})
        todo = []
        for x in points:
            if x not in self.gbar and (getattr(self, 'nu', None), x) not in memo and x not in todo:
                todo.append(x)
        fresh = dict(zip(todo, _EM(self, todo)))
        for x, out in fresh.items():
            if not out[0]:
                memo[(getattr(self, 'nu', None), x)] = out
        for x in points:
            if x not in self.gbar and x not in fresh:
                _log(x)
            fresh.pop(x, None)
        return [(True, self.gbar[x], self.sehat[x]) if x in self.gbar else memo[(getattr(self, 'nu', None), x)]
                for x in points]

    chnbase.RASolver.estimate = estimate
    chnbase.RASolver.estimate_many = estimate_many
