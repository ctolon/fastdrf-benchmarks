"""Validate samples, aggregate them per group and write the report of a run."""

import csv
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

from bench.cases import CASES, KINDS, PROFILES

# At or above this CPU utilization PostgreSQL or the load generator may have
# limited the throughput, rather than the server under test.
BUSY = 0.8
PACKAGES = (
    "Django",
    "djangorestframework",
    "django-fastdrf",
    "msgspec",
    "pydantic",
    "gunicorn",
    "psycopg",
)
METRICS = ("rps", "p50_ms", "p99_ms", "cpu_mean_percent", "rss_peak_mib")


def normalize(raw: dict, *, status: int, expected_requests: int | None = None) -> dict:
    """oha's result as numbers; raise unless every request got ``status``."""
    summary, counts = raw["summary"], raw["statusCodeDistribution"]
    successful = counts.get(str(status), 0)
    if (
        raw.get("errorDistribution")
        or set(counts) != {str(status)}
        or successful <= 0
        or summary["successRate"] != 1
    ):
        raise ValueError(
            f"The load had errors or unexpected statuses: {counts}, {raw.get('errorDistribution')}"
        )
    if expected_requests is not None and successful != expected_requests:
        raise ValueError(
            f"{successful} requests completed instead of {expected_requests}"
        )
    percentiles = raw["latencyPercentiles"]
    result = {
        "requests": successful,
        "rps": summary["requestsPerSec"],
        "elapsed_seconds": summary["total"],
        "p50_ms": percentiles["p50"] * 1000,
        "p99_ms": percentiles["p99"] * 1000,
    }
    if any(not math.isfinite(value) or value < 0 for value in result.values()):
        raise ValueError("The load result has non-finite or negative numbers")
    return result


def _median(values):
    values = [value for value in values if isinstance(value, (int, float))]
    return statistics.median(values) if values else None


def aggregate(directory: Path) -> tuple[dict, list[dict]]:
    """One row per case, profile and worker count: medians over the repeats."""
    manifest = json.loads((directory / "manifest.json").read_text())
    records = json.loads((directory / "samples.json").read_text())
    parameters = manifest["parameters"]
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for case in parameters.get("cases") or [r["case"] for r in records]:
        for profile in parameters.get("profiles", PROFILES):
            for workers in parameters.get("workers", [1]):
                groups[case, profile, workers] = []
    for record in records:
        groups[record["case"], record["profile"], record["workers"]].append(record)
    rows = []
    for (case, profile, workers), samples in groups.items():
        valid = [sample for sample in samples if sample["valid"]]
        complete = len(valid) == len(samples) == parameters.get("repeats", len(samples))
        row = {
            "case": case,
            "profile": profile,
            "workers": workers,
            "valid_samples": len(valid),
            "complete": complete,
        }
        for metric in METRICS:
            row[metric] = _median(s.get(metric) for s in valid) if complete else None
        rates = [sample["rps"] for sample in valid]
        row["rps_min"] = min(rates) if complete else None
        row["rps_max"] = max(rates) if complete else None
        row["postgres_utilization"] = (
            _median(
                (s.get("service_cpu") or {}).get("postgres", {}).get("utilization")
                for s in valid
            )
            if complete
            else None
        )
        row["load_utilization"] = (
            _median((s.get("load_cpu") or {}).get("utilization") for s in valid)
            if complete
            else None
        )
        rows.append(row)
    return manifest, rows


def speedups(rows: list[dict]) -> list[dict]:
    """fastdrf's throughput and latency relative to DRF's, per case and worker count."""
    by = {(r["case"], r["profile"], r["workers"]): r for r in rows}
    result = []
    for (case, profile, workers), fast in by.items():
        if profile != "fastdrf":
            continue
        drf = by.get((case, "drf", workers))
        if not drf or not (fast["rps"] and drf["rps"]):
            continue
        result.append(
            {
                "case": case,
                "workers": workers,
                "drf_rps": drf["rps"],
                "fastdrf_rps": fast["rps"],
                "speedup": fast["rps"] / drf["rps"],
                "p50_ratio": drf["p50_ms"] / fast["p50_ms"] if fast["p50_ms"] else None,
                "p99_ratio": drf["p99_ms"] / fast["p99_ms"] if fast["p99_ms"] else None,
            }
        )
    return result


