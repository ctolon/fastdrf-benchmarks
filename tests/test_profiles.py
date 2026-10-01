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
