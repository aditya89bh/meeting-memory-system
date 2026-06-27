#!/usr/bin/env python
"""Run the performance benchmarks and print (or save) a report.

Usage:
    python examples/ops/run_benchmarks.py --dataset medium --iterations 3
    python examples/ops/run_benchmarks.py --dataset small --json --out report.json

Datasets are seeded and reproducible. Timings depend on the host, so treat the
numbers as relative measurements rather than fixed targets.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from meeting_memory.benchmarks import DATASET_PRESETS, get_preset, run_benchmarks


def main() -> int:
    """Run benchmarks for the chosen dataset and emit a report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", choices=sorted(DATASET_PRESETS), default="small")
    parser.add_argument("--iterations", type=int, default=1)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    report = run_benchmarks(get_preset(args.dataset), iterations=args.iterations)
    text = json.dumps(report.to_dict(), indent=2) if args.json else report.render_text()
    if args.out is not None:
        args.out.write_text(text + "\n", encoding="utf-8")
        print(f"Wrote benchmark report to {args.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
