"""Dependency-free SVG charts for benchmark reports.

Benchmark timings vary between machines, so these helpers render whatever data a
:class:`~meeting_memory.benchmarks.runner.BenchmarkReport` contains rather than
fabricating fixed numbers. Charts are emitted as self-contained SVG text with no
third-party plotting dependency, matching the project's dependency-free philosophy.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape

from .runner import BenchmarkReport

_WIDTH = 720
_HEIGHT = 360
_PAD_LEFT = 70
_PAD_RIGHT = 24
_PAD_TOP = 48
_PAD_BOTTOM = 64
_BAR_COLOR = "#2563eb"
_LINE_COLOR = "#2563eb"
_DOT_COLOR = "#1e3a8a"
_AXIS_COLOR = "#94a3b8"
_TEXT_COLOR = "#0f172a"
_GRID_COLOR = "#e2e8f0"


@dataclass(frozen=True)
class Chart:
    """A rendered chart: a filename plus its SVG document text."""

    filename: str
    svg: str

    def write(self, directory: Path) -> Path:
        """Write the SVG to ``directory`` and return the resulting path."""
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / self.filename
        path.write_text(self.svg, encoding="utf-8")
        return path


def _fmt(value: float) -> str:
    """Format a number compactly without trailing-zero noise."""
    if value == 0:
        return "0"
    if abs(value) >= 1000:
        return f"{value:,.0f}"
    if abs(value) >= 1:
        return f"{value:.2f}"
    return f"{value:.4f}"


def _plot_area() -> tuple[float, float, float, float]:
    """Return the inner plot rectangle as (x0, y0, x1, y1)."""
    return (
        float(_PAD_LEFT),
        float(_PAD_TOP),
        float(_WIDTH - _PAD_RIGHT),
        float(_HEIGHT - _PAD_BOTTOM),
    )


def _y_axis_label(text: str, y0: float, y1: float) -> str:
    mid = (y0 + y1) / 2
    return (
        f'<text x="16" y="{mid:.0f}" text-anchor="middle" font-size="12" '
        f'fill="{_TEXT_COLOR}" transform="rotate(-90 16 {mid:.0f})">{escape(text)}</text>'
    )


def _svg_header(title: str) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{_WIDTH}" height="{_HEIGHT}" '
        f'viewBox="0 0 {_WIDTH} {_HEIGHT}" font-family="system-ui, sans-serif">',
        f'<rect width="{_WIDTH}" height="{_HEIGHT}" fill="white"/>',
        f'<text x="{_WIDTH / 2:.0f}" y="26" text-anchor="middle" '
        f'font-size="18" font-weight="600" fill="{_TEXT_COLOR}">{escape(title)}</text>',
    ]


def bar_chart(title: str, labels: Sequence[str], values: Sequence[float], *, y_label: str) -> str:
    """Render a vertical bar chart as an SVG document string."""
    if len(labels) != len(values):
        raise ValueError("labels and values must be the same length")
    x0, y0, x1, y1 = _plot_area()
    parts = _svg_header(title)
    top = max(values, default=0.0)
    top = top if top > 0 else 1.0

    for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
        gy = y1 - frac * (y1 - y0)
        parts.append(
            f'<line x1="{x0:.1f}" y1="{gy:.1f}" x2="{x1:.1f}" y2="{gy:.1f}" '
            f'stroke="{_GRID_COLOR}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{x0 - 8:.1f}" y="{gy + 4:.1f}" text-anchor="end" '
            f'font-size="11" fill="{_TEXT_COLOR}">{_fmt(top * frac)}</text>'
        )

    count = len(values) or 1
    span = (x1 - x0) / count
    bar_w = span * 0.6
    for i, (label, value) in enumerate(zip(labels, values, strict=False)):
        cx = x0 + span * i + span / 2
        height = (value / top) * (y1 - y0)
        by = y1 - height
        parts.append(
            f'<rect x="{cx - bar_w / 2:.1f}" y="{by:.1f}" width="{bar_w:.1f}" '
            f'height="{height:.1f}" rx="3" fill="{_BAR_COLOR}"/>'
        )
        parts.append(
            f'<text x="{cx:.1f}" y="{by - 6:.1f}" text-anchor="middle" '
            f'font-size="11" fill="{_TEXT_COLOR}">{_fmt(value)}</text>'
        )
        parts.append(
            f'<text x="{cx:.1f}" y="{y1 + 18:.1f}" text-anchor="middle" '
            f'font-size="12" fill="{_TEXT_COLOR}">{escape(label)}</text>'
        )

    parts.append(_y_axis_label(y_label, y0, y1))
    parts.append("</svg>")
    return "\n".join(parts)


def line_chart(
    title: str,
    xs: Sequence[float],
    ys: Sequence[float],
    *,
    x_label: str,
    y_label: str,
) -> str:
    """Render a single-series line chart as an SVG document string."""
    if len(xs) != len(ys):
        raise ValueError("xs and ys must be the same length")
    x0, y0, x1, y1 = _plot_area()
    parts = _svg_header(title)
    x_max = max(xs, default=0.0) or 1.0
    y_max = max(ys, default=0.0) or 1.0

    for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
        gy = y1 - frac * (y1 - y0)
        parts.append(
            f'<line x1="{x0:.1f}" y1="{gy:.1f}" x2="{x1:.1f}" y2="{gy:.1f}" '
            f'stroke="{_GRID_COLOR}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{x0 - 8:.1f}" y="{gy + 4:.1f}" text-anchor="end" '
            f'font-size="11" fill="{_TEXT_COLOR}">{_fmt(y_max * frac)}</text>'
        )

    def point(x: float, y: float) -> tuple[float, float]:
        px = x0 + (x / x_max) * (x1 - x0)
        py = y1 - (y / y_max) * (y1 - y0)
        return px, py

    coords = [point(x, y) for x, y in zip(xs, ys, strict=False)]
    if len(coords) >= 2:
        path = " ".join(
            f"{'M' if i == 0 else 'L'}{px:.1f},{py:.1f}" for i, (px, py) in enumerate(coords)
        )
        parts.append(f'<path d="{path}" fill="none" stroke="{_LINE_COLOR}" stroke-width="2.5"/>')
    for (px, py), xv in zip(coords, xs, strict=False):
        parts.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="3.5" fill="{_DOT_COLOR}"/>')
        parts.append(
            f'<text x="{px:.1f}" y="{y1 + 18:.1f}" text-anchor="middle" '
            f'font-size="11" fill="{_TEXT_COLOR}">{_fmt(xv)}</text>'
        )

    parts.append(
        f'<text x="{(x0 + x1) / 2:.0f}" y="{_HEIGHT - 12}" text-anchor="middle" '
        f'font-size="12" fill="{_TEXT_COLOR}">{escape(x_label)}</text>'
    )
    parts.append(_y_axis_label(y_label, y0, y1))
    parts.append("</svg>")
    return "\n".join(parts)


def _mean_ms(report: BenchmarkReport, name: str) -> float:
    result = report.result(name)
    return result.mean_ms if result is not None else 0.0


def _throughput(report: BenchmarkReport, name: str) -> float:
    result = report.result(name)
    return result.throughput if result is not None else 0.0


def _summary_value(report: BenchmarkReport, key: str) -> float:
    value = report.summary.get(key, 0)
    return float(value) if isinstance(value, (int, float)) else 0.0


def comparison_charts(reports: Sequence[BenchmarkReport]) -> list[Chart]:
    """Build the standard set of cross-dataset benchmark charts.

    One :class:`Chart` is produced per metric (import throughput, retrieval latency,
    graph generation, intelligence generation, memory usage, and database growth),
    with one bar/point per supplied report.
    """
    if not reports:
        raise ValueError("at least one report is required")
    labels = [report.dataset for report in reports]
    charts = [
        Chart(
            "import_throughput.svg",
            bar_chart(
                "Import throughput",
                labels,
                [_throughput(r, "import") for r in reports],
                y_label="meetings / second",
            ),
        ),
        Chart(
            "retrieval_latency.svg",
            bar_chart(
                "Retrieval latency",
                labels,
                [_mean_ms(r, "retrieval") for r in reports],
                y_label="mean ms / query",
            ),
        ),
        Chart(
            "graph_generation.svg",
            bar_chart(
                "Graph generation",
                labels,
                [_mean_ms(r, "graph") for r in reports],
                y_label="mean ms / build",
            ),
        ),
        Chart(
            "intelligence_generation.svg",
            bar_chart(
                "Intelligence generation",
                labels,
                [_mean_ms(r, "intelligence") for r in reports],
                y_label="mean ms / report",
            ),
        ),
        Chart(
            "memory_usage.svg",
            bar_chart(
                "Peak memory usage",
                labels,
                [_summary_value(r, "peak_memory_bytes") / 1_048_576 for r in reports],
                y_label="peak MiB",
            ),
        ),
        Chart(
            "database_growth.svg",
            line_chart(
                "Database growth",
                [_summary_value(r, "memories") for r in reports],
                [_summary_value(r, "db_size_bytes") / 1024 for r in reports],
                x_label="memories stored",
                y_label="database size (KiB)",
            ),
        ),
    ]
    return charts


def report_charts(report: BenchmarkReport) -> list[Chart]:
    """Build per-operation charts for a single benchmark report."""
    names = [r.name for r in report.results]
    return [
        Chart(
            "operation_latency.svg",
            bar_chart(
                f"Operation latency — {report.dataset}",
                names,
                [r.mean_ms for r in report.results],
                y_label="mean ms",
            ),
        ),
        Chart(
            "operation_throughput.svg",
            bar_chart(
                f"Operation throughput — {report.dataset}",
                names,
                [r.throughput for r in report.results],
                y_label="ops / second",
            ),
        ),
    ]


def write_comparison_charts(reports: Sequence[BenchmarkReport], out_dir: Path) -> list[Path]:
    """Render and write the cross-dataset charts to ``out_dir``."""
    return [chart.write(out_dir) for chart in comparison_charts(reports)]


def write_report_charts(report: BenchmarkReport, out_dir: Path) -> list[Path]:
    """Render and write the single-report charts to ``out_dir``."""
    return [chart.write(out_dir) for chart in report_charts(report)]
