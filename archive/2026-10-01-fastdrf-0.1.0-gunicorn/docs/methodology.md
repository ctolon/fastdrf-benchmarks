# Methodology

## The two profiles

Both profiles serve the same URLs from the same models, payloads and
database rows. `BENCH_PROFILE` selects one per server process
(`bench/settings.py`).

### drf

Django REST framework with its default configuration: no `REST_FRAMEWORK`
setting, so DRF's `JSONRenderer` and `BrowsableAPIRenderer`, its JSON, form
and multipart parsers and its default content negotiation. The views are
DRF's generic views (`RetrieveAPIView`, `ListAPIView`, `ListCreateAPIView`,
`RetrieveUpdateAPIView`, `GenericAPIView`) with `rest_framework.serializers`
classes. The database views state `select_related` and `prefetch_related`
as a careful DRF project would, so that neither profile runs more queries.

### fastdrf

The same API with django-fastdrf 0.5.0's optimizations. Each was kept only
if every case still answers DRF's exact bytes; the tests check it.

| Setting or class | Where | Why |
| --- | --- | --- |
| `SERIALIZER_BACKEND = "msgspec"` | `FASTDRF` | Output of every eligible serializer from a compiled msgspec class, and input recognition. `BENCH_SERIALIZER_BACKEND` also selects `pydantic` or `python`; Python compiles output only. |
| `SERIALIZER_BACKEND_PARITY = "strict"` | `FASTDRF` | Only output proven equal to DRF's is compiled. `fast` parity changes decimal formatting and other values, so it cannot meet the byte-identity rule. |
| `SERIALIZER_BACKEND_FALLBACK = "drf"` | `FASTDRF` | `plain-serializer` is left to DRF in strict parity. The tests switch this to `error` to prove the other output cases compile. |
| `DELEGATE_FIELDS = True` | `FASTDRF` | Compile the model fields of `method-field`, then run its original `label` method. `BENCH_DELEGATE_FIELDS=0` selects the earlier whole-serializer fallback. |
| `CACHE_SERIALIZER_FIELDS = True`, `FIELD_COPY_MODE = "compiled"` | `FASTDRF` | Fields built once per serializer class and copied with a generated plan instead of DRF's per-instance construction and `deepcopy`. |
| `BATCH_RELATED_LOOKUPS = False` | `FASTDRF` | Off on purpose. It would look up the three `tag_ids` of `db-create` in one query instead of three, and the benchmark compares the two profiles at the same SQL. |
| `FETCH_MODE = "peers"` | `FASTDRF` | fastdrf's recommended safety net for lazily loaded relations. No case loads one, and the tests show the SQL is unchanged. |
| `fastdrf.serializers` bases with `default_list_serializer_class = fastdrf.list_serializers.ListSerializer` | serializers | The compiled backend applies to fastdrf's bases; the list serializer binds its child weakly, so reference counting frees a response's objects. |
| `Meta.auto_prefetch = True` with `QueryOptimizationMixin` | serializers, views | Derives `select_related("author")`, `prefetch_related("tags")` and `prefetch_related("articles__tags")` from the nested fields: the same statements the DRF views state. |
| `DispatchOptimizationMixin` | views | Keeps content negotiation and request construction between requests, resolves `DataResponse`, and answers with a `Response` that releases its request objects when closed. |
| `DataResponse` | views of single objects, lists without pagination, validation | Rendered straight into an `HttpResponse`, without DRF's template response; status, headers and bytes are DRF's. The paginated `db-list` and the error responses keep DRF's response class. |
| `fastdrf.mixins.CreateModelMixin`, `UpdateModelMixin` | `db-create`, `db-update` | The saved object is produced with the compiled encoder of the serializer's class. |
| `MsgspecJSONRenderer`, `MsgspecJSONParser` | views | msgspec's encoder and decoder, with DRF's form parsers and the browsable API kept, so the `Vary` header is DRF's too. Its documented differences from DRF's encoder concern values no case contains ([cases](cases.md#renderer)); fastdrf's kept-encoder `JSONRenderer` would be the choice for data that has them. |

`BENCH_JSON` can select pydantic-core, orjson, or DRF's default JSON classes
instead of msgspec, independently of the compiler. Form/upload parsers and the
browsable renderer remain present. This changes only fastdrf's profile.
All configurations retain byte equality and SQL-count checks. In fastdrf 0.5.0,
orjson cannot render the integer keys in the `invalid` case's indexed field
errors; that combination fails and must not contribute a speed-up number.
No fallback renderer is added to conceal the failure.

The checked-in report is historical (fastdrf 0.1.0 with delegation disabled).
A 0.5.0 measurement must write a new run directory with its own manifest.

`fastdrf` is in `INSTALLED_APPS` of this profile only, for its system checks.
Not used: schema serializers (`SchemaViewMixin`, msgspec `Struct` or pydantic
models as serializers), whose output and validation rules are their own and
not DRF's; `PrefetchListSerializer`, which no case needs; and the cache
codecs.

`manifest.json` records both profiles' settings, and for each case what
fastdrf does: compiled output, recognized input, or DRF with fastdrf's
reason, plus the delegated fields. The JSON transport is recorded by its
selected name and fully qualified parser/renderer classes.

## Validity

Before the measurements, `fastdrf-bench expected --write` recorded DRF's
response to every case in `bench/expected.json`: the status, the headers the
application sets (`Content-Type`, `Vary`, `Allow`), and the length and SHA-256
of the body. Absolute URLs, the pagination links, are compared with the
server's base URL replaced by the test client's.

The same expectation is checked in four places:

1. `tests/test_parity.py`: both profiles in one process, each through its own
   URLconf, with Django's test client. The database cases must also run the
   same SQL statements in both profiles, in the same order, and the number of
   queries `bench/cases.py` states (`CaptureQueriesContext`; transaction
   control statements are not counted, since SQLite logs them and PostgreSQL
   does not).
2. `tests/test_profiles.py`: each profile with its own settings, in a
   process of its own (`fastdrf-bench check --profile ...`).
3. `tests/test_http.py` (with `BENCH_HTTP_TESTS=1`): both profiles on
   Gunicorn, one and two workers, every case twice.
4. The runner, on the real server, before and after every sample (below).

A response matches only with exactly these bytes, so both profiles answer the
same bytes, status and headers; `Content-Length`, when the server sends it,
must be the body's length.

## A sample

A sample is one case, profile and worker count, measured on a fresh server:

1. For a database case, write the seeded rows again: every row is replaced
   and the key sequences restart, so a created article always gets key 101.
2. Start Gunicorn with its workers pinned to their CPUs, and wait until it
   answers and all workers have started. Check that each worker is pinned to
   its own CPU.
3. Send the case once and check the response against the expectation. For a
   write, check the database (one more article, or the updated article).
4. Warm up with oha for `--warmup` seconds; every response must have the
   expected status. Write the seeded rows again after a write case's warmup.
5. Measure with oha. Read and input cases run for `--duration` seconds;
   write cases send exactly `--write-requests` requests, so every sample
   writes the same rows. Every response must have the expected status and oha
   must report no error.
6. For a write, check that the database holds exactly the rows the requests
   wrote, then write the seeded rows again. Send the case once more and check
   the response against the expectation.
7. Stop the server's process group and check its log for tracebacks, errors
   and warnings.

A failed check makes the sample invalid. It is kept in `samples.json` and
listed in the report, and its group is not ranked.

During the measurement the runner samples the CPU and memory of the server's
process tree, reads PostgreSQL's CPU time from its container's cgroup, and
records oha's CPU time.

## Order and repetitions

For each repetition and case, the order of the configurations (profile and
worker count) is shuffled with a recorded seed (`--seed`), so that a slow
drift of the host does not favour one profile. A group's result is the median
over its repetitions; the report's spread is half the range between the
fastest and slowest repetition, relative to the median. Two or three
repetitions show whether a difference is larger than the variation between
server starts; they are not a confidence interval.

## Server

Gunicorn 26 with the `gthread` worker, 1 or 4 workers, 8 threads per worker
(`--threads`), keep-alive 5 seconds, so oha's connections stay open. Each
worker serves its requests on one CPU, so the threads interleave under the
GIL: they overlap the database round trips of the database cases, and add
nothing to CPU-bound cases, where the requests wait in the worker's queue
instead (with 64 connections and 8 threads, latency includes that wait).
The same threads and settings serve both profiles. The exact command is in
`manifest.json`.

Django runs without middleware, with `DEBUG = False`, `USE_TZ = True` and
`TIME_ZONE = "Europe/Istanbul"`. Database connections are persistent
(`CONN_MAX_AGE = None`), one per thread.

## CPU layout

The server, the load generator and PostgreSQL do not share CPUs, and a server
of N workers runs on exactly N CPUs, one per worker. The default layout is
for a host with 8 performance cores (SMT, CPUs 0–15) and 12 efficiency cores
(CPUs 16–27), such as an Intel Core i7-14700F:

| CPUs | Used by |
| --- | --- |
| 0, 2, 4, 6 | The server: worker i on the i-th CPU (`SERVER_CPUS`) |
| 1, 3, 5, 7 | Idle: the SMT siblings of the server CPUs |
| 8–15 | oha, one thread per CPU (`LOAD_CPUS`) |
| 16–19 | PostgreSQL (`BENCH_PG_CPUS`) |

Gunicorn's master is started with `taskset` on the server CPUs, and each
worker pins itself to one of them after the fork (`bench/gunicorn_config.py`).
On another host, give the server one physical core per worker for the largest
worker count, the load generator about as many, and PostgreSQL the rest. The
manifest records the layout of every run. Processes outside the benchmark are
not confined; run on a quiet host.

## PostgreSQL

PostgreSQL 18 runs in Docker Compose (`compose.yaml`, project
`fastdrf-benchmarks`, port 55451) on its own CPUs, with
`synchronous_commit = off`: a commit does not wait for its WAL flush, so the
write cases measure the frameworks rather than the disk, in both profiles.
The report marks a group where PostgreSQL used 80% or more of its CPUs; at
that level the database, rather than the server, may have set the
throughput. The same mark applies to oha.

## The load

oha keeps `--concurrency` requests in flight (a closed loop, 64 by default)
over HTTP/1.1 keep-alive connections without compression. Throughput and
latency are measured together, and the latency percentiles are those of the
completed requests. It is not a fixed-arrival-rate test, and latencies are
not corrected for coordinated omission. A request slower than 15 seconds
counts as an error.

## Limits

- One host runs the server, the load generator and PostgreSQL. Results
  depend on the CPU, the kernel and the configuration; compare the profiles
  within a run, not across runs on different hosts.
- No middleware, sessions, authentication, TLS or compression: the
  measurement is the server, DRF and fastdrf.
- The output cases without a database represent instances of unmanaged
  models built in memory. Real views usually load them from a database, as
  the PostgreSQL cases do.
- The payloads avoid values that msgspec's renderer writes differently from
  DRF's (`timedelta`, `bytes`, non-finite floats, raw decimals, floats with
  an exponent). An API that returns such values needs fastdrf's kept-encoder
  `JSONRenderer` instead, which these measurements do not cover.
- One Python, CPython 3.14 with the GIL. Free-threaded Python and other
  servers are not measured.