def _fmt(value, digits=0, suffix="") -> str:
    if not isinstance(value, (int, float)):
        return "—"
    return f"{value:,.{digits}f}{suffix}"


def _spread(row) -> str:
    if not (row["rps"] and row["rps_min"] is not None):
        return "—"
    return f"±{(row['rps_max'] - row['rps_min']) / 2 / row['rps'] * 100:.1f}%"


def _utilization(value) -> str:
    if not isinstance(value, (int, float)):
        return "—"
    return f"{value * 100:.0f}%" + (" ⚠" if value >= BUSY else "")


def _environment(manifest: dict) -> list[str]:
    parameters = manifest["parameters"]
    environment = manifest.get("environment") or {}
    packages = environment.get("packages", {})
    fastdrf = environment.get("fastdrf") or {}
    lines = [
        "## Parameters",
        "",
        f"- Profiles: {', '.join(parameters.get('profiles', []))}; workers: {parameters.get('workers')}; "
        f"Gunicorn gthread with {parameters.get('threads')} threads per worker",
        f"- Server CPUs: {parameters.get('server_cpus') or 'not pinned'} (one per worker); "
        f"load generator CPUs: {parameters.get('load_cpus') or 'not pinned'}",
        f"- Repeats: {parameters.get('repeats')}; duration: {parameters.get('duration')} s per read sample; "
        f"warmup: {parameters.get('warmup')} s; requests per write sample: {parameters.get('write_requests')}",
        f"- Concurrency: {parameters.get('concurrency')}; order seed: {parameters.get('seed')}",
        f"- Started: {manifest.get('started_at', '—')}; finished: {manifest.get('finished_at', '—')}",
    ]
    if manifest.get("oha_version"):
        lines.append(f"- Load generator: {manifest['oha_version']}")
    if environment:
        lines += [
            "",
            "## Environment",
            "",
            f"- Python: {environment.get('python', '—')}; GIL enabled: {environment.get('gil_enabled', '—')}",
            f"- Host: {environment.get('cpu_model') or '—'}, {environment.get('cpu_count', '—')} logical CPUs, "
            f"{environment.get('memory_gib') or '—'} GiB; CPU frequency governor: {environment.get('cpu_governor') or '—'}",
            f"- Platform: {environment.get('platform', '—')}",
            "- Packages: "
            + ", ".join(
                f"{name} {packages[name]}" for name in PACKAGES if name in packages
            ),
            f"- django-fastdrf {fastdrf.get('version', '—')}: source "
            f"`{(fastdrf.get('source_sha256') or '')[:12]}`, "
            + (
                f"installed from {fastdrf['direct_url'].get('url')}"
                if fastdrf.get("direct_url")
                else "installed from the package index"
            ),
        ]
        benchmark = environment.get("benchmark") or {}
        state = {True: "modified", False: "clean", None: "unknown"}[
            benchmark.get("git_dirty")
        ]
        lines.append(
            f"- Benchmark source: `{benchmark.get('python_sha256', '')[:12]}` "
            f"(commit {benchmark.get('git_head') or 'none'}, working tree {state})"
        )
    postgres = manifest.get("postgres") or {}
    if postgres:
        lines.append(
            "- PostgreSQL: "
            + ", ".join(f"{key} {value}" for key, value in postgres.items())
        )
    if manifest.get("server_commands"):
        lines += ["", "Server commands:", ""]
        lines += [
            f"- {name}: `{' '.join(command)}`"
            for name, command in sorted(manifest["server_commands"].items())
        ]
    return lines + [""]


