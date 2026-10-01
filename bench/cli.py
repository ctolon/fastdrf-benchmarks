"""Command-line entry points: prepare, check, record expectations, measure, report."""

import argparse
import os
import signal
import subprocess
import sys
from pathlib import Path

from bench.cases import CASES, PROFILES


def positive(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def cpu_list(value: str) -> list[int]:
    """``0,2,4,6`` or ``8-15``: logical CPU numbers, in order."""
    cpus: list[int] = []
    try:
        for part in value.split(","):
            first, _, last = part.partition("-")
            cpus += range(int(first), int(last or first) + 1)
    except ValueError:
        raise argparse.ArgumentTypeError(
            "expected CPU numbers such as 0,2,4 or 8-15"
        ) from None
    if not cpus or len(cpus) != len(set(cpus)) or min(cpus) < 0:
        raise argparse.ArgumentTypeError("expected distinct CPU numbers")
    return cpus


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="fastdrf-bench", description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)
    commands.add_parser(
        "prepare", help="Migrate the database and write the seeded rows"
    )

    check = commands.add_parser(
        "check",
        help="Send every case to one profile in-process (Django's test client) and compare it with bench/expected.json",
    )
    check.add_argument("--profile", choices=PROFILES, required=True)
    check.add_argument("--cases", nargs="+", choices=CASES, default=list(CASES))

    expected = commands.add_parser(
        "expected",
        help="Compute DRF's responses in-process; compare them with bench/expected.json, or --write them",
    )
    expected.add_argument("--write", action="store_true")

    serve = commands.add_parser(
        "serve", help="Run one profile's server for manual checks"
    )
    serve.add_argument("--profile", choices=PROFILES, required=True)
    serve.add_argument("--port", type=positive, default=8180)
    serve.add_argument("--workers", type=positive, default=1)
    serve.add_argument("--threads", type=positive, default=8)

    run = commands.add_parser(
        "run", help="Measure the cases with a fresh server per sample"
    )
    run.add_argument("--cases", nargs="+", choices=CASES, default=list(CASES))
    run.add_argument("--profiles", nargs="+", choices=PROFILES, default=list(PROFILES))
    run.add_argument("--workers", type=positive, nargs="+", default=[1, 4])
    run.add_argument(
        "--threads", type=positive, default=8, help="Gunicorn threads per worker"
    )
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--host", default="127.0.0.1")
    run.add_argument("--port", type=positive, default=8180)
    run.add_argument(
        "--duration", type=positive, default=10, help="Seconds per read sample"
    )
    run.add_argument(
        "--warmup", type=int, default=2, help="Seconds of warmup; 0 disables"
    )
    run.add_argument("--repeats", type=positive, default=3)
    run.add_argument("--concurrency", type=positive, default=64)
    run.add_argument(
        "--write-requests",
        type=positive,
        default=2000,
        help="Requests per write sample",
    )
    run.add_argument(
        "--write-timeout",
        type=positive,
        default=600,
        help="Maximum seconds of a write sample",
    )
    run.add_argument(
        "--load-threads",
        type=positive,
        default=4,
        help="oha threads without --load-cpus",
    )
    run.add_argument(
        "--server-cpus",
        type=cpu_list,
        help="CPUs of the server: worker i is pinned to the i-th of them",
    )
    run.add_argument(
        "--load-cpus", type=cpu_list, help="CPUs of oha, with one oha thread per CPU"
    )
    run.add_argument(
        "--seed", type=int, default=42, help="Seed of the configuration order"
    )
    run.add_argument("--oha", default="oha")

    report = commands.add_parser("report", help="Write the report of a run again")
    report.add_argument("directory", type=Path)
    return result


def stop_on_sigterm() -> None:
    """Exit on SIGTERM through the normal unwinding, as on Ctrl-C.

    Python's default SIGTERM action ends the process without running
    ``finally`` blocks, which would leave the server under test running.
    """

    def stop(signum, frame):
        raise SystemExit(128 + signum)

    signal.signal(signal.SIGTERM, stop)


def setup(profile: str) -> None:
    os.environ["BENCH_PROFILE"] = profile
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "bench.settings")
    import django

    django.setup()


def migrate() -> None:
    from django.core.management import call_command

    call_command("migrate", interactive=False, verbosity=0)


def in_process(names: list[str]) -> dict:
    from bench import inprocess

    migrate()
    return {name: inprocess.run(CASES[name]) for name in names}


def check(args) -> None:
    from bench import verify

    setup(args.profile)
    expected = verify.load_expected()
    failures = []
    for name, result in in_process(args.cases).items():
        case = CASES[name]
        try:
            verify.compare(case, result.fingerprint, expected[name])
            if case.queries is not None and result.queries != case.queries:
                raise verify.Mismatch(
                    f"{name}: {result.queries} SQL queries, expected {case.queries}"
                )
        except verify.Mismatch as exc:
            failures.append(str(exc))
            continue
        print(
            f"{name}: {result.fingerprint['status']}, {result.fingerprint['length']} bytes, "
            f"{result.queries} queries: as expected"
        )
    if failures:
        raise ValueError("\n".join(failures))


def record_expected(args) -> None:
    from bench import verify

    setup("drf")
    fingerprints = {
        name: result.fingerprint for name, result in in_process(list(CASES)).items()
    }
    if args.write:
        verify.write_expected(fingerprints)
        print(f"Wrote {verify.EXPECTED}")
        return
    if fingerprints != verify.load_expected():
        raise ValueError(f"DRF's responses differ from {verify.EXPECTED}")
    print(f"DRF's responses are those of {verify.EXPECTED}")


def main() -> None:
    arguments = parser()
    args = arguments.parse_args()
    stop_on_sigterm()
    try:
        if args.command == "prepare":
            setup("drf")
            from bench.api import data

            migrate()
            data.seed()
            print(f"Database ready: {data.counts()}")
        elif args.command == "check":
            check(args)
        elif args.command == "expected":
            record_expected(args)
        elif args.command == "serve":
            from bench.processes import ROOT, environment, server_command

            os.chdir(ROOT)
            command = server_command("127.0.0.1", args.port, args.workers, args.threads)
            os.execve(command[0], command, environment(args.profile))
        elif args.command == "run":
            from bench.runner import run

            if args.warmup < 0:
                raise ValueError("--warmup cannot be negative")
            for name in ("cases", "profiles", "workers"):
                values = getattr(args, name)
                if len(values) != len(set(values)):
                    raise ValueError(f"--{name} has duplicates")
            run(args)
        elif args.command == "report":
            from bench.results import write_report

            write_report(args.directory)
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        arguments.exit(1, f"Error: {exc}\n")


if __name__ == "__main__":
    sys.exit(main())
