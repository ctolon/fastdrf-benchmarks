"""Starting and stopping the Gunicorn server of a sample."""

import os
import signal
import socket
import subprocess
import sys
import time
from collections.abc import Generator
from contextlib import contextmanager, suppress
from pathlib import Path

import httpx
import psutil

from bench.cases import PROFILES

ROOT = Path(__file__).resolve().parent.parent


def environment(profile: str) -> dict[str, str]:
    if profile not in PROFILES:
        raise ValueError(f"Unknown profile: {profile}")
    return {
        **os.environ,
        "BENCH_PROFILE": profile,
        "DJANGO_SETTINGS_MODULE": "bench.settings",
        "PYTHONHASHSEED": "0",
        "PYTHONUNBUFFERED": "1",
    }


def server_command(host: str, port: int, workers: int, threads: int) -> list[str]:
    return [
        sys.executable,
        "-m",
        "gunicorn",
        "bench.wsgi:application",
        "--bind",
        f"{host}:{port}",
        "--workers",
        str(workers),
        "--worker-class",
        "gthread",
        "--threads",
        str(threads),
        "--keep-alive",
        "5",
        "--backlog",
        "2048",
        "--timeout",
        "60",
        "--graceful-timeout",
        "10",
        "--log-level",
        "warning",
        "--error-logfile",
        "-",
        "--config",
        "python:bench.gunicorn_config",
    ]


def pinned(command: list[str], cpus: list[int] | None) -> list[str]:
    """``command`` restricted to ``cpus`` with taskset."""
    if not cpus:
        return command
    return ["taskset", "-c", ",".join(map(str, cpus)), *command]


def ensure_port_free(host: str, port: int) -> None:
    """Refuse a port another process listens on.

    ``SO_REUSEADDR``, as Gunicorn sets it, ignores the connections a stopped
    server left in TIME_WAIT.
    """
    with socket.socket() as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        probe.bind((host, port))
        probe.listen()


def check_server_log(log: Path) -> None:
    """Reject a sample whose server reported an error, even after a 200."""
    markers = (
        "Traceback (most recent call last):",
        "[ERROR]",
        "[CRITICAL]",
        "Warning:",
    )
    with log.open() as stream:
        for line in stream:
            if any(marker in line for marker in markers):
                raise RuntimeError(
                    f"The server reported errors; see {log}: {line.strip()}"
                )


def worker_affinity(pid: int) -> list[list[int]]:
    """The CPUs each worker of the Gunicorn master ``pid`` may run on."""
    return sorted(
        sorted(child.cpu_affinity()) for child in psutil.Process(pid).children()
    )


@contextmanager
def server(
    profile: str,
    *,
    host: str,
    port: int,
    workers: int,
    threads: int,
    log: Path,
    cpus: list[int] | None = None,
) -> Generator[subprocess.Popen]:
    """
    Start Gunicorn and stop its whole process group afterwards. With
    ``cpus``, the first ``workers`` of them are used: Gunicorn's master is
    restricted to them with taskset, and each worker pins itself to one of
    them (``bench/gunicorn_config.py``).
    """
    if os.name != "posix":
        raise RuntimeError("The runner requires POSIX process groups")
    if cpus is not None and len(cpus) < workers:
        raise ValueError(f"{workers} workers need {workers} CPUs; {len(cpus)} given")
    ensure_port_free(host, port)
    worker_cpus = cpus[:workers] if cpus else None
    env = environment(profile)
    if worker_cpus:
        env["BENCH_WORKER_CPUS"] = ",".join(map(str, worker_cpus))
    command = pinned(server_command(host, port, workers, threads), worker_cpus)
    with log.open("w") as output:
        child = subprocess.Popen(
            command,
            cwd=ROOT,
            env=env,
            stdout=output,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            wait_until_ready(child, host, port, workers, log)
            yield child
        finally:
            # The process group belongs to this Popen, workers included.
            with suppress(ProcessLookupError):
                os.killpg(child.pid, signal.SIGTERM)
            try:
                child.wait(timeout=15)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait(timeout=10)
    check_server_log(log)


def wait_until_ready(
    child: subprocess.Popen, host: str, port: int, workers: int, log: Path
) -> None:
    """Until the server answers and all its workers have started."""
    deadline = time.monotonic() + 45
    with httpx.Client(timeout=1, trust_env=False) as client:
        while time.monotonic() < deadline:
            if child.poll() is not None:
                raise RuntimeError(f"The server exited during start-up; see {log}")
            try:
                response = client.get(f"http://{host}:{port}/health/")
                if (
                    response.status_code == 200
                    and len(psutil.Process(child.pid).children()) == workers
                ):
                    return
            except httpx.HTTPError, psutil.Error:
                pass
            time.sleep(0.1)
    raise RuntimeError(f"The server did not start in time; see {log}")