def write_report(directory: Path) -> None:
    """REPORT.md, summary.csv and graphs/ of a run directory."""
    from bench.visualize import case_chart, speedup_chart

    manifest, rows = aggregate(directory)
    parameters = manifest["parameters"]
    ratios = speedups(rows)
    with (directory / "summary.csv").open("w", newline="") as output:
        fields = [*rows[0], "speedup"] if rows else ["case"]
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        by_ratio = {(r["case"], r["workers"]): r["speedup"] for r in ratios}
        for row in rows:
            writer.writerow(
                {
                    **row,
                    "speedup": by_ratio.get((row["case"], row["workers"]))
                    if row["profile"] == "fastdrf"
                    else None,
                }
            )
    graphs = directory / "graphs"
    graphs.mkdir(exist_ok=True)
    counts = sorted({row["workers"] for row in rows})
    cases = list(dict.fromkeys(row["case"] for row in rows))
    complete = sum(row["complete"] for row in rows)
    caption = (
        f"median of {parameters.get('repeats')} server start(s), "
        f"{parameters.get('duration')} s per read sample, "
        f"{parameters.get('concurrency')} connections"
    )
    case_info = manifest.get("cases") or {}
    lines = [
        f"# Benchmark report: {directory.name}",
        "",
        f"State: {manifest['state']}. {len(cases)} cases, profiles "
        f"{' and '.join(parameters.get('profiles', PROFILES))}, "
        f"{', '.join(map(str, counts))} worker(s), {parameters.get('repeats')} "
        f"server start(s) per group: {complete} of {len(rows)} groups complete.",
        "",
        "## Reading this report",
        "",
        "- `drf` is Django REST framework with its default configuration; `fastdrf` is the same API with django-fastdrf's optimizations. "
        "Both answer every case with the same status, headers and body bytes, checked before and after every sample.",
        "- Every number is the median over independent server starts. Spread is half the range between the fastest and slowest start, relative to the median.",
        "- Speed-up is fastdrf's requests per second divided by DRF's, at the same worker count. Above 1, fastdrf served more requests.",
        "- CPU % is the server process tree's mean CPU (100% = one CPU). PostgreSQL and load generator columns are their CPU use relative to the CPUs they have; "
        f"at {BUSY:.0%} or more (⚠) they, rather than the server, may have limited the throughput.",
        "- The fastdrf column says whether fastdrf compiled the output and recognized the input of the case, or left it to DRF.",
        "",
        "## Speed-up",
        "",
    ]
    for count in counts:
        stem = speedup_chart(graphs, ratios, count, caption)
        if stem:
            lines += [f"![Speed-up, {count} worker(s)](graphs/{stem}.png)", ""]
    ratio_by = {(r["case"], r["workers"]): r for r in ratios}
    row_by = {(r["case"], r["profile"], r["workers"]): r for r in rows}
    header = "| Case | Kind |"
    rule = "| --- | --- |"
    for count in counts:
        header += f" {count}w DRF req/s | {count}w fastdrf req/s | {count}w speed-up |"
        rule += " ---: | ---: | ---: |"
    lines += [header + " fastdrf |", rule + " --- |"]
    for case in cases:
        cells = f"| [{case}](#{case}) | {CASES[case].kind if case in CASES else '—'} |"
        for count in counts:
            ratio = ratio_by.get((case, count))
            drf = row_by.get((case, "drf", count)) or {}
            fast = row_by.get((case, "fastdrf", count)) or {}
            cells += (
                f" {_fmt(drf.get('rps'))} | {_fmt(fast.get('rps'))} |"
                f" {_fmt(ratio['speedup'], 2, '×') if ratio else '—'} |"
            )
        lines.append(
            cells + f" {_path_summary(case_info.get(case, {}).get('fastdrf'))} |"
        )
    lines += _headroom(rows)
    lines += ["", "## Cases", ""]
    for kind, title in KINDS.items():
        selected = [
            case for case in cases if case in CASES and CASES[case].kind == kind
        ]
        if not selected:
            continue
        lines += [f"### {title}", ""]
        for case in selected:
            lines += _case_section(case, rows, counts, case_info.get(case, {}))
            case_chart(graphs, case, [r for r in rows if r["case"] == case], caption)
    lines += _failures(directory)
    lines += _environment(manifest)
    lines += [
        "## Files",
        "",
        "`summary.csv` holds every group's numbers; `samples.json` every sample; each case directory "
        "the load generator's output and command, the server log and the resource samples; "
        "`manifest.json` the environment, the settings of both profiles and what fastdrf does per case.",
    ]
    (directory / "REPORT.md").write_text("\n".join(lines) + "\n")


