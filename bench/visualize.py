"""Charts of a run: the speed-up per worker count, and the throughput per case."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from bench.cases import CASES

SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
MUTED = "#52514e"
GRID = "#e4e3df"
# One colour per profile in every chart.
COLORS = {"drf": "#eb6834", "fastdrf": "#2a78d6"}


def _style(axis) -> None:
    axis.set_facecolor(SURFACE)
    axis.grid(axis="x", color=GRID, linewidth=0.8)
    axis.set_axisbelow(True)
    axis.spines[["top", "right", "left"]].set_visible(False)
    axis.spines["bottom"].set_color(MUTED)
    axis.tick_params(colors=MUTED, labelsize=8)
    axis.tick_params(axis="y", length=0, labelcolor=TEXT)


def _save(figure, directory: Path, name: str) -> None:
    try:
        figure.savefig(
            directory / f"{name}.png", dpi=150, bbox_inches="tight", facecolor=SURFACE
        )
    finally:
        plt.close(figure)


def speedup_chart(
    directory: Path, ratios: list[dict], workers: int, caption: str
) -> str | None:
    """fastdrf's requests per second ÷ DRF's for every case; returns the file stem."""
    selected = [r for r in ratios if r["workers"] == workers]
    if not selected:
        return None
    order = {name: index for index, name in enumerate(CASES)}
    selected.sort(key=lambda r: order.get(r["case"], len(order)))
    names = [r["case"] for r in selected]
    values = [r["speedup"] for r in selected]
    figure, axis = plt.subplots(
        figsize=(8, 0.32 * len(selected) + 1.6), layout="constrained"
    )
    figure.set_facecolor(SURFACE)
    axis.barh(names, values, height=0.62, color=COLORS["fastdrf"])
    axis.axvline(1, color=TEXT, linewidth=1)
    for index, value in enumerate(values):
        axis.annotate(
            f"{value:.2f}×",
            (value, index),
            xytext=(4, 0),
            textcoords="offset points",
            va="center",
            fontsize=8,
            color=TEXT,
        )
    axis.set_xlim(0, max(max(values) * 1.15, 1.2))
    axis.invert_yaxis()
    _style(axis)
    axis.set_xlabel("fastdrf req/s ÷ DRF req/s (1 = equal)", color=MUTED, fontsize=8)
    axis.set_title(
        f"Speed-up of fastdrf over DRF, {workers} worker{'s' if workers > 1 else ''}\n{caption}",
        fontsize=10,
        color=TEXT,
        loc="left",
    )
    stem = f"speedup-{workers}-worker{'s' if workers > 1 else ''}"
    _save(figure, directory, stem)
    return stem


def case_chart(directory: Path, case: str, rows: list[dict], caption: str) -> None:
    """Requests per second of both profiles at each worker count, with the range."""
    counts = sorted({r["workers"] for r in rows})
    by = {(r["profile"], r["workers"]): r for r in rows}
    figure, axis = plt.subplots(
        figsize=(8, 0.9 * len(counts) + 1.4), layout="constrained"
    )
    figure.set_facecolor(SURFACE)
    height = 0.36
    labels = []
    top = 0
    for index, count in enumerate(counts):
        labels.append(f"{count} worker{'s' if count > 1 else ''}")
        for offset, profile in ((-height / 2, "drf"), (height / 2, "fastdrf")):
            row = by.get((profile, count))
            position = index + offset
            if not row or not row["rps"]:
                axis.text(0, position, " invalid", va="center", fontsize=8, color=MUTED)
                continue
            axis.barh(
                position,
                row["rps"],
                height=height - 0.04,
                color=COLORS[profile],
                label=profile if index == 0 else None,
            )
            end = row["rps"]
            if row.get("rps_min") is not None and row["rps_max"] > row["rps_min"]:
                axis.errorbar(
                    row["rps"],
                    position,
                    xerr=[[row["rps"] - row["rps_min"]], [row["rps_max"] - row["rps"]]],
                    color=TEXT,
                    capsize=2,
                    linewidth=0.8,
                )
                end = row["rps_max"]
            top = max(top, end)
            axis.annotate(
                f"{row['rps']:,.0f}",
                (end, position),
                xytext=(4, 0),
                textcoords="offset points",
                va="center",
                fontsize=8,
                color=TEXT,
            )
    axis.set_yticks(range(len(counts)), labels)
    axis.set_xlim(0, top * 1.18 if top else 1)
    axis.invert_yaxis()
    _style(axis)
    axis.set_xlabel(
        "requests per second (range: fastest and slowest start)",
        color=MUTED,
        fontsize=8,
    )
    figure.legend(
        loc="outside lower center", ncol=2, fontsize=8, frameon=False, labelcolor=TEXT
    )
    axis.set_title(f"{case}\n{caption}", fontsize=10, color=TEXT, loc="left")
    _save(figure, directory, case)
