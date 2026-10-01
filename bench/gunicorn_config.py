"""Gunicorn hooks of the benchmark server."""

import os


def post_fork(server, worker):
    """
    Pin each worker to its own CPU of ``BENCH_WORKER_CPUS``.

    taskset restricts the master and its workers to the set; within it each
    worker gets one CPU, so a server of N workers uses N CPUs, one each.
    ``worker.age`` counts the workers the master has started, from 1.
    """
    cpus = os.environ.get("BENCH_WORKER_CPUS")
    if cpus:
        choices = [int(cpu) for cpu in cpus.split(",")]
        os.sched_setaffinity(0, {choices[(worker.age - 1) % len(choices)]})