def _path_summary(path: dict | None) -> str:
    if not path:
        return "—"
    parts = []
    for key in ("output", "input"):
        if key in path:
            parts.append(
                f"{key} compiled"
                if path[key] in ("compiled", "recognized")
                else f"{key} DRF"
            )
    return ", ".join(parts)


def _headroom(rows: list[dict]) -> list[str]:
    lines = ["", "## Headroom", ""]
    busy_database = [
        r
        for r in rows
        if isinstance(r["postgres_utilization"], (int, float))
        and r["postgres_utilization"] >= BUSY
    ]
    busy_load = [
        r
        for r in rows
        if isinstance(r["load_utilization"], (int, float))
        and r["load_utilization"] >= BUSY
    ]
    if busy_database:
        lines += [
            f"PostgreSQL used {BUSY:.0%} or more of its CPUs in these groups:",
            "",
        ]
        lines += [
            f"- {r['case']}: {r['profile']}, {r['workers']}w ({r['postgres_utilization'] * 100:.0f}%)"
            for r in busy_database
        ]
    else:
        lines.append(f"PostgreSQL stayed below {BUSY:.0%} of its CPUs in every group.")
    lines.append("")
    if busy_load:
        lines += [f"oha used {BUSY:.0%} or more of its CPUs in these groups:", ""]
        lines += [
            f"- {r['case']}: {r['profile']}, {r['workers']}w ({r['load_utilization'] * 100:.0f}%)"
            for r in busy_load
        ]
    else:
        lines.append(f"oha stayed below {BUSY:.0%} of its CPUs in every group.")
    return lines


def _case_section(
    case: str, rows: list[dict], counts: list[int], info: dict
) -> list[str]:
    known = CASES.get(case)
    path = info.get("fastdrf") or {}
    lines = [f"#### {case}", ""]
    if known:
        lines += [
            f"{known.description}. `{known.method} {known.path}`, "
            f"{_fmt(info.get('response_bytes'))} response bytes"
            + (
                f", {_fmt(info.get('request_bytes'))} request bytes"
                if info.get("request_bytes")
                else ""
            )
            + (
                f", {known.queries} SQL queries per request in both profiles"
                if known.queries
                else ""
            )
            + ".",
            "",
        ]
    if path:
        lines += [
            f"fastdrf: serializer `{path.get('serializer')}`"
            + "".join(
                f"; {key} {path[key]}" for key in ("output", "input") if key in path
            )
            + ".",
            "",
        ]
    lines += [
        f"![{case}](graphs/{case}.png)",
        "",
        "| Profile | Workers | req/s | Spread | p50 ms | p99 ms | CPU % | PostgreSQL | oha |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for count in counts:
        for profile in PROFILES:
            row = next(
                (
                    r
                    for r in rows
                    if r["case"] == case
                    and r["profile"] == profile
                    and r["workers"] == count
                ),
                None,
            )
            if row is None:
                continue
            if not row["complete"]:
                lines.append(
                    f"| {profile} | {count} | invalid | — | — | — | — | — | — |"
                )
                continue
            lines.append(
                f"| {profile} | {count} | {_fmt(row['rps'])} | {_spread(row)} | "
                f"{_fmt(row['p50_ms'], 2)} | {_fmt(row['p99_ms'], 2)} | "
                f"{_fmt(row['cpu_mean_percent'])} | {_utilization(row['postgres_utilization'])} | "
                f"{_utilization(row['load_utilization'])} |"
            )
    return lines + [""]


def _failures(directory: Path) -> list[str]:
    records = json.loads((directory / "samples.json").read_text())
    failures = [r for r in records if not r.get("valid")]
    if not failures:
        return []
    lines = [
        "## Failed samples",
        "",
        "| Case | Profile | Workers | Repeat | Error |",
        "| --- | --- | ---: | ---: | --- |",
    ]
    for record in failures:
        error = (
            str(record.get("error", "")).replace("|", "\\|").replace("\n", " ")[:300]
        )
        lines.append(
            f"| {record['case']} | {record['profile']} | {record['workers']} | {record['repeat']} | {error} |"
        )
    return lines + [""]
