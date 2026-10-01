import argparse
from pathlib import Path

import pytest

from bench import gunicorn_config
from bench.cases import CASES
from bench.cli import cpu_list, parser
from bench.processes import pinned, server_command
from bench.runner import load_command


def arguments(*extra):
    return parser().parse_args(["run", "--output", "out", *extra])


def test_cpu_list():
    assert cpu_list("0,2,4,6") == [0, 2, 4, 6]
    assert cpu_list("8-11,14") == [8, 9, 10, 11, 14]
    for invalid in ("1,1", "a", ""):
        with pytest.raises(argparse.ArgumentTypeError):
            cpu_list(invalid)


def test_read_load_runs_for_the_duration():
    args = arguments("--duration", "7", "--load-cpus", "8-11")
    command = load_command("oha", args, CASES["small"], None)
    assert command[:3] == ["taskset", "-c", "8,9,10,11"]
    assert command[command.index("--worker-threads") + 1] == "4"
    assert command[command.index("-z") + 1] == "7s"
    assert "-n" not in command and "-D" not in command
    assert command[-1] == "http://127.0.0.1:8180/out/small/"


def test_write_load_sends_a_fixed_number_of_requests():
    args = arguments("--write-requests", "500")
    body = Path("body.json")
    command = load_command("oha", args, CASES["db-update"], body)
    assert command[command.index("-m") + 1] == "PATCH"
    assert command[command.index("-n") + 1] == "500"
    assert command[command.index("-D") + 1] == "body.json"
    warmup = load_command("oha", args, CASES["db-update"], body, warmup=True)
    assert "-n" not in warmup and warmup[warmup.index("-z") + 1] == "2s"


def test_input_load_is_timed_not_counted():
    command = load_command("oha", arguments(), CASES["invalid"], Path("b"))
    assert "-z" in command and "-n" not in command


def test_server_command():
    command = server_command("127.0.0.1", 8180, 4, 8)
    assert command[command.index("--worker-class") + 1] == "gthread"
    assert command[command.index("--workers") + 1] == "4"
    assert command[command.index("--threads") + 1] == "8"
    assert pinned(["x"], [0, 2]) == ["taskset", "-c", "0,2", "x"]
    assert pinned(["x"], None) == ["x"]


def test_each_worker_is_pinned_to_its_cpu(monkeypatch):
    pinned_to = []
    monkeypatch.setenv("BENCH_WORKER_CPUS", "0,2,4,6")
    monkeypatch.setattr(
        gunicorn_config.os,
        "sched_setaffinity",
        lambda pid, cpus: pinned_to.append(cpus),
    )
    for age in range(1, 5):
        gunicorn_config.post_fork(None, argparse.Namespace(age=age))
    assert pinned_to == [{0}, {2}, {4}, {6}]
