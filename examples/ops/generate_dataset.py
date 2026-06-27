#!/usr/bin/env python
"""Generate a deterministic benchmark dataset (e.g. a large organization).

Usage:
    python examples/ops/generate_dataset.py --dataset enterprise --out /tmp/org

The "enterprise" preset models a large organization: many projects and people,
recurring risks, evolving decisions, long weekly timelines, and cross-meeting
references, producing thousands of memories. Output is byte-for-byte
reproducible for a given preset.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from meeting_memory.benchmarks import DATASET_PRESETS, get_preset, write_dataset


def main() -> int:
    """Generate the requested dataset into a directory and print a summary."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", choices=sorted(DATASET_PRESETS), default="large")
    parser.add_argument("--out", type=Path, default=Path("dataset"))
    args = parser.parse_args()

    spec = get_preset(args.dataset)
    paths = write_dataset(spec, args.out)
    print(f"Wrote {len(paths)} transcripts for the '{spec.name}' dataset to {args.out}")
    print(
        f"projects={spec.projects} people={spec.people} "
        f"meetings={spec.meetings} utterances/meeting={spec.utterances_per_meeting}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
