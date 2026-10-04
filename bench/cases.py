"""The benchmark cases: one HTTP request each, the same in both profiles."""

import json
from dataclasses import dataclass
from functools import cached_property
from importlib import import_module

PROFILES = ("drf", "fastdrf")

# Kinds of case.
OUTPUT = "output"  # GET of in-memory objects: serializer and renderer only
DATABASE = "database"  # GET of PostgreSQL rows
INPUT = "input"  # POST validated without a database
WRITE = "write"  # POST or PATCH that writes to PostgreSQL


@dataclass(frozen=True)
class Case:
    name: str
    kind: str
    method: str
    path: str
    status: int
    description: str
    # The function of bench.api.payloads that returns the request body.
    body: str | None = None
    # SQL queries per request, the same in both profiles; None for the cases
    # without a database.
    queries: int | None = None

    @property
    def uses_database(self) -> bool:
        return self.kind in (DATABASE, WRITE)

    @property
    def writes(self) -> bool:
        return self.kind == WRITE

    @cached_property
    def body_bytes(self) -> bytes | None:
        """The request body: compact UTF-8 JSON, the same bytes for both profiles."""
        if self.body is None:
            return None
        payloads = import_module("bench.api.payloads")
        return json.dumps(
            getattr(payloads, self.body)(), separators=(",", ":"), ensure_ascii=False
        ).encode()


CASES = {
    case.name: case
    for case in (
        Case(
            "small",
            OUTPUT,
            "GET",
            "/out/small/",
            200,
            "One object with 5 scalar fields",
        ),
        Case(
            "wide",
            OUTPUT,
            "GET",
            "/out/wide/",
            200,
            "One object with 50 fields: strings, integers, floats, booleans, dates, datetimes, decimals and a UUID",
        ),
        Case(
            "list-100",
            OUTPUT,
            "GET",
            "/out/list-100/",
            200,
            "100 flat objects with 10 fields each",
        ),
        Case(
            "list-1000",
            OUTPUT,
            "GET",
            "/out/list-1000/",
            200,
            "1,000 flat objects with 10 fields each",
        ),
        Case(
            "list-10000",
            OUTPUT,
            "GET",
            "/out/list-10000/",
            200,
            "10,000 flat objects with 10 fields each",
        ),
        Case(
            "nested",
            OUTPUT,
            "GET",
            "/out/nested/",
            200,
            "An order with its customer (nested object) and 10 lines (nested list)",
        ),
        Case(
            "deep",
            OUTPUT,
            "GET",
            "/out/deep/",
            200,
            "A tree five levels deep, three children per node: 121 nested objects",
        ),
        Case(
            "types",
            OUTPUT,
            "GET",
            "/out/types/",
            200,
            "100 objects of datetimes in three time zones, dates, times, decimals, UUIDs, booleans, nulls, choices, integers and floats",
        ),
        Case(
            "text-heavy",
            OUTPUT,
            "GET",
            "/out/text-heavy/",
            200,
            "Four strings of 10,000 characters: Latin with diacritics, Greek, CJK, and a mix with emoji, escapes and line separators",
        ),
        Case(
            "method-field",
            OUTPUT,
            "GET",
            "/out/method-field/",
            200,
            "The list-100 objects with a SerializerMethodField, delegated inside compiled output when enabled",
        ),
        Case(
            "plain-serializer",
            OUTPUT,
            "GET",
            "/out/plain-serializer/",
            200,
            "100 dictionaries through a plain Serializer, which strict parity leaves to DRF",
        ),
        Case(
            "db-list",
            DATABASE,
            "GET",
            "/db/articles/",
            200,
            "A page of 20 articles with their author (foreign key) and tags (many-to-many), and the count",
            queries=3,
        ),
        Case(
            "db-detail",
            DATABASE,
            "GET",
            "/db/articles/1/",
            200,
            "One article with its author and tags",
            queries=2,
        ),
        Case(
            "db-nested-list",
            DATABASE,
            "GET",
            "/db/authors/",
            200,
            "10 authors, each with 10 articles and their tags (to-many, two levels)",
            queries=3,
        ),
        Case(
            "validate-small",
            INPUT,
            "POST",
            "/in/small/",
            200,
            "5 fields validated; the validated data is returned",
            body="small_input",
        ),
        Case(
            "validate-wide",
            INPUT,
            "POST",
            "/in/wide/",
            200,
            "50 fields validated; the validated data is returned",
            body="wide_input",
        ),
        Case(
            "validate-nested",
            INPUT,
            "POST",
            "/in/nested/",
            200,
            "A batch of 100 nested lines, each with a nested object and a list, validated and returned",
            body="nested_input",
        ),
        Case(
            "invalid",
            INPUT,
            "POST",
            "/in/wide/",
            400,
            "The wide body with 10 invalid and 3 missing fields: DRF's 400 error body",
            body="invalid_input",
        ),
        Case(
            "db-create",
            WRITE,
            "POST",
            "/db/articles/",
            201,
            "An article created with an author and three tags; the nested article is returned",
            body="create_input",
            queries=8,
        ),
        Case(
            "db-update",
            WRITE,
            "PATCH",
            "/db/articles/2/",
            200,
            "A partial update of three fields; the nested article is returned",
            body="update_input",
            queries=4,
        ),
    )
}

KINDS = {
    OUTPUT: "Output of in-memory objects",
    DATABASE: "Output from PostgreSQL",
    INPUT: "Input validation",
    WRITE: "Writes to PostgreSQL",
}


def selected(names: list[str] | None) -> list[Case]:
    return [CASES[name] for name in (names or CASES)]
