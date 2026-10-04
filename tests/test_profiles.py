"""
Each profile with its own settings, in a process of its own: what Gunicorn
serves, through Django's test client. It uses the database of the
environment (BENCH_DATABASE) and writes the seeded rows to it.
"""

import os
import subprocess
import sys

import pytest

from bench.processes import ROOT


def fastdrf_bench(*arguments):
    return subprocess.run(
        [sys.executable, "-m", "bench.cli", *arguments],
        cwd=ROOT,
        env={key: value for key, value in os.environ.items() if key != "BENCH_PROFILE"},
        capture_output=True,
        text=True,
        timeout=300,
    )


@pytest.mark.parametrize("profile", ["drf", "fastdrf"])
def test_profile_answers_the_expected_responses(profile):
    result = fastdrf_bench("check", "--profile", profile)
    assert result.returncode == 0, result.stderr + result.stdout


def test_expectations_are_drf_responses():
    result = fastdrf_bench("expected")
    assert result.returncode == 0, result.stderr + result.stdout


@pytest.mark.parametrize("backend", ["msgspec", "pydantic", "python"])
@pytest.mark.parametrize("transport", ["msgspec", "pydantic", "orjson", "drf"])
def test_backend_and_transport_combinations_keep_expected_bytes(
    monkeypatch, backend, transport
):
    monkeypatch.setenv("BENCH_SERIALIZER_BACKEND", backend)
    monkeypatch.setenv("BENCH_JSON", transport)
    from bench.cases import CASES

    cases = [name for name in CASES if transport != "orjson" or name != "invalid"]
    result = fastdrf_bench("check", "--profile", "fastdrf", "--cases", *cases)
    assert result.returncode == 0, result.stderr + result.stdout


def test_orjson_rejects_drf_indexed_validation_errors(monkeypatch):
    # The released renderer rejects integer keys in ListField error details.
    # Keep the original expected 400; do not record the server error as parity.
    monkeypatch.setenv("BENCH_JSON", "orjson")
    result = fastdrf_bench("check", "--profile", "fastdrf", "--cases", "invalid")
    assert result.returncode != 0
    assert "Dict key must be str" in result.stderr


@pytest.mark.parametrize(
    "name,value",
    [
        ("BENCH_SERIALIZER_BACKEND", "unknown"),
        ("BENCH_JSON", "unknown"),
        ("BENCH_DELEGATE_FIELDS", "true"),
    ],
)
def test_bad_options_are_rejected(monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    result = fastdrf_bench("check", "--profile", "fastdrf", "--cases", "small")
    assert result.returncode != 0
    assert name in result.stderr


def test_drf_baseline_does_not_change_with_fastdrf_options(monkeypatch):
    monkeypatch.setenv("BENCH_SERIALIZER_BACKEND", "python")
    monkeypatch.setenv("BENCH_JSON", "orjson")
    monkeypatch.setenv("BENCH_DELEGATE_FIELDS", "0")
    result = fastdrf_bench("check", "--profile", "drf")
    assert result.returncode == 0, result.stderr + result.stdout


def test_manifest_records_selected_transport_and_delegation(settings):
    from bench.cases import CASES
    from bench.inspection import fastdrf_path
    from bench.runner import profile_settings

    record = profile_settings()["fastdrf"]
    assert record["BENCH_JSON"] == settings.BENCH_JSON
    assert record["FASTDRF"]["DELEGATE_FIELDS"] is True
    assert record["parser_classes"][0] == "fastdrf.msgspec.parsers.MsgspecJSONParser"
    assert fastdrf_path(CASES["method-field"])["delegated"] == ["label"]


def test_installed_fastdrf_matches_the_lock_and_project():
    import tomllib
    from importlib.metadata import version

    import fastdrf

    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    (requirement,) = (
        item
        for item in project["project"]["dependencies"]
        if item.startswith("django-fastdrf[")
    )
    expected = requirement.split("==", 1)[1]
    assert version("django-fastdrf") == fastdrf.__version__ == expected
    assert (
        f"django-fastdrf=={expected}"
        in (ROOT / "requirements.lock").read_text().splitlines()
    )
