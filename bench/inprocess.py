"""
Every case through Django's test client in this process: the response
fingerprint and the SQL each request runs.

Used by the tests, by ``fastdrf-bench expected`` (which records DRF's
responses as the canonical ones) and by ``fastdrf-bench check`` (which checks
one profile's real settings against them).
"""

from dataclasses import dataclass

from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext

from bench import verify
from bench.api import data
from bench.cases import Case

# Statements of transaction control, which the database backends log
# differently (SQLite logs BEGIN, PostgreSQL does not); they are not counted.
TRANSACTION_CONTROL = ("BEGIN", "COMMIT", "ROLLBACK", "SAVEPOINT", "RELEASE")


@dataclass
class Result:
    fingerprint: dict
    statements: list[str]

    @property
    def queries(self) -> int:
        return len(self.statements)


def statements(captured: CaptureQueriesContext) -> list[str]:
    return [
        query["sql"]
        for query in captured.captured_queries
        if not query["sql"].lstrip().upper().startswith(TRANSACTION_CONTROL)
    ]


def run(case: Case, client: Client | None = None) -> Result:
    """
    Send ``case`` with the test client. A database case starts from the
    seeded rows, so that a write's response is the same every time.
    """
    client = client or Client()
    if case.uses_database:
        data.seed()
    with CaptureQueriesContext(connection) as captured:
        response = verify.request_django(client, case)
    return Result(verify.django_fingerprint(response), statements(captured))
