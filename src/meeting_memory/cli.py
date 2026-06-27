"""Command-line interface for the Meeting Memory System.

Example:
    $ meeting-memory parse meeting.txt
    $ meeting-memory parse meeting.json --stats --output meeting.parsed.json
    $ meeting-memory extract meeting.txt --types decision,commitment --min-confidence 0.7
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from . import __version__
from .exceptions import MeetingMemoryError
from .extraction import ExtractionConfig, MemoryType, extract_memories
from .parser import MeetingParser, validate_meeting
from .utils import compute_statistics


def _parse_memory_types(value: str) -> frozenset[MemoryType]:
    """Parse a comma-separated list of memory type names into a set."""
    valid = {member.value: member for member in MemoryType}
    selected: set[MemoryType] = set()
    for raw_name in value.split(","):
        name = raw_name.strip()
        if not name:
            continue
        if name not in valid:
            choices = ", ".join(sorted(valid))
            raise argparse.ArgumentTypeError(
                f"unknown memory type {name!r}; choose from: {choices}"
            )
        selected.add(valid[name])
    if not selected:
        raise argparse.ArgumentTypeError("no valid memory types provided")
    return frozenset(selected)


def _parse_confidence(value: str) -> float:
    """Parse and bound-check a confidence threshold in ``[0.0, 1.0]``."""
    number = float(value)
    if not 0.0 <= number <= 1.0:
        raise argparse.ArgumentTypeError("min-confidence must be between 0.0 and 1.0")
    return number


def _parse_iso_datetime(value: str) -> datetime:
    """Parse an ISO-8601 timestamp (used for reproducible extraction output)."""
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid ISO-8601 timestamp: {value!r}") from exc


def build_parser() -> argparse.ArgumentParser:
    """Construct the top-level argument parser."""
    parser = argparse.ArgumentParser(
        prog="meeting-memory",
        description="Parse raw meeting transcripts into structured JSON.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subcommands = parser.add_subparsers(dest="command", required=True)

    parse_cmd = subcommands.add_parser(
        "parse",
        help="Parse a transcript file and emit structured JSON.",
        description="Parse a transcript file (txt or json) and emit structured JSON.",
    )
    parse_cmd.add_argument("path", type=Path, help="Path to the transcript file.")
    parse_cmd.add_argument(
        "--stats",
        action="store_true",
        help="Include descriptive statistics in the output.",
    )
    parse_cmd.add_argument(
        "--indent",
        type=int,
        default=2,
        help="Number of spaces for JSON indentation (use 0 for compact output).",
    )
    parse_cmd.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip semantic validation of the parsed meeting.",
    )
    parse_cmd.add_argument(
        "--allow-duplicate-timestamps",
        action="store_true",
        help="Do not treat duplicate timestamps as a validation error.",
    )
    parse_cmd.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Write JSON to this file instead of standard output.",
    )
    parse_cmd.set_defaults(handler=_handle_parse)

    extract_cmd = subcommands.add_parser(
        "extract",
        help="Extract structured memory records from a transcript.",
        description=(
            "Parse a transcript and extract memory primitives (decisions, "
            "commitments, open loops, risks, assumptions, questions, facts)."
        ),
    )
    extract_cmd.add_argument("path", type=Path, help="Path to the transcript file.")
    extract_cmd.add_argument(
        "--types",
        type=_parse_memory_types,
        default=None,
        metavar="T1,T2,...",
        help=(
            "Comma-separated memory types to extract "
            "(decision, commitment, open_loop, risk, assumption, question, fact). "
            "Defaults to all types."
        ),
    )
    extract_cmd.add_argument(
        "--min-confidence",
        type=_parse_confidence,
        default=0.0,
        metavar="FLOAT",
        help="Drop memories scoring below this confidence (0.0-1.0). Default: 0.0.",
    )
    extract_cmd.add_argument(
        "--no-deduplicate",
        action="store_true",
        help="Keep duplicate memories instead of collapsing them.",
    )
    extract_cmd.add_argument(
        "--now",
        type=_parse_iso_datetime,
        default=None,
        metavar="ISO8601",
        help="Stamp memories with this timestamp instead of the current time.",
    )
    extract_cmd.add_argument(
        "--indent",
        type=int,
        default=2,
        help="Number of spaces for JSON indentation (use 0 for compact output).",
    )
    extract_cmd.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Write JSON to this file instead of standard output.",
    )
    extract_cmd.set_defaults(handler=_handle_extract)
    return parser


def _handle_parse(args: argparse.Namespace) -> int:
    """Execute the ``parse`` subcommand."""
    parser = MeetingParser()
    meeting = parser.parse_file(args.path)

    if not args.no_validate:
        validate_meeting(
            meeting,
            require_timestamps_unique=not args.allow_duplicate_timestamps,
        )

    payload = meeting.to_dict()
    if args.stats:
        payload["statistics"] = compute_statistics(meeting).to_dict()

    _emit(payload, indent=args.indent, output=args.output)
    return 0


def _handle_extract(args: argparse.Namespace) -> int:
    """Execute the ``extract`` subcommand."""
    meeting = MeetingParser().parse_file(args.path)
    config = ExtractionConfig(
        enabled_types=args.types,
        min_confidence=args.min_confidence,
        deduplicate=not args.no_deduplicate,
    )
    result = extract_memories(meeting, config=config, now=args.now)
    _emit(result.to_dict(), indent=args.indent, output=args.output)
    return 0


def _emit(payload: dict[str, object], *, indent: int, output: Path | None) -> None:
    """Serialise ``payload`` to JSON and write it to a file or standard output."""
    json_indent = indent if indent > 0 else None
    text = json.dumps(payload, indent=json_indent, ensure_ascii=False)
    if output is not None:
        output.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point: parse arguments, dispatch, and translate errors to exit codes."""
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result: int = args.handler(args)
        return result
    except MeetingMemoryError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
