# Contributing

Issues and pull requests are welcome: a JSON shape or workload the cases do
not cover, a DRF view that is not written the way a careful DRF project
would write it, a fastdrf option used in a way its documentation does not
recommend, or a flaw in the method.

Continuous integration runs the lint and the tests that need no services. On
a pull request from a contributor it starts after a maintainer approves the
run.

## Development environment

```sh
uv venv --python 3.14 .venv
uv pip sync --python .venv/bin/python requirements.lock
uv pip install --python .venv/bin/python --no-deps -e .
uv pip install --python .venv/bin/python --group dev
```

After changing the dependencies in `pyproject.toml`, regenerate
`requirements.lock` with the command at its top.

## Tests

```sh
.venv/bin/ruff check .
.venv/bin/ruff format --check .
BENCH_DATABASE=sqlite .venv/bin/pytest -q
```

With PostgreSQL running, the same tests run against it (leave out
`BENCH_DATABASE`), and the real-server tests start both profiles on
Gunicorn:

```sh
docker compose -p fastdrf-benchmarks up -d --wait
.venv/bin/pytest -q
BENCH_HTTP_TESTS=1 .venv/bin/pytest -q tests/test_http.py
```

They rewrite the benchmark rows; do not run them during a measurement.

## Adding a case

1. Add the data to `bench/api/payloads.py`, built from a fixed seed, and a
   model to `bench/api/models.py` if it needs one (`makemigrations`).
2. Write the serializer twice: in `bench/api/drf/serializers.py` with DRF's
   classes, and in `bench/api/fast/serializers.py` with fastdrf's. Route it in
   `bench/api/routes.py`; both profiles' views take it from there.
3. Add the request to `CASES` in `bench/cases.py`, with the number of SQL
   queries for a database case.
4. Record DRF's response with `fastdrf-bench expected --write` and check
   the diff of `bench/expected.json`: only the new case may change.
5. Run the tests, which check both profiles against it, and describe the
   case in `docs/cases.md`.

If the fastdrf profile cannot answer DRF's bytes for a case, do not change
the expectation or the comparison: report the difference, and leave that
option out of the profile.

## Results

When a pull request claims a difference, attach the run directory's
`REPORT.md`, `summary.csv`, `samples.json` and `manifest.json`, with the
exact command. Compare profiles measured in the same run; numbers from
different hosts or runs are not comparable. Keep invalid samples in the
results.
