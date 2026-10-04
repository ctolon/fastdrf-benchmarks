# Cases

Every case is one HTTP request, sent with the same method, path and body to
both profiles. The `drf` profile's views are in `bench/api/drf/`, the
`fastdrf` profile's in `bench/api/fast/`; `bench/api/routes.py` gives them the
same URLs, and `bench/cases.py` defines the requests.

All data is deterministic. The in-memory objects, request bodies and
database rows are built by `bench/api/payloads.py` from fixed seeds, so every
process, profile and run produces the same bytes. `bench/expected.json`
records the response of each case (status, headers, body length and SHA-256);
see [methodology](methodology.md#validity).

## Overview

Sizes are in bytes. The response size of `db-list` is measured with the
test client's host (`http://testserver`) in the pagination link; on the
benchmark server the link holds `http://127.0.0.1:8180`, four bytes more.
SQL is the number of queries per request, the same in both profiles.

| Case | Kind | Request | Status | Request body | Response body | SQL | fastdrf |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| `small` | output | `GET /out/small/` | 200 | — | 84 | 0 | output compiled |
| `wide` | output | `GET /out/wide/` | 200 | — | 1,310 | 0 | output compiled |
| `list-100` | output | `GET /out/list-100/` | 200 | — | 20,976 | 0 | output compiled |
| `list-1000` | output | `GET /out/list-1000/` | 200 | — | 210,588 | 0 | output compiled |
| `list-10000` | output | `GET /out/list-10000/` | 200 | — | 2,116,150 | 0 | output compiled |
| `nested` | output | `GET /out/nested/` | 200 | — | 1,113 | 0 | output compiled |
| `deep` | output | `GET /out/deep/` | 200 | — | 8,390 | 0 | output compiled |
| `types` | output | `GET /out/types/` | 200 | — | 28,302 | 0 | output compiled |
| `text-heavy` | output | `GET /out/text-heavy/` | 200 | — | 77,712 | 0 | output compiled |
| `method-field` | output | `GET /out/method-field/` | 200 | — | 25,877 | 0 | compiled output; `label` delegated |
| `plain-serializer` | output | `GET /out/plain-serializer/` | 200 | — | 19,285 | 0 | output on DRF |
| `db-list` | database | `GET /db/articles/` | 200 | — | 12,928 | 3 | output compiled |
| `db-detail` | database | `GET /db/articles/1/` | 200 | — | 632 | 2 | output compiled |
| `db-nested-list` | database | `GET /db/authors/` | 200 | — | 20,866 | 3 | output compiled |
| `validate-small` | input | `POST /in/small/` | 200 | 75 | 75 | 0 | input recognized |
| `validate-wide` | input | `POST /in/wide/` | 200 | 1,304 | 1,304 | 0 | input recognized |
| `validate-nested` | input | `POST /in/nested/` | 200 | 22,350 | 22,350 | 0 | input recognized |
| `invalid` | input | `POST /in/wide/` | 400 | 1,252 | 645 | 0 | input on DRF |
| `db-create` | write | `POST /db/articles/` | 201 | 190 | 298 | 8 | output compiled, input on DRF |
| `db-update` | write | `PATCH /db/articles/2/` | 200 | 54 | 605 | 4 | output compiled, input on DRF |

The last column is what fastdrf does in the `fastdrf` profile, as
`bench/inspection.py` reports it from fastdrf's own eligibility checks, and
as the tests confirm at run time (`tests/test_parity.py`). Every run records
it in `manifest.json`, with fastdrf's reason for each case left to DRF.

## Output of in-memory objects

These views represent objects built once per process, without a database:
the request runs DRF's dispatch, the serializer and the renderer, and
nothing else. The objects are instances of unmanaged models (no table
exists): fastdrf's strict parity compiles `ModelSerializer` output only, and
DRF represents the instances exactly as it represents rows. To-many relations
hold their items the way `prefetch_related` stores them, so the related
manager's `all()` returns them without a query.

### `small`

One `Small` object: `id`, `name`, `email`, `active`, `score`.

### `wide`

One `Wide` object of 50 fields: the id, 13 strings, 12 integers, 8 floats,
6 booleans, 3 dates, 3 datetimes, 3 decimals and a UUID. It exercises the
per-field cost of a single object.

### `list-100`, `list-1000`, `list-10000`

`Item` lists with 10 fields per item (SKU, name, quantity, decimal price,
boolean, float rating, choice, date, UUID, id), through
`ListAPIView` without pagination. They show how the per-item cost scales.

### `nested`

An `Order` with its `Customer` (a nested serializer on a foreign key) and
10 `OrderLine` items (a nested `many=True` serializer on the reverse
foreign key): two levels.

### `deep`

A `Node` tree five levels deep with three children per node (121 nodes),
with one serializer class per level.

### `types`

100 `Typed` objects with aware datetimes in UTC, Istanbul and Berlin time
(converted to the current time zone, `Europe/Istanbul`), dates, times with
and without microseconds, decimals with four places, UUIDs, booleans, null
strings and integers, text and integer choices, integers up to 2^40 and
floats.

### `text-heavy`

One `Document` with four strings of 10,000 characters: Latin letters with
diacritics, Greek, CJK, and a mix of emoji, characters outside the Basic
Multilingual Plane, quotes, backslashes, control characters and the line
separators U+2028 and U+2029, which DRF's renderer escapes.

### `method-field`

The `list-100` items with a `SerializerMethodField`. The current fastdrf
profile compiles the model fields and delegates `label` to the original
method. `BENCH_DELEGATE_FIELDS=0` leaves the whole serializer to DRF, retaining
field caching, rendering and dispatch optimizations. The manifest and report
record delegated fields so these two paths are distinguishable.

### `plain-serializer`

100 dictionaries through a plain `Serializer` (no model). In strict parity
fastdrf compiles `ModelSerializer` output only, so this output is DRF's as
well.

## Output from PostgreSQL

Ten authors, twelve tags and 100 articles (ten per author, three tags each),
with fixed keys and values. The DRF views state their lookups, as a careful
DRF project would:

- `db-list` and `db-detail`: `Article.objects.select_related("author").prefetch_related("tags")`.
- `db-nested-list`: `Author.objects.prefetch_related("articles__tags")`.

The fastdrf views use `Article.objects.all()` and `Author.objects.all()`
with `QueryOptimizationMixin`, which derives the same lookups from the
serializers' `Meta.auto_prefetch`. The tests assert that both profiles run
the same SQL statements, so the difference between them is not the queries.

### `db-list`

The first page (`PageNumberPagination`, 20 per page) of articles, each
with its nested author and tags: the count, the page joined with its
authors, and the page's tags.

### `db-detail`

Article 1 with its author and tags.

### `db-nested-list`

All ten authors, each with their ten articles (id, title, price,
datetime) and each article's tags: two levels of to-many relations.

## Input validation

The views validate the body and answer the validated data (200), or DRF's
errors (400). No database is involved.

### `validate-small`

Five fields: a string with a maximum length, a bounded integer, a boolean,
a float and a choice.

### `validate-wide`

50 fields: 14 strings, 12 bounded integers, 8 floats, 6 booleans, 4
choices, 2 UUIDs, 2 dates and 2 lists of integers.

### `validate-nested`

A batch with 100 lines; each line has seven fields, including a list of
strings, and a nested `dimensions` object of four fields.

### `invalid`

The `validate-wide` body with ten invalid values (empty and too long
strings, a word for an integer, an integer out of range, a word for a
float and for a boolean, an unknown choice, a malformed UUID, an impossible
date, a list with a string) and three missing fields. fastdrf's recognizer
does not accept it, so DRF validates it and produces the error body in
both profiles.

## Writes to PostgreSQL

### `db-create`

An article with `author_id` and three `tag_ids`; the response is the
nested article (201). The queries: the author, the three tags one at a
time, the insert, the existing links, the new links and the tags of the
response. Input recognition does not apply (the serializer has relation
and decimal fields).

### `db-update`

A `PATCH` of title, price and views of article 2; the response is the
nested article. The queries: the article with its author, its tags, the
update and the tags again (DRF clears the prefetched tags after an update).

Each write sample sends a fixed number of requests, and the rows are reset
before and after it; see [methodology](methodology.md#a-sample).

## Renderer

The `fastdrf` profile renders with `fastdrf.msgspec.renderers.MsgspecJSONRenderer`
and parses with `MsgspecJSONParser`. msgspec's encoder differs from DRF's for
`timedelta`, `bytes`, non-finite floats, raw `Decimal` values in the data
and floats written with an exponent. None of the cases contains such a value:
serializers output decimals as strings, and the floats of the payloads have
at most three decimals and lie below 100,000, which both encoders write the
same way. Every case's bytes are compared with DRF's, so a value outside these
limits would fail the tests rather than the comparison.

## Alternative JSON transports

`BENCH_JSON=pydantic` selects fastdrf's pydantic-core parser/renderer;
`orjson` selects its orjson pair; `drf` selects DRF's default JSON classes.
The default remains msgspec. Payloads, expected bytes and SQL limits do not
change with the selection. All 20 cases pass for msgspec, pydantic and DRF.
With fastdrf 0.5.0, orjson passes 19 cases but rejects the integer index keys
in `invalid`'s `ListField` error details (`TypeError: Dict key must be str`).
The runner must reject this response; it is not a valid speed-up sample.
