"""Render benchmark visualization assets from deterministic datasets.

Runs the benchmark suite across the dataset presets and writes one SVG chart per
metric (import throughput, retrieval latency, graph/intelligence generation, memory
usage, and database growth). Timings vary by machine; the datasets do not.

Usage:
    python examples/ops/benchmark_charts.py --out docs/assets/benchmarks
"""

from __future__ import annotations

import argparse
from pathlib import Path

from meeting_memory.benchmarks import (
    get_preset,
    run_benchmarks,
    write_comparison_charts,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("docs/assets/benchmarks"),
        help="Directory to write SVG charts into.",
    )
    parser.add_argument(
        "--datasets",
        nargs="+",
        default=["small", "medium", "large", "enterprise"],
        help="Dataset presets to benchmark (default: small medium large enterprise).",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=1,
        help="Iterations per benchmark (default: 1).",
    )
    args = parser.parse_args()

    reports = [
        run_benchmarks(get_preset(name), iterations=args.iterations) for name in args.datasets
    ]
    written = write_comparison_charts(reports, args.out)
    for path in written:
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
