"""A record of the host, the Python environment and the source of a run."""

import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def tree_digest(directory: Path, pattern: str = "*.py") -> str:
    """SHA-256 over the relative paths and contents of matching files."""
    digest = hashlib.sha256()
    for path in sorted(directory.rglob(pattern)):
        relative = path.relative_to(directory)
        if any(
            part.startswith(".") or part == "__pycache__" for part in relative.parts
        ):
            continue
        digest.update(relative.as_posix().encode() + b"\0" + path.read_bytes() + b"\0")
    return digest.hexdigest()


def git_state(directory: Path) -> dict:
    """The commit and working tree state, if ``directory`` is a repository's root."""

    def git(*arguments):
        result = subprocess.run(
            ["git", "-C", str(directory), *arguments],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.stdout.strip() if result.returncode == 0 else None

    try:
        if git("rev-parse", "--show-toplevel") != str(directory):
            return {"git_head": None, "git_dirty": None}
        return {
            "git_head": git("rev-parse", "HEAD"),
            "git_dirty": bool(git("status", "--porcelain")),
        }
    except FileNotFoundError:
        return {"git_head": None, "git_dirty": None}


def fastdrf_record() -> dict:
    """The installed django-fastdrf: version, origin and a digest of its files."""
    distribution = importlib.metadata.distribution("django-fastdrf")
    import fastdrf

    package = Path(fastdrf.__file__).resolve().parent
    direct_url = distribution.read_text("direct_url.json")
    return {
        "version": distribution.version,
        "location": str(package),
        # Absent for an install from an index (PyPI); a URL or path otherwise.
        "direct_url": json.loads(direct_url) if direct_url else None,
        "source_sha256": tree_digest(package),
        "record_sha256": hashlib.sha256(
            (distribution.read_text("RECORD") or "").encode()
        ).hexdigest(),
    }


def _read(path: str) -> str | None:
    try:
        return Path(path).read_text().strip()
    except OSError:
        return None


def _cpu_model() -> str | None:
    for line in (_read("/proc/cpuinfo") or "").splitlines():
        if line.startswith("model name"):
            return line.partition(":")[2].strip()
    return platform.processor() or None


def _memory_gib() -> float | None:
    for line in (_read("/proc/meminfo") or "").splitlines():
        if line.startswith("MemTotal:"):
            return round(int(line.split()[1]) / 1024**2, 1)
    return None


def snapshot() -> dict:
    return {
        "python": sys.version,
        "gil_enabled": sys._is_gil_enabled(),
        "platform": platform.platform(),
        "cpu_model": _cpu_model(),
        "cpu_count": os.cpu_count(),
        "cpu_governor": _read("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor"),
        "memory_gib": _memory_gib(),
        "packages": {
            item.metadata["Name"]: item.version
            for item in sorted(
                importlib.metadata.distributions(),
                key=lambda item: item.metadata["Name"].lower(),
            )
        },
        "fastdrf": fastdrf_record(),
        "benchmark": {
            "path": str(ROOT),
            "python_sha256": tree_digest(ROOT / "bench"),
            **git_state(ROOT),
        },
    }
