"""
Run by tests/test_worker_pool.py as a separate process: opens a pool,
prints its workers' pids, then waits to be killed.

    python _pool_parent_kill.py <start method> idle|busy
"""
import multiprocessing
import sys
import time

from pymoso.pool import WorkerPool


def sleep_task(state, seconds):
    time.sleep(seconds)
    return seconds


def main(method, mode):
    pool = WorkerPool(3, context=multiprocessing.get_context(method)).open()
    print(" ".join(str(w.process.pid) for w in pool._workers), flush=True)
    if mode == "busy":
        pool.run([(sleep_task, (2.0,))] * 3)
    time.sleep(600)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
