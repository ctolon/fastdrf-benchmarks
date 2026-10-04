# Benchmark report: 2026-10-03-fastdrf-0.5.0-gthread-1w

State: complete. 20 cases, profiles drf and fastdrf, 1 worker(s), 2 server start(s) per group: 40 of 40 groups complete.

## Reading this report

- `drf` is Django REST framework with its default configuration; `fastdrf` is the same API with django-fastdrf's optimizations. Both answer every case with the same status, headers and body bytes, checked before and after every sample.
- Every number is the median over independent server starts. Spread is half the range between the fastest and slowest start, relative to the median.
- Speed-up is fastdrf's requests per second divided by DRF's, at the same worker count. Above 1, fastdrf served more requests.
- CPU % is the server process tree's mean CPU (100% = one CPU). PostgreSQL and load generator columns are their CPU use relative to the CPUs they have; at 80% or more (⚠) they, rather than the server, may have limited the throughput.
- The fastdrf column says whether fastdrf compiled the output and recognized the input of the case, or left it to DRF.

## Speed-up

![Speed-up, 1 worker(s)](report/graphs/speedup-1-worker.png)

| Case | Kind | 1w DRF req/s | 1w fastdrf req/s | 1w speed-up | fastdrf |
| --- | --- | ---: | ---: | ---: | --- |
| [small](#small) | output | 2,752 | 4,183 | 1.52× | output compiled |
| [wide](#wide) | output | 1,028 | 3,614 | 3.52× | output compiled |
| [list-100](#list-100) | output | 702 | 1,802 | 2.57× | output compiled |
| [list-1000](#list-1000) | output | 98 | 374 | 3.81× | output compiled |
| [list-10000](#list-10000) | output | 11 | 37 | 3.23× | output compiled |
| [nested](#nested) | output | 1,536 | 3,375 | 2.20× | output compiled |
| [deep](#deep) | output | 775 | 2,285 | 2.95× | output compiled |
| [types](#types) | output | 480 | 1,426 | 2.97× | output compiled |
| [text-heavy](#text-heavy) | output | 1,495 | 2,131 | 1.43× | output compiled |
| [method-field](#method-field) | output | 664 | 1,346 | 2.03× | output compiled, delegated: label |
| [plain-serializer](#plain-serializer) | output | 956 | 1,039 | 1.09× | output DRF |
| [db-list](#db-list) | database | 344 | 466 | 1.35× | output compiled |
| [db-detail](#db-detail) | database | 672 | 909 | 1.35× | output compiled |
| [db-nested-list](#db-nested-list) | database | 132 | 181 | 1.38× | output compiled |
| [validate-small](#validate-small) | input | 2,804 | 4,125 | 1.47× | input compiled |
| [validate-wide](#validate-wide) | input | 1,248 | 3,468 | 2.78× | input compiled |
| [validate-nested](#validate-nested) | input | 294 | 1,516 | 5.16× | input compiled |
| [invalid](#invalid) | input | 969 | 1,067 | 1.10× | input DRF |
| [db-create](#db-create) | write | 363 | 382 | 1.05× | output compiled, input DRF |
| [db-update](#db-update) | write | 449 | 487 | 1.08× | output compiled, input DRF |

## Headroom

PostgreSQL stayed below 80% of its CPUs in every group.

oha stayed below 80% of its CPUs in every group.

## Cases

### Output of in-memory objects

#### small

One object with 5 scalar fields. `GET /out/small/`, 84 response bytes.

fastdrf: serializer `SmallSerializer`; output compiled.

![small](report/graphs/small.png)

| Profile | Workers | req/s | Spread | p50 ms | p99 ms | CPU % | PostgreSQL | oha |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| drf | 1 | 2,752 | ±5.4% | 20.49 | 74.63 | 98 | 1% | 1% |
| fastdrf | 1 | 4,183 | ±4.8% | 13.69 | 54.18 | 98 | 1% | 1% |

#### wide

One object with 50 fields: strings, integers, floats, booleans, dates, datetimes, decimals and a UUID. `GET /out/wide/`, 1,310 response bytes.

fastdrf: serializer `WideSerializer`; output compiled.

![wide](report/graphs/wide.png)

| Profile | Workers | req/s | Spread | p50 ms | p99 ms | CPU % | PostgreSQL | oha |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| drf | 1 | 1,028 | ±5.9% | 53.70 | 138.02 | 99 | 1% | 0% |
| fastdrf | 1 | 3,614 | ±1.3% | 15.73 | 61.01 | 99 | 1% | 1% |

#### list-100

100 flat objects with 10 fields each. `GET /out/list-100/`, 20,976 response bytes.

fastdrf: serializer `ItemSerializer`; output compiled.

![list-100](report/graphs/list-100.png)

| Profile | Workers | req/s | Spread | p50 ms | p99 ms | CPU % | PostgreSQL | oha |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| drf | 1 | 702 | ±1.6% | 82.29 | 164.30 | 98 | 1% | 0% |
| fastdrf | 1 | 1,802 | ±1.0% | 31.80 | 94.85 | 99 | 1% | 1% |

#### list-1000

1,000 flat objects with 10 fields each. `GET /out/list-1000/`, 210,588 response bytes.

fastdrf: serializer `ItemSerializer`; output compiled.

![list-1000](report/graphs/list-1000.png)

| Profile | Workers | req/s | Spread | p50 ms | p99 ms | CPU % | PostgreSQL | oha |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| drf | 1 | 98 | ±0.2% | 639.30 | 852.20 | 98 | 1% | 0% |
| fastdrf | 1 | 374 | ±2.3% | 162.60 | 253.23 | 99 | 1% | 0% |

#### list-10000

10,000 flat objects with 10 fields each. `GET /out/list-10000/`, 2,116,150 response bytes.

fastdrf: serializer `ItemSerializer`; output compiled.

![list-10000](report/graphs/list-10000.png)

| Profile | Workers | req/s | Spread | p50 ms | p99 ms | CPU % | PostgreSQL | oha |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| drf | 1 | 11 | ±0.8% | 5,396.00 | 6,234.87 | 99 | 1% | 0% |
| fastdrf | 1 | 37 | ±2.7% | 1,706.14 | 2,097.72 | 99 | 1% | 0% |

#### nested

An order with its customer (nested object) and 10 lines (nested list). `GET /out/nested/`, 1,113 response bytes.

fastdrf: serializer `OrderSerializer`; output compiled.

![nested](report/graphs/nested.png)

| Profile | Workers | req/s | Spread | p50 ms | p99 ms | CPU % | PostgreSQL | oha |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| drf | 1 | 1,536 | ±0.4% | 36.49 | 105.91 | 98 | 1% | 0% |
| fastdrf | 1 | 3,375 | ±0.7% | 16.85 | 64.24 | 98 | 1% | 1% |

#### deep

A tree five levels deep, three children per node: 121 nested objects. `GET /out/deep/`, 8,390 response bytes.

fastdrf: serializer `TreeSerializer`; output compiled.

![deep](report/graphs/deep.png)

| Profile | Workers | req/s | Spread | p50 ms | p99 ms | CPU % | PostgreSQL | oha |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| drf | 1 | 775 | ±1.2% | 72.66 | 155.45 | 98 | 1% | 0% |
| fastdrf | 1 | 2,285 | ±1.1% | 25.05 | 64.86 | 98 | 1% | 1% |

#### types

100 objects of datetimes in three time zones, dates, times, decimals, UUIDs, booleans, nulls, choices, integers and floats. `GET /out/types/`, 28,302 response bytes.

fastdrf: serializer `TypedSerializer`; output compiled.

![types](report/graphs/types.png)

| Profile | Workers | req/s | Spread | p50 ms | p99 ms | CPU % | PostgreSQL | oha |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| drf | 1 | 480 | ±0.0% | 123.63 | 210.75 | 99 | 1% | 0% |
| fastdrf | 1 | 1,426 | ±0.5% | 39.93 | 108.44 | 100 | 1% | 0% |

#### text-heavy

Four strings of 10,000 characters: Latin with diacritics, Greek, CJK, and a mix with emoji, escapes and line separators. `GET /out/text-heavy/`, 77,712 response bytes.

fastdrf: serializer `DocumentSerializer`; output compiled.

![text-heavy](report/graphs/text-heavy.png)

| Profile | Workers | req/s | Spread | p50 ms | p99 ms | CPU % | PostgreSQL | oha |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| drf | 1 | 1,495 | ±0.2% | 37.83 | 106.19 | 98 | 1% | 1% |
| fastdrf | 1 | 2,131 | ±1.2% | 26.71 | 84.51 | 99 | 1% | 1% |

#### method-field

The list-100 objects with a SerializerMethodField, delegated inside compiled output when enabled. `GET /out/method-field/`, 25,877 response bytes.

fastdrf: serializer `LabelledItemSerializer`; output compiled; delegated fields: label.

![method-field](report/graphs/method-field.png)

| Profile | Workers | req/s | Spread | p50 ms | p99 ms | CPU % | PostgreSQL | oha |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| drf | 1 | 664 | ±3.0% | 87.36 | 170.33 | 99 | 1% | 0% |
| fastdrf | 1 | 1,346 | ±3.7% | 42.67 | 110.50 | 99 | 1% | 0% |

#### plain-serializer

100 dictionaries through a plain Serializer, which strict parity leaves to DRF. `GET /out/plain-serializer/`, 19,285 response bytes.

fastdrf: serializer `PlainItemSerializer`; output DRF: PlainItemSerializer is not a ModelSerializer.

![plain-serializer](report/graphs/plain-serializer.png)

| Profile | Workers | req/s | Spread | p50 ms | p99 ms | CPU % | PostgreSQL | oha |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| drf | 1 | 956 | ±1.6% | 59.67 | 139.66 | 98 | 1% | 0% |
| fastdrf | 1 | 1,039 | ±3.0% | 55.55 | 130.05 | 98 | 1% | 0% |

### Output from PostgreSQL

#### db-list

A page of 20 articles with their author (foreign key) and tags (many-to-many), and the count. `GET /db/articles/`, 12,928 response bytes, 3 SQL queries per request in both profiles.

fastdrf: serializer `ArticleSerializer`; output compiled.

![db-list](report/graphs/db-list.png)

| Profile | Workers | req/s | Spread | p50 ms | p99 ms | CPU % | PostgreSQL | oha |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| drf | 1 | 344 | ±0.3% | 181.14 | 229.28 | 99 | 6% | 0% |
| fastdrf | 1 | 466 | ±0.6% | 134.64 | 170.36 | 99 | 7% | 0% |

#### db-detail

One article with its author and tags. `GET /db/articles/1/`, 632 response bytes, 2 SQL queries per request in both profiles.

fastdrf: serializer `ArticleSerializer`; output compiled.

![db-detail](report/graphs/db-detail.png)

| Profile | Workers | req/s | Spread | p50 ms | p99 ms | CPU % | PostgreSQL | oha |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| drf | 1 | 672 | ±1.3% | 93.13 | 121.31 | 98 | 5% | 0% |
| fastdrf | 1 | 909 | ±1.3% | 69.49 | 85.26 | 99 | 7% | 0% |

#### db-nested-list

10 authors, each with 10 articles and their tags (to-many, two levels). `GET /db/authors/`, 20,866 response bytes, 3 SQL queries per request in both profiles.

fastdrf: serializer `AuthorWithArticlesSerializer`; output compiled.

![db-nested-list](report/graphs/db-nested-list.png)

| Profile | Workers | req/s | Spread | p50 ms | p99 ms | CPU % | PostgreSQL | oha |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| drf | 1 | 132 | ±0.9% | 485.32 | 556.95 | 99 | 3% | 0% |
| fastdrf | 1 | 181 | ±3.1% | 348.66 | 435.58 | 100 | 4% | 0% |

### Input validation

#### validate-small

5 fields validated; the validated data is returned. `POST /in/small/`, 75 response bytes, 75 request bytes.

fastdrf: serializer `SmallInputSerializer`; input recognized.

![validate-small](report/graphs/validate-small.png)

| Profile | Workers | req/s | Spread | p50 ms | p99 ms | CPU % | PostgreSQL | oha |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| drf | 1 | 2,804 | ±3.1% | 20.10 | 72.77 | 99 | 1% | 1% |
| fastdrf | 1 | 4,125 | ±0.2% | 13.77 | 54.43 | 99 | 1% | 1% |

#### validate-wide

50 fields validated; the validated data is returned. `POST /in/wide/`, 1,304 response bytes, 1,304 request bytes.

fastdrf: serializer `WideInputSerializer`; input recognized.

![validate-wide](report/graphs/validate-wide.png)

| Profile | Workers | req/s | Spread | p50 ms | p99 ms | CPU % | PostgreSQL | oha |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| drf | 1 | 1,248 | ±2.6% | 44.62 | 117.86 | 99 | 1% | 0% |
| fastdrf | 1 | 3,468 | ±0.4% | 16.55 | 50.53 | 98 | 1% | 1% |

#### validate-nested

A batch of 100 nested lines, each with a nested object and a list, validated and returned. `POST /in/nested/`, 22,350 response bytes, 22,350 request bytes.

fastdrf: serializer `BatchSerializer`; input recognized.

![validate-nested](report/graphs/validate-nested.png)

| Profile | Workers | req/s | Spread | p50 ms | p99 ms | CPU % | PostgreSQL | oha |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| drf | 1 | 294 | ±5.0% | 212.19 | 314.25 | 99 | 1% | 0% |
| fastdrf | 1 | 1,516 | ±3.0% | 37.87 | 103.21 | 99 | 1% | 1% |

#### invalid

The wide body with 10 invalid and 3 missing fields: DRF's 400 error body. `POST /in/wide/`, 645 response bytes, 1,252 request bytes.

fastdrf: serializer `WideInputSerializer`; input DRF: the recognizer does not accept invalid input.

![invalid](report/graphs/invalid.png)

| Profile | Workers | req/s | Spread | p50 ms | p99 ms | CPU % | PostgreSQL | oha |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| drf | 1 | 969 | ±4.5% | 57.28 | 141.92 | 99 | 1% | 0% |
| fastdrf | 1 | 1,067 | ±5.6% | 53.21 | 129.66 | 99 | 1% | 0% |

### Writes to PostgreSQL

#### db-create

An article created with an author and three tags; the nested article is returned. `POST /db/articles/`, 298 response bytes, 190 request bytes, 8 SQL queries per request in both profiles.

fastdrf: serializer `ArticleSerializer`; output compiled; input DRF: ArticleSerializer.price is a DecimalField.

![db-create](report/graphs/db-create.png)

| Profile | Workers | req/s | Spread | p50 ms | p99 ms | CPU % | PostgreSQL | oha |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| drf | 1 | 363 | ±4.5% | 174.56 | 203.57 | 97 | 9% | 0% |
| fastdrf | 1 | 382 | ±6.6% | 166.68 | 199.47 | 98 | 9% | 0% |

#### db-update

A partial update of three fields; the nested article is returned. `PATCH /db/articles/2/`, 605 response bytes, 54 request bytes, 4 SQL queries per request in both profiles.

fastdrf: serializer `ArticleSerializer`; output compiled; input DRF: ArticleSerializer.price is a DecimalField.

![db-update](report/graphs/db-update.png)

| Profile | Workers | req/s | Spread | p50 ms | p99 ms | CPU % | PostgreSQL | oha |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| drf | 1 | 449 | ±1.6% | 139.47 | 177.02 | 97 | 7% | 0% |
| fastdrf | 1 | 487 | ±3.6% | 130.36 | 149.25 | 96 | 7% | 0% |

## Parameters

- Profiles: drf, fastdrf; workers: [1]; Gunicorn gthread with 8 threads per worker
- Server CPUs: [0] (one per worker); load generator CPUs: [8, 9, 10, 11, 12, 13, 14, 15]
- Repeats: 2; duration: 10 s per read sample; warmup: 2 s; requests per write sample: 2000
- Concurrency: 64; order seed: 42
- Started: 2026-10-03T19:04:07.091873+00:00; finished: 2026-10-03T19:20:59.020687+00:00
- Load generator: oha 1.16.0

## Environment

- Python: 3.14.7 (main, Sep  1 2026, 14:18:09) [Clang 22.1.3 ]; GIL enabled: True
- Host: Intel(R) Core(TM) i7-14700F, 28 logical CPUs, 123.3 GiB; CPU frequency governor: powersave
- Platform: Linux-7.0.0-31-generic-x86_64-with-glibc2.43
- Packages: Django 6.1.1, djangorestframework 3.18.1, django-fastdrf 0.5.0, msgspec 0.22.0, pydantic 2.13.5, gunicorn 26.2.0, psycopg 3.3.6
- django-fastdrf 0.5.0: source `63f32eee6b29`, installed from the package index
- Benchmark source: `0052fc4b2004` (commit 782ed4532d694b3c591a7894bd3836b3e41c9466, working tree modified)
- PostgreSQL: effective_cache_size 3GB, fsync on, max_connections 200, random_page_cost 1.1, server_version 18.6 (Debian 18.6-1.pgdg12+2), shared_buffers 512MB, synchronous_commit off, work_mem 8MB

Server commands:

- w1: `/home/ctolon/aiodrf/forks/fastdrf-benchmarks/.venv/bin/python -m gunicorn bench.wsgi:application --bind 127.0.0.1:8180 --workers 1 --worker-class gthread --threads 8 --keep-alive 5 --backlog 2048 --timeout 60 --graceful-timeout 10 --log-level warning --error-logfile - --config python:bench.gunicorn_config`

## Files

`summary.csv` holds every group's numbers; `samples.json` every sample; each case directory the load generator's output and command, the server log and the resource samples; `manifest.json` the environment, the settings of both profiles and what fastdrf does per case.
