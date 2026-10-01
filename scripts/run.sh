#!/usr/bin/env bash
# Measure every case with both profiles, one and four workers, and write the
# report: PostgreSQL in Docker Compose, a fresh Gunicorn server per sample.
#
# Settings are environment variables; extra arguments go to
# `fastdrf-bench run` (for example `--cases small wide`).
#
#   scripts/run.sh
#   REPEATS=3 DURATION=10 scripts/run.sh --cases list-1000 db-list
#   SMOKE=1 scripts/run.sh --cases small db-list
#
# The default CPU layout is for an 8 performance-core / 12 efficiency-core
# host (docs/methodology.md#cpu-layout); adapt SERVER_CPUS, LOAD_CPUS and
# BENCH_PG_CPUS to other machines.
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ "${SMOKE:-0}" == "1" ]]; then
  # A quick check that everything runs: not a measurement.
  : "${REPEATS:=1}" "${DURATION:=2}" "${WARMUP:=1}" "${WORKERS:=1}" "${WRITE_REQUESTS:=200}"
fi
REPEATS="${REPEATS:-2}"
DURATION="${DURATION:-10}"
WARMUP="${WARMUP:-2}"
CONCURRENCY="${CONCURRENCY:-64}"
WRITE_REQUESTS="${WRITE_REQUESTS:-2000}"
WORKERS="${WORKERS:-1 4}"
THREADS="${THREADS:-8}"
# One CPU per worker with their SMT siblings idle; oha on the four other
# performance cores, both SMT threads; PostgreSQL on four efficiency cores.
SERVER_CPUS="${SERVER_CPUS:-0,2,4,6}"
LOAD_CPUS="${LOAD_CPUS:-8-15}"
export BENCH_PG_CPUS="${BENCH_PG_CPUS:-16-19}"
export BENCH_PG_PORT="${BENCH_PG_PORT:-55451}"
OUTPUT="${OUTPUT:-results/run-$(date -u +%Y%m%dT%H%M%SZ)}"
BENCH="${BENCH:-.venv/bin/fastdrf-bench}"

command -v oha >/dev/null || { echo "oha is not installed (https://github.com/hatoo/oha)" >&2; exit 1; }
docker compose -p fastdrf-benchmarks up -d --wait
"$BENCH" prepare

# shellcheck disable=SC2086 # WORKERS is a list
"$BENCH" run \
  --workers $WORKERS --threads "$THREADS" \
  --repeats "$REPEATS" --duration "$DURATION" --warmup "$WARMUP" \
  --concurrency "$CONCURRENCY" --write-requests "$WRITE_REQUESTS" \
  --server-cpus "$SERVER_CPUS" --load-cpus "$LOAD_CPUS" \
  --output "$OUTPUT" "$@"
echo "Report: $OUTPUT/REPORT.md"
