import json

import pytest

from bench.results import aggregate, normalize, speedups, write_report


def oha(rps=1000.0, status="200", errors=None):
    return {
        "summary": {"successRate": 1, "requestsPerSec": rps, "total": 2.0},
        "statusCodeDistribution": {status: int(rps * 2)},
        "errorDistribution": errors or {},
        "latencyPercentiles": {"p50": 0.002, "p99": 0.01},
    }


def test_normalize():
    result = normalize(oha(), status=200)
    assert result["rps"] == 1000 and result["p50_ms"] == 2 and result["p99_ms"] == 10
    with pytest.raises(ValueError):
        normalize(oha(status="500"), status=200)
    with pytest.raises(ValueError):
        normalize(oha(errors={"timeout": 1}), status=200)
    with pytest.raises(ValueError):
        normalize(oha(), status=200, expected_requests=5)


def write_run(directory, invalid=False):
    samples = []
    for repeat in (1, 2):
        for case in ("small", "db-list"):
            for profile, base in (("drf", 1000), ("fastdrf", 2500)):
                for workers in (1, 4):
                    samples.append(
                        {
                            "repeat": repeat,
                            "case": case,
                            "profile": profile,
                            "workers": workers,
                            "valid": not (invalid and repeat == 2 and profile == "drf"),
                            "rps": base * workers + repeat * 10,
                            "p50_ms": 1.0,
                            "p99_ms": 4.0,
                            "cpu_mean_percent": 99.0 * workers,
                            "service_cpu": {"postgres": {"utilization": 0.85}},
                            "load_cpu": {"utilization": 0.3},
                        }
                    )
    manifest = {
        "state": "complete",
        "parameters": {
            "cases": ["small", "db-list"],
            "profiles": ["drf", "fastdrf"],
            "workers": [1, 4],
            "repeats": 2,
            "duration": 2,
            "concurrency": 64,
        },
        "cases": {"small": {"fastdrf": {"serializer": "S", "output": "compiled"}}},
    }
    (directory / "samples.json").write_text(json.dumps(samples))
    (directory / "manifest.json").write_text(json.dumps(manifest))


def test_aggregate_and_speedup(tmp_path):
    write_run(tmp_path)
    _, rows = aggregate(tmp_path)
    assert len(rows) == 8 and all(row["complete"] for row in rows)
    small = {(r["profile"], r["workers"]): r for r in rows if r["case"] == "small"}
    assert small["drf", 1]["rps"] == 1015
    assert small["drf", 1]["rps_min"] == 1010 and small["drf", 1]["rps_max"] == 1020
    ratio = next(
        r for r in speedups(rows) if r["case"] == "small" and r["workers"] == 4
    )
    assert ratio["speedup"] == pytest.approx(10015 / 4015)


def test_invalid_group_has_no_numbers(tmp_path):
    write_run(tmp_path, invalid=True)
    _, rows = aggregate(tmp_path)
    drf = [r for r in rows if r["profile"] == "drf"]
    assert drf and all(not r["complete"] and r["rps"] is None for r in drf)
    assert not speedups(rows)


def test_report(tmp_path):
    write_run(tmp_path)
    write_report(tmp_path)
    report = (tmp_path / "REPORT.md").read_text()
    assert "| [small](#small) | output |" in report
    assert "2.49×" in report
    assert "PostgreSQL used 80% or more" in report
    assert (tmp_path / "graphs" / "speedup-1-worker.png").is_file()
    assert (tmp_path / "graphs" / "speedup-4-workers.png").is_file()
    assert (tmp_path / "graphs" / "db-list.png").is_file()
    assert (tmp_path / "summary.csv").read_text().count("\n") == 9


def test_report_identifies_delegated_output(tmp_path):
    write_run(tmp_path)
    path = tmp_path / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest["cases"]["small"]["fastdrf"]["delegated"] = ["label"]
    path.write_text(json.dumps(manifest))
    write_report(tmp_path)
    report = (tmp_path / "REPORT.md").read_text()
    assert "delegated: label" in report
    assert "delegated fields: label" in report
