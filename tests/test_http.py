"""
Both profiles on real Gunicorn servers: every case answers the expected
bytes. Enable with BENCH_HTTP_TESTS=1; they need the database of the
environment (PostgreSQL by default) and port 8181, and reset its rows.
"""

import os
import subprocess
import sys

import httpx
import pytest

from bench import verify
from bench.cases import CASES
from bench.processes import ROOT, environment, server

pytestmark = pytest.mark.skipif(
    os.environ.get("BENCH_HTTP_TESTS") != "1", reason="set BENCH_HTTP_TESTS=1"
)
PORT = 8181


def seed():
    # In a process of its own: this one may be connected to pytest-django's
    # test database, the server never is.
    subprocess.run(
        [sys.executable, "-m", "bench.cli", "prepare"],
        cwd=ROOT,
        env=environment("drf"),
        check=True,
        capture_output=True,
        timeout=120,
    )


@pytest.mark.parametrize("workers", [1, 2])
@pytest.mark.parametrize("profile", ["drf", "fastdrf"])
def test_server_answers_the_expected_responses(profile, workers, tmp_path):
    expected = verify.load_expected()
    with (
        server(
            profile,
            host="127.0.0.1",
            port=PORT,
            workers=workers,
            threads=4,
            log=tmp_path / "server.log",
        ),
        httpx.Client(base_url=f"http://127.0.0.1:{PORT}", trust_env=False) as client,
    ):
        for case in CASES.values():
            if case.uses_database:
                seed()
            # Twice: the second request uses what the first one cached.
            verify.check_http(client, case, expected[case.name])
            if case.writes:
                seed()
            verify.check_http(client, case, expected[case.name])
