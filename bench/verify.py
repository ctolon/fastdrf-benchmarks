"""
The canonical response of every case, and the check of a response against it.

``bench/expected.json`` holds, for each case, the status, the headers the
application sets, and the length and SHA-256 of the body that DRF's profile
answers in-process (``fastdrf-bench expected``). The tests check that both
profiles answer it in-process, and the runner checks it on the real server
before and after every sample. A response matches only with exactly these
bytes, so both profiles answer the same bytes.

Absolute URLs (the pagination links) contain the host the request was sent
to; they are compared with that base URL replaced by ``http://testserver``,
the test client's.
"""

import hashlib
import json
from pathlib import Path

import httpx

from bench.cases import Case

EXPECTED = Path(__file__).with_name("expected.json")
CANONICAL_BASE = b"http://testserver"
# Headers the HTTP server adds or that describe the connection, not the
# application's response.
SERVER_HEADERS = {
    "connection",
    "content-length",
    "date",
    "keep-alive",
    "server",
    "transfer-encoding",
}


class Mismatch(AssertionError):
    pass


def canonical(body: bytes, base_url: str) -> bytes:
    return body.replace(base_url.rstrip("/").encode(), CANONICAL_BASE)


def fingerprint(status: int, headers, body: bytes, base_url: str) -> dict:
    """What is compared: status, application headers, body length and digest."""
    content = canonical(body, base_url)
    return {
        "status": status,
        "headers": {
            name.lower(): value
            for name, value in sorted(headers)
            if name.lower() not in SERVER_HEADERS
        },
        "length": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }


def load_expected() -> dict[str, dict]:
    return json.loads(EXPECTED.read_text())


def write_expected(fingerprints: dict[str, dict]) -> None:
    EXPECTED.write_text(json.dumps(fingerprints, indent=2, sort_keys=True) + "\n")


def compare(case: Case, observed: dict, expected: dict) -> None:
    """Raise Mismatch, naming every difference, unless ``observed`` is ``expected``."""
    differences = [
        f"{key}: expected {expected[key]!r}, got {observed.get(key)!r}"
        for key in ("status", "headers", "length", "sha256")
        if observed.get(key) != expected[key]
    ]
    if differences:
        raise Mismatch(f"{case.name}: " + "; ".join(differences))


def check_framing(headers, body: bytes) -> None:
    """A Content-Length header, when present, must be the body's length."""
    length = headers.get("content-length")
    if length is not None and int(length) != len(body):
        raise Mismatch(f"Content-Length {length} for a body of {len(body)} bytes")


def request_http(client: httpx.Client, case: Case) -> httpx.Response:
    headers = {"Content-Type": "application/json"} if case.body_bytes else {}
    return client.request(
        case.method, case.path, content=case.body_bytes, headers=headers
    )


def check_http(client: httpx.Client, case: Case, expected: dict) -> dict:
    """Send the case to a running server and check its response; return it."""
    response = request_http(client, case)
    check_framing(response.headers, response.content)
    observed = fingerprint(
        response.status_code,
        response.headers.items(),
        response.content,
        str(client.base_url),
    )
    compare(case, observed, expected)
    return observed


def request_django(client, case: Case):
    """The response of the Django test client ``client`` to ``case``."""
    return client.generic(
        case.method,
        case.path,
        case.body_bytes or b"",
        content_type="application/json",
    )


def django_fingerprint(response) -> dict:
    return fingerprint(
        response.status_code,
        response.items(),
        response.content,
        "http://testserver",
    )
