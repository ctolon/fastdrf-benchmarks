# fastdrf-benchmarks

HTTP benchmarks of one API served twice: by Django REST framework with its
default configuration, and by the same code with the optimizations of
[django-fastdrf](https://github.com/ctolon/django-fastdrf). Twenty endpoints
cover JSON output of many shapes and sizes, input validation, and reads and
writes against PostgreSQL. Both servers answer every request with the same
status, headers and body bytes, checked before and after every measurement.

The benchmark environment is pinned to django-fastdrf 0.5.0. Its default
profile compiles with msgspec and enables delegated fields. JSON transport and
serializer compilation can be selected independently. The published run uses
msgspec for both compilation and JSON parsing/rendering.

| | |
| --- | --- |
| Profiles | `drf`: Django REST framework 3.18 with no `REST_FRAMEWORK` setting; `fastdrf`: the same API with django-fastdrf 0.5.0 ([settings and classes](docs/methodology.md#fastdrf)) |
| Software | CPython 3.14 (GIL build), Django 6.1, DRF 3.18, Gunicorn 26 (gthread worker), PostgreSQL 18; `requirements.lock` pins every package |
| Server | 1 Gunicorn gthread worker pinned to one CPU, 8 threads, keep-alive |
| Load | [oha](https://github.com/hatoo/oha), 64 connections, on CPUs of its own |
| Results | the median of independent server starts, with the spread between them, per case and worker count |

## Latest results

[REPORT.md](REPORT.md) is the run of 3 October 2026: **DRF defaults vs DRF
tuned with fastdrf 0.5.0 and msgspec**, both on **one Gunicorn gthread worker
with eight threads**. All 80 samples (40 groups, two independent server
starts each) passed the status, headers, body and write-integrity checks.
The median throughput spread between starts is ±1.6%.
PostgreSQL used at most 9.4% of its assigned CPUs and oha 1.1%; neither
reached the report's 80% CPU threshold.

| | |
| --- | --- |
| Host | Intel Core i7-14700F, 28 logical CPUs, 123 GiB RAM, `powersave` governor |
| Software | Linux 7.0.0, CPython 3.14.7 (GIL), Django 6.1.1, DRF 3.18.1, fastdrf 0.5.0, msgspec 0.22.0, Gunicorn 26.2.0, PostgreSQL 18.6 |
| Server | 1 gthread worker, 8 threads, CPU 0; HTTP/1.1 keep-alive |
| Load | 64 connections; 10 s per read/validation sample after 2 s warmup; 2,000 requests per write sample; 16.9 minutes total |
| fastdrf | msgspec compiler and JSON parser/renderer; strict parity; delegated fields enabled |

Throughput medians over the two starts:

| Case | DRF req/s | DRF + fastdrf req/s | Ratio |
| --- | ---: | ---: | ---: |
| `small` | 2,752 | 4,183 | 1.52× |
| `wide` | 1,028 | 3,614 | 3.52× |
| `list-100` | 702 | 1,802 | 2.57× |
| `list-1000` | 98 | 374 | 3.81× |
| `list-10000` | 11 | 37 | 3.23× |
| `nested` | 1,536 | 3,375 | 2.20× |
| `deep` | 775 | 2,285 | 2.95× |
| `types` | 480 | 1,426 | 2.97× |
| `text-heavy` | 1,495 | 2,131 | 1.43× |
| `method-field` | 664 | 1,346 | 2.03× |
| `plain-serializer` | 956 | 1,039 | 1.09× |
| `db-list` | 344 | 466 | 1.35× |
| `db-detail` | 672 | 909 | 1.35× |
| `db-nested-list` | 132 | 181 | 1.38× |
| `validate-small` | 2,804 | 4,125 | 1.47× |
| `validate-wide` | 1,248 | 3,468 | 2.78× |
| `validate-nested` | 294 | 1,516 | 5.16× |
| `invalid` | 969 | 1,067 | 1.10× |
| `db-create` | 363 | 382 | 1.05× |
| `db-update` | 449 | 487 | 1.08× |

The write-case gains are small (1.05× and 1.08×); the report includes the
spread of both profiles. Two starts do not establish statistical significance.

![Speed-up of fastdrf over DRF, 1 worker](report/graphs/speedup-1-worker.png)

The [previous results](archive/2026-10-01-fastdrf-0.1.0-gunicorn/REPORT.md)
(fastdrf 0.1.0, one and four Gunicorn workers) are archived with their
[manifest](archive/2026-10-01-fastdrf-0.1.0-gunicorn/report/manifest.json) and
[samples](archive/2026-10-01-fastdrf-0.1.0-gunicorn/report/samples.json).
Compare profiles within each run; these separate runs do not isolate the effect
of the fastdrf version. These are synchronous DRF/WSGI measurements, not ASGI.

## Cases

| Kind | Cases |
| --- | --- |
| Output of in-memory objects (serializer and renderer only) | `small` (5 fields), `wide` (50 fields), `list-100`, `list-1000`, `list-10000`, `nested` (an object with a nested object and a list of 10), `deep` (5 levels), `types` (datetimes, dates, times, decimals, UUIDs, nulls, choices), `text-heavy` (four 10,000-character Unicode strings), `method-field` (a `SerializerMethodField`), `plain-serializer` (a `Serializer` without a model) |
| Output from PostgreSQL | `db-list` (a page of 20 articles with author and tags), `db-detail`, `db-nested-list` (authors with their articles and tags) |
| Input validation | `validate-small`, `validate-wide`, `validate-nested` (100 nested items), `invalid` (DRF's 400 error body) |
| Writes to PostgreSQL | `db-create` (foreign key and many-to-many), `db-update` (partial update) |

[Cases](docs/cases.md) lists every endpoint with its request and response
sizes, its SQL and what fastdrf does for it. With the current defaults,
`method-field` compiles its model fields and delegates `label` to the original
method. `plain-serializer` stays on DRF in strict parity. Set
`BENCH_DELEGATE_FIELDS=0` to measure the old whole-serializer fallback as well.

## Running

You need Linux, Docker with Compose, [uv](https://docs.astral.sh/uv/) and
oha on the `PATH`.

```sh
uv venv --python 3.14 .venv
uv pip sync --python .venv/bin/python requirements.lock
uv pip install --python .venv/bin/python --no-deps -e .
scripts/run.sh
```

`scripts/run.sh` starts PostgreSQL (`docker compose -p fastdrf-benchmarks`,
port 55451), writes the benchmark rows, measures every case with both
profiles at 1 worker, and writes the report to `results/<run>/`.
Settings are environment variables, and further arguments go to
`fastdrf-bench run`:

| Variable | Default | Meaning |
| --- | --- | --- |
| `BENCH_SERIALIZER_BACKEND` | `msgspec` | Compiler: `msgspec`, `pydantic` or `python` |
| `BENCH_JSON` | `msgspec` | JSON parser/renderer: `msgspec`, `pydantic`, `orjson` or `drf` |
| `BENCH_DELEGATE_FIELDS` | `1` | `1`: delegate unsupported fields within compiled output; `0`: whole-serializer fallback |
| `REPEATS` | 2 | Server starts per case, profile and worker count |
| `DURATION` | 10 | Seconds per read or validation sample |
| `WARMUP` | 2 | Seconds of warmup per sample |
| `CONCURRENCY` | 64 | Requests in flight |
| `WRITE_REQUESTS` | 2000 | Requests per write sample |
| `THREADS` | 8 | Gunicorn threads per worker |
| `SERVER_CPUS` | `0` | Server CPU |
| `LOAD_CPUS` | `8-15` | oha's CPUs |
| `BENCH_PG_CPUS` | `16-19` | PostgreSQL's CPUs |
| `OUTPUT` | `results/run-<time>` | Run directory |
| `SMOKE` | 0 | 1: one start, 2 s, 1 worker, 200 writes; a check that everything runs |

```sh
scripts/run.sh --cases small list-1000 db-list
SMOKE=1 scripts/run.sh --cases small db-create
REPEATS=3 scripts/run.sh
```

For example, keep JSON transport fixed while changing the compiler:

```sh
BENCH_SERIALIZER_BACKEND=pydantic BENCH_JSON=msgspec scripts/run.sh
BENCH_SERIALIZER_BACKEND=python BENCH_JSON=msgspec scripts/run.sh
BENCH_JSON=pydantic scripts/run.sh
BENCH_JSON=orjson scripts/run.sh --cases small list-1000 method-field
BENCH_DELEGATE_FIELDS=0 scripts/run.sh --cases method-field
```

Fastdrf 0.5.0's orjson renderer cannot render the integer keys in DRF's indexed
`ListField` errors. The `invalid` case therefore returns a server error instead
of the expected 400. An all-case orjson run fails the existing parity gate;
select cases explicitly when evaluating it. The other three JSON choices pass
all 20 cases with each compiler. Expected responses and SQL requirements are
unchanged. These checks establish compatibility, not a throughput result.

The default CPU layout is for an Intel Core i7-14700F (8 performance cores,
12 efficiency cores); see [methodology](docs/methodology.md#cpu-layout) for
other hosts. Run on a quiet machine.

## Reading the results

Each run directory holds:

- `REPORT.md`: the speed-up chart per worker count, a table of every case
  with DRF's and fastdrf's requests per second and their ratio, and a section
  per case with its chart, requests per second, spread, p50 and p99 latency,
  server CPU, PostgreSQL CPU and oha CPU.
- `summary.csv`: the numbers of every group (case, profile, workers).
- `samples.json`: every sample, valid or not.
- `manifest.json`: the parameters, host, package versions, the installed
  django-fastdrf version with a digest of its source, both profiles'
  settings, the server commands, PostgreSQL's settings and what fastdrf does
  per case.
- `graphs/`: the charts.
- one directory per sample: oha's output and command, the server log and the
  resource samples.

The speed-up is fastdrf's requests per second divided by DRF's at the same
worker count. A group whose PostgreSQL or oha used 80% or more of its CPUs is
marked: there, the database or the load generator may have limited the
throughput. Numbers hold for the host and settings of the run; compare the
profiles within a run, not with runs on other machines.

## Method

[Methodology](docs/methodology.md) describes the profiles and the reason for
each fastdrf option, how parity is enforced, the steps of a sample, the CPU
layout and the limits of the measurements:

- Both profiles answer the bytes recorded in `bench/expected.json`, checked
  in-process by the tests and on the real server before and after every
  sample.
- The database cases run the same SQL statements in both profiles; the tests
  compare them.
- Every sample starts a new server; write samples send a fixed number of
  requests, and the rows are written again before and after them.
- The configuration order is shuffled per case with a recorded seed.

## Development

```sh
uv pip install --python .venv/bin/python --group dev
.venv/bin/ruff check . && .venv/bin/ruff format --check .
BENCH_DATABASE=sqlite .venv/bin/pytest -q
```

See [contributing](CONTRIBUTING.md) for the real-server tests and for adding
cases.

## License

BSD 3-Clause; see [LICENSE](LICENSE).
