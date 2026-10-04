"""The measurement loop: every case, profile and worker count, one sample at a time."""

import hashlib
import json
import os
import random
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

from bench import verify
from bench.cases import Case, selected
from bench.monitor import ResourceMonitor
from bench.processes import ROOT, server, server_command, worker_affinity
from bench.results import normalize, write_report
from bench.service_usage import ServiceUsage, containers
from bench.snapshot import snapshot

POSTGRES_SETTINGS = (
    "server_version",
    "shared_buffers",
    "effective_cache_size",
    "work_mem",
    "max_connections",
    "fsync",
    "synchronous_commit",
    "random_page_cost",
)


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, default=str) + "\n")


def setup_django() -> None:
    """Django in the runner, with the fastdrf profile's settings: for the
    database resets and for the record of what fastdrf compiles."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "bench.settings")
    os.environ["BENCH_PROFILE"] = "fastdrf"
    import django

    django.setup()


def migrate() -> None:
    subprocess.run(
        [sys.executable, "manage.py", "migrate", "--noinput", "-v", "0"],
        cwd=ROOT,
        env={**os.environ, "BENCH_PROFILE": "drf"},
        check=True,
        timeout=120,
    )


def reset_database() -> None:
    """The seeded rows again; the runner's connection is closed afterwards so
    that it holds nothing while the server runs."""
    from django.db import connection

    from bench.api import data

    data.seed()
    connection.close()


def written(case: Case, requests: int) -> None:
    """Check what ``requests`` requests of a write case left in the database."""
    from django.db import connection

    from bench.api import data, models, payloads

    try:
        articles = data.counts()["articles"]
        if case.name == "db-create":
            expected = payloads.ARTICLES + requests
            if articles != expected:
                raise verify.Mismatch(
                    f"db-create: {articles} articles after {requests} creates, expected {expected}"
                )
        elif case.name == "db-update":
            article = models.Article.objects.get(pk=payloads.UPDATED_ARTICLE)
            body = payloads.update_input()
            if articles != payloads.ARTICLES or article.title != body["title"]:
                raise verify.Mismatch("db-update: the article was not updated")
    finally:
        connection.close()


def postgres_settings() -> dict:
    from django.db import connection

    try:
        with connection.cursor() as cursor:
            values = {}
            for name in POSTGRES_SETTINGS:
                cursor.execute(f"SHOW {name}")
                values[name] = cursor.fetchone()[0]
            return values
    finally:
        connection.close()


def profile_settings() -> dict:
    from django.conf import settings

    from bench.api.fast.views import Optimized

    def dotted(classes):
        return [f"{cls.__module__}.{cls.__qualname__}" for cls in classes]

    return {
        "drf": {"REST_FRAMEWORK": "not set (DRF's defaults)", "FASTDRF": "not set"},
        "fastdrf": {
            "REST_FRAMEWORK": "not set (DRF's defaults)",
            "FASTDRF": settings.FASTDRF,
            "BENCH_JSON": settings.BENCH_JSON,
            "renderer_classes": dotted(Optimized.renderer_classes),
            "parser_classes": dotted(Optimized.parser_classes),
        },
    }


def provenance(args, oha: str, cases: list[Case]) -> dict:
    from bench.inspection import fastdrf_path

    environment = snapshot()
    record = {
        "schema_version": 1,
        "state": "running",
        "started_at": datetime.now(UTC).isoformat(),
        "parameters": {
            key: str(value) if isinstance(value, Path) else value
            for key, value in vars(args).items()
            if key not in ("command", "expected")
        },
        "environment": environment,
        "oha_version": subprocess.check_output([oha, "--version"], text=True).strip(),
        "settings": profile_settings(),
        "server_commands": {
            f"w{workers}": server_command(args.host, args.port, workers, args.threads)
            for workers in args.workers
        },
        "cases": {
            case.name: {
                "kind": case.kind,
                "method": case.method,
                "path": case.path,
                "status": case.status,
                "request_bytes": len(case.body_bytes or b""),
                "response_bytes": args.expected[case.name]["length"],
                "queries": case.queries,
                "fastdrf": fastdrf_path(case),
            }
            for case in cases
        },
        "expected_sha256": hashlib.sha256(verify.EXPECTED.read_bytes()).hexdigest(),
    }
    if any(case.uses_database for case in cases):
        record["postgres"] = postgres_settings()
    return record


def load_command(
    oha: str, args, case: Case, body: Path | None, *, warmup: bool = False
) -> list[str]:
    threads = len(args.load_cpus) if args.load_cpus else args.load_threads
    command = [
        oha,
        "--no-tui",
        "--output-format",
        "json",
        "--disable-compression",
        "--http-version",
        "1.1",
        "--worker-threads",
        str(threads),
        "-c",
        str(args.concurrency),
        "-t",
        "15s",
        # Wait for the requests in flight at the end, so that every request
        # sent is counted.
        "-w",
        "-m",
        case.method,
    ]
    if body is not None:
        command += ["-T", "application/json", "-D", str(body)]
    if case.writes and not warmup:
        # A fixed number of writes, so that every sample writes the same rows.
        command += ["-n", str(args.write_requests)]
    else:
        command += ["-z", f"{args.warmup if warmup else args.duration}s"]
    command.append(f"http://{args.host}:{args.port}{case.path}")
    if args.load_cpus:
        command = ["taskset", "-c", ",".join(map(str, args.load_cpus)), *command]
    return command


def load(command: list[str], destination: Path, *, timeout: float) -> tuple[dict, dict]:
    """
    Run the load generator; return its result and its CPU use: seconds of CPU
    time, and cores (CPU seconds per elapsed second).
    """
    write_json(destination.with_suffix(".command.json"), command)
    with (
        destination.open("w") as output,
        destination.with_suffix(".stderr.log").open("w") as errors,
    ):
        started = time.monotonic()
        child = subprocess.Popen(command, stdout=output, stderr=errors)
        deadline = started + timeout
        while True:
            pid, status, usage = os.wait4(child.pid, os.WNOHANG)
            if pid:
                break
            if time.monotonic() > deadline:
                child.kill()
                child.wait()
                raise subprocess.TimeoutExpired(command, timeout)
            time.sleep(0.05)
        elapsed = time.monotonic() - started
        child.returncode = os.waitstatus_to_exitcode(status)
    if child.returncode:
        raise subprocess.CalledProcessError(child.returncode, command)
    cpu = usage.ru_utime + usage.ru_stime
    return json.loads(destination.read_text()), {
        "cpu_seconds": round(cpu, 3),
        "cores": round(cpu / elapsed, 3) if elapsed else 0.0,
    }


def measure(args, oha: str, case: Case, profile: str, workers: int, folder: Path):
    expected = args.expected[case.name]
    body = None
    if case.body_bytes is not None:
        body = folder / "body.json"
        body.write_bytes(case.body_bytes)
    if case.uses_database:
        reset_database()
    base_url = f"http://{args.host}:{args.port}"
    with (
        server(
            profile,
            host=args.host,
            port=args.port,
            workers=workers,
            threads=args.threads,
            log=folder / "server.log",
            cpus=args.server_cpus,
        ) as process,
        httpx.Client(base_url=base_url, timeout=60, trust_env=False) as client,
    ):
        affinity = worker_affinity(process.pid)
        if args.server_cpus and affinity != [
            [cpu] for cpu in args.server_cpus[:workers]
        ]:
            raise RuntimeError(f"Workers are not pinned one per CPU: {affinity}")
        verify.check_http(client, case, expected)
        if case.writes:
            written(case, 1)
        if args.warmup:
            raw, _ = load(
                load_command(oha, args, case, body, warmup=True),
                folder / "warmup.json",
                timeout=args.warmup + 60,
            )
            normalize(raw, status=case.status)
        if case.writes:
            reset_database()
        monitor = ResourceMonitor(process.pid)
        usage = ServiceUsage(containers())
        try:
            with monitor, usage:
                raw, generator = load(
                    load_command(oha, args, case, body),
                    folder / "oha.json",
                    timeout=args.write_timeout if case.writes else args.duration + 60,
                )
        finally:
            write_json(
                folder / "resources.json",
                {"samples": monitor.samples, **monitor.summary()},
            )
        result = normalize(
            raw,
            status=case.status,
            expected_requests=args.write_requests if case.writes else None,
        )
        if case.writes:
            written(case, args.write_requests)
            reset_database()
        # The same bytes after the load: nothing the load did changed them.
        verify.check_http(client, case, expected)
    threads = len(args.load_cpus) if args.load_cpus else args.load_threads
    generator["cpus"] = threads
    generator["utilization"] = round(generator["cores"] / threads, 3)
    return {
        **result,
        **monitor.summary(),
        "service_cpu": usage.result,
        "load_cpu": generator,
        "worker_cpus": affinity,
    }


def run(args) -> None:
    if os.environ.get("BENCH_DATABASE", "postgres") != "postgres":
        raise ValueError("Measurements need PostgreSQL; SQLite is for the tests only")
    if args.host != "127.0.0.1":
        raise ValueError("The runner binds the server to 127.0.0.1 only")
    oha = shutil.which(args.oha)
    if oha is None:
        raise ValueError("Install oha or pass --oha /path/to/oha")
    if args.server_cpus and len(args.server_cpus) < max(args.workers):
        raise ValueError("--server-cpus needs one CPU per worker")
    cases = selected(args.cases)
    args.expected = verify.load_expected()
    directory = args.output.resolve()
    directory.mkdir(parents=True, exist_ok=False)
    manifest = {"schema_version": 1, "state": "initializing", "parameters": {}}
    samples: list[dict] = []
    failed = False
    write_json(directory / "samples.json", samples)
    try:
        setup_django()
        if any(case.uses_database for case in cases):
            migrate()
            reset_database()
        manifest = provenance(args, oha, cases)
        (directory / "compose.yaml").write_text((ROOT / "compose.yaml").read_text())
        write_json(directory / "manifest.json", manifest)
        order = random.Random(args.seed)
        configurations = [
            (profile, workers) for profile in args.profiles for workers in args.workers
        ]
        for repeat in range(1, args.repeats + 1):
            for case in cases:
                shuffled = configurations.copy()
                order.shuffle(shuffled)
                for profile, workers in shuffled:
                    folder = (
                        directory / f"{repeat:02d}-{case.name}-{profile}-w{workers}"
                    )
                    folder.mkdir()
                    record = {
                        "repeat": repeat,
                        "case": case.name,
                        "profile": profile,
                        "workers": workers,
                        "valid": False,
                    }
                    print(
                        f"[{repeat}/{args.repeats}] {case.name}: {profile}, {workers} worker(s)",
                        flush=True,
                    )
                    try:
                        record.update(
                            measure(args, oha, case, profile, workers, folder),
                            valid=True,
                        )
                    except (Exception, KeyboardInterrupt) as exc:
                        record["error"] = f"{type(exc).__name__}: {exc}"
                        failed = True
                        if isinstance(exc, KeyboardInterrupt):
                            raise
                    finally:
                        samples.append(record)
                        write_json(directory / "samples.json", samples)
        manifest["state"] = "failed" if failed else "complete"
    except BaseException as exc:
        manifest.update(state="interrupted", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        manifest["finished_at"] = datetime.now(UTC).isoformat()
        write_json(directory / "manifest.json", manifest)
        if samples:
            write_report(directory)
    if failed:
        raise ValueError(
            f"One or more samples failed; see {directory / 'samples.json'}"
        )
