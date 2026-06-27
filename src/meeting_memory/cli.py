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
from .retrieval import (
    ContextAssembler,
    ContextWindow,
    MemoryRetriever,
    RankedMemory,
    RankingWeights,
    RetrievalFilter,
    RetrievalQuery,
    explain_match,
    score_components,
)
from .storage import (
    MemoryQuery,
    MemoryStatus,
    SQLiteMemoryStore,
    StoredMemory,
    import_meeting,
)
from .utils import compute_statistics

DEFAULT_DB_PATH = Path("meeting-memory.db")


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


def _parse_str_set(value: str) -> frozenset[str]:
    """Parse a comma-separated list of non-empty strings."""
    items = {token.strip() for token in value.split(",") if token.strip()}
    if not items:
        raise argparse.ArgumentTypeError("expected at least one value")
    return frozenset(items)


def _parse_status_set(value: str) -> frozenset[MemoryStatus]:
    """Parse a comma-separated list of lifecycle statuses."""
    valid = {member.value: member for member in MemoryStatus}
    selected: set[MemoryStatus] = set()
    for raw_name in value.split(","):
        name = raw_name.strip()
        if not name:
            continue
        if name not in valid:
            choices = ", ".join(sorted(valid))
            raise argparse.ArgumentTypeError(f"unknown status {name!r}; choose from: {choices}")
        selected.add(valid[name])
    if not selected:
        raise argparse.ArgumentTypeError("no valid statuses provided")
    return frozenset(selected)


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

    _add_storage_commands(subcommands)
    _add_retrieval_commands(subcommands)
    return parser


def _add_db_argument(command: argparse.ArgumentParser) -> None:
    """Attach the shared ``--db`` option to a storage subcommand."""
    command.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        help=f"Path to the SQLite database (default: {DEFAULT_DB_PATH}).",
    )


def _add_storage_commands(subcommands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the persistent-storage subcommands."""
    import_cmd = subcommands.add_parser(
        "import",
        help="Import a transcript into the persistent memory store.",
        description="Load, parse, extract, and persist a transcript, then print a summary.",
    )
    import_cmd.add_argument("path", type=Path, help="Path to the transcript file.")
    _add_db_argument(import_cmd)
    import_cmd.add_argument(
        "--types",
        type=_parse_memory_types,
        default=None,
        metavar="T1,T2,...",
        help="Comma-separated memory types to extract. Defaults to all types.",
    )
    import_cmd.add_argument(
        "--min-confidence",
        type=_parse_confidence,
        default=0.0,
        metavar="FLOAT",
        help="Drop memories scoring below this confidence (0.0-1.0). Default: 0.0.",
    )
    import_cmd.add_argument(
        "--no-deduplicate",
        action="store_true",
        help="Keep duplicate memories instead of collapsing them.",
    )
    import_cmd.add_argument(
        "--now",
        type=_parse_iso_datetime,
        default=None,
        metavar="ISO8601",
        help="Stamp records with this timestamp instead of the current time.",
    )
    import_cmd.add_argument("--json", action="store_true", help="Emit the import summary as JSON.")
    import_cmd.set_defaults(handler=_handle_import)

    list_cmd = subcommands.add_parser(
        "list",
        help="List stored memories, optionally filtered.",
        description="Query stored memories with optional type/speaker/meeting/status filters.",
    )
    _add_db_argument(list_cmd)
    list_cmd.add_argument("--type", type=_parse_memory_types, default=None, metavar="T1,T2,...")
    list_cmd.add_argument("--speaker", type=_parse_str_set, default=None, metavar="S1,S2,...")
    list_cmd.add_argument("--meeting", type=_parse_str_set, default=None, metavar="M1,M2,...")
    list_cmd.add_argument("--status", type=_parse_status_set, default=None, metavar="S1,S2,...")
    list_cmd.add_argument("--min-confidence", type=_parse_confidence, default=None, metavar="FLOAT")
    list_cmd.add_argument("--limit", type=int, default=None, help="Maximum rows to return.")
    list_cmd.add_argument("--json", action="store_true", help="Emit memories as JSON.")
    list_cmd.set_defaults(handler=_handle_list)

    show_cmd = subcommands.add_parser(
        "show",
        help="Show a single memory by id.",
        description="Display the full detail of one stored memory.",
    )
    show_cmd.add_argument("memory_id", help="The memory id to display.")
    _add_db_argument(show_cmd)
    show_cmd.add_argument("--json", action="store_true", help="Emit the memory as JSON.")
    show_cmd.set_defaults(handler=_handle_show)

    meetings_cmd = subcommands.add_parser(
        "meetings",
        help="List meetings in the registry.",
        description="List all meetings stored in the registry.",
    )
    _add_db_argument(meetings_cmd)
    meetings_cmd.add_argument("--limit", type=int, default=None, help="Maximum rows to return.")
    meetings_cmd.add_argument("--json", action="store_true", help="Emit meetings as JSON.")
    meetings_cmd.set_defaults(handler=_handle_meetings)

    stats_cmd = subcommands.add_parser(
        "stats",
        help="Show aggregate statistics for the store.",
        description="Summarise stored meetings and memories by type and status.",
    )
    _add_db_argument(stats_cmd)
    stats_cmd.add_argument("--json", action="store_true", help="Emit statistics as JSON.")
    stats_cmd.set_defaults(handler=_handle_stats)


def _add_retrieval_filter_options(command: argparse.ArgumentParser) -> None:
    """Attach the filter options shared by ``search`` and ``timeline``."""
    command.add_argument("--type", type=_parse_memory_types, default=None, metavar="T1,T2,...")
    command.add_argument("--speaker", type=_parse_str_set, default=None, metavar="S1,S2,...")
    command.add_argument("--meeting", type=_parse_str_set, default=None, metavar="M1,M2,...")
    command.add_argument("--status", type=_parse_status_set, default=None, metavar="S1,S2,...")
    command.add_argument("--min-confidence", type=_parse_confidence, default=None, metavar="FLOAT")
    command.add_argument(
        "--before", default=None, metavar="DATE", help="Meetings on or before DATE."
    )
    command.add_argument("--after", default=None, metavar="DATE", help="Meetings on or after DATE.")
    command.add_argument(
        "--between",
        nargs=2,
        default=None,
        metavar=("START", "END"),
        help="Meetings between START and END (inclusive).",
    )
    command.add_argument("--limit", type=int, default=None, help="Maximum results to return.")
    command.add_argument("--offset", type=int, default=0, help="Skip this many results.")
    command.add_argument(
        "--context", type=int, default=0, metavar="N", help="Utterances of context per result."
    )
    command.add_argument("--json", action="store_true", help="Emit results as JSON.")


def _add_retrieval_commands(
    subcommands: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the retrieval subcommands (``search``, ``timeline``, ``explain``)."""
    search_cmd = subcommands.add_parser(
        "search",
        help="Search organizational memory across meetings.",
        description="Rank stored memories by deterministic relevance to a query.",
    )
    search_cmd.add_argument("text", nargs="*", help="Free-text query terms.")
    _add_db_argument(search_cmd)
    _add_retrieval_filter_options(search_cmd)
    search_cmd.set_defaults(handler=_handle_search)

    timeline_cmd = subcommands.add_parser(
        "timeline",
        help="Show matching memories in chronological order.",
        description="List memories ordered by meeting date (oldest first).",
    )
    timeline_cmd.add_argument("text", nargs="*", help="Free-text query terms.")
    _add_db_argument(timeline_cmd)
    _add_retrieval_filter_options(timeline_cmd)
    timeline_cmd.set_defaults(handler=_handle_timeline)

    explain_cmd = subcommands.add_parser(
        "explain",
        help="Explain why a memory exists and show its context.",
        description="Show a memory's provenance, attributes, and surrounding context.",
    )
    explain_cmd.add_argument("memory_id", help="The memory id to explain.")
    _add_db_argument(explain_cmd)
    explain_cmd.add_argument(
        "--context", type=int, default=2, metavar="N", help="Utterances of context to show."
    )
    explain_cmd.add_argument("--json", action="store_true", help="Emit the explanation as JSON.")
    explain_cmd.set_defaults(handler=_handle_explain)


def _retrieval_query_from_args(args: argparse.Namespace) -> RetrievalQuery:
    """Assemble a :class:`RetrievalQuery` from shared filter arguments."""
    words = getattr(args, "text", None) or []
    text = " ".join(words).strip() or None
    date_from: str | None = None
    date_to: str | None = None
    if args.between is not None:
        date_from, date_to = args.between
    if args.after is not None:
        date_from = args.after
    if args.before is not None:
        date_to = args.before
    memory_types = frozenset(member.value for member in args.type) if args.type else frozenset()
    return RetrievalQuery(
        text=text,
        memory_types=memory_types,
        speakers=args.speaker or frozenset(),
        statuses=args.status or frozenset(),
        meeting_ids=args.meeting or frozenset(),
        min_confidence=args.min_confidence,
        date_from=date_from,
        date_to=date_to,
        limit=args.limit,
        offset=args.offset,
        context_size=args.context,
    )


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


def _handle_import(args: argparse.Namespace) -> int:
    """Execute the ``import`` subcommand."""
    config = ExtractionConfig(
        enabled_types=args.types,
        min_confidence=args.min_confidence,
        deduplicate=not args.no_deduplicate,
    )
    with SQLiteMemoryStore(args.db) as store:
        result = import_meeting(args.path, store, config=config, now=args.now)
    if args.json:
        _print_json(result.to_dict())
    else:
        print("\n".join(result.summary_lines()))
    return 0


def _handle_list(args: argparse.Namespace) -> int:
    """Execute the ``list`` subcommand."""
    query = MemoryQuery(
        memory_types=(frozenset(member.value for member in args.type) if args.type else None),
        speakers=args.speaker,
        meeting_ids=args.meeting,
        statuses=args.status,
        min_confidence=args.min_confidence,
        limit=args.limit,
    )
    with SQLiteMemoryStore(args.db) as store:
        memories = store.query(query)
    if args.json:
        _print_json([memory.to_dict() for memory in memories])
    elif not memories:
        print("No memories found.")
    else:
        for memory in memories:
            print(_format_memory_line(memory))
    return 0


def _handle_show(args: argparse.Namespace) -> int:
    """Execute the ``show`` subcommand."""
    with SQLiteMemoryStore(args.db) as store:
        memory = store.get(args.memory_id)
    if args.json:
        _print_json(memory.to_dict())
    else:
        print("\n".join(_format_memory_detail(memory)))
    return 0


def _handle_meetings(args: argparse.Namespace) -> int:
    """Execute the ``meetings`` subcommand."""
    with SQLiteMemoryStore(args.db) as store:
        meetings = store.list_meetings(limit=args.limit)
    if args.json:
        _print_json([meeting.to_dict() for meeting in meetings])
    elif not meetings:
        print("No meetings found.")
    else:
        for meeting in meetings:
            participants = ", ".join(meeting.participants) or "-"
            date = meeting.date or "-"
            title = meeting.title or "(untitled)"
            print(f"{meeting.meeting_id}  {date}  {title}  [{participants}]")
    return 0


def _handle_stats(args: argparse.Namespace) -> int:
    """Execute the ``stats`` subcommand."""
    with SQLiteMemoryStore(args.db) as store:
        meetings = len(store.list_meetings())
        total = store.count()
        by_type = {
            member.value: store.count(MemoryQuery(memory_types=frozenset({member.value})))
            for member in MemoryType
        }
        by_status = {
            member.value: store.count(MemoryQuery(statuses=frozenset({member})))
            for member in MemoryStatus
        }
    stats = {
        "meetings": meetings,
        "memories": total,
        "by_type": by_type,
        "by_status": by_status,
    }
    if args.json:
        _print_json(stats)
    else:
        print(f"Meetings: {meetings}")
        print(f"Memories: {total}")
        print("By type:")
        for name, count in by_type.items():
            if count:
                print(f"  {name}: {count}")
        print("By status:")
        for name, count in by_status.items():
            if count:
                print(f"  {name}: {count}")
    return 0


def _handle_search(args: argparse.Namespace) -> int:
    """Execute the ``search`` subcommand."""
    query = _retrieval_query_from_args(args)
    with SQLiteMemoryStore(args.db) as store:
        result = MemoryRetriever(store).retrieve(query)
    if args.json:
        _print_json(result.to_dict())
    elif not result.ranked:
        print("No matching memories.")
    else:
        for ranked in result.ranked:
            print("\n".join(_format_ranked(ranked, args.context)))
            print("")
    return 0


def _handle_timeline(args: argparse.Namespace) -> int:
    """Execute the ``timeline`` subcommand."""
    query = _retrieval_query_from_args(args)
    with SQLiteMemoryStore(args.db) as store:
        result = MemoryRetriever(store).timeline(query)
    if args.json:
        _print_json(result.to_dict())
    elif not result.ranked:
        print("No matching memories.")
    else:
        for ranked in result.ranked:
            date = ranked.meeting.date if ranked.meeting and ranked.meeting.date else "-"
            speaker = ranked.memory.speaker or "?"
            print(
                f"{date}  {ranked.memory.memory_id}  [{ranked.memory.memory_type}] "
                f"{speaker}: {ranked.memory.text}"
            )
    return 0


def _handle_explain(args: argparse.Namespace) -> int:
    """Execute the ``explain`` subcommand."""
    with SQLiteMemoryStore(args.db) as store:
        memory = store.get(args.memory_id)
        meeting = store.get_meeting(memory.meeting_id)
        applied = RetrievalFilter(
            memory_types=frozenset({memory.memory_type}),
            statuses=frozenset({memory.status}),
            speakers=frozenset({memory.speaker}) if memory.speaker else frozenset(),
        )
        components = score_components(memory, meeting, applied, recency=1.0)
        explanation = explain_match(memory, meeting, applied, components, RankingWeights())
        context = ContextAssembler().assemble(memory, meeting, args.context)
    if args.json:
        _print_json(
            {
                "memory": memory.to_dict(),
                "explanation": explanation.to_dict(),
                "context": context.to_dict(),
            }
        )
    else:
        lines = _format_memory_detail(memory)
        lines.append("matched because:")
        lines.extend(f"  {line}" for line in explanation.lines())
        lines.append("context:")
        lines.extend(f"  {line}" for line in _format_context_lines(context))
        print("\n".join(lines))
    return 0


def _format_ranked(ranked: RankedMemory, context_size: int) -> list[str]:
    """Render a ranked memory with its explanation and optional context."""
    speaker = ranked.memory.speaker or "?"
    date = ranked.meeting.date if ranked.meeting and ranked.meeting.date else "-"
    lines = [
        f"{ranked.memory.memory_id}  ({ranked.score:.3f})  {date}  "
        f"[{ranked.memory.memory_type}] {ranked.memory.status.value}  {speaker}: "
        f"{ranked.memory.text}"
    ]
    if ranked.explanation is not None:
        lines.extend(f"  {line}" for line in ranked.explanation.lines())
    if context_size > 0 and ranked.context is not None:
        lines.append("  context:")
        lines.extend(f"    {line}" for line in _format_context_lines(ranked.context))
    return lines


def _format_context_lines(context: ContextWindow) -> list[str]:
    """Render a context window (before/target/after) as readable lines."""
    lines: list[str] = []
    for utterance in context.before:
        lines.append(f"  [{utterance.index}] {utterance.speaker}: {utterance.text}")
    if context.target is not None:
        target = context.target
        lines.append(f"> [{target.index}] {target.speaker}: {target.text}")
    for utterance in context.after:
        lines.append(f"  [{utterance.index}] {utterance.speaker}: {utterance.text}")
    return lines


def _format_memory_line(memory: StoredMemory) -> str:
    """Render a one-line summary of a stored memory."""
    speaker = memory.speaker or "?"
    return (
        f"{memory.memory_id}  [{memory.memory_type}] "
        f"({memory.confidence:.2f}) {memory.status.value}  {speaker}: {memory.text}"
    )


def _format_memory_detail(memory: StoredMemory) -> list[str]:
    """Render a multi-line detail view of a stored memory."""
    lines = [
        f"id:         {memory.memory_id}",
        f"meeting:    {memory.meeting_id}",
        f"type:       {memory.memory_type}",
        f"status:     {memory.status.value}",
        f"speaker:    {memory.speaker or '-'}",
        f"confidence: {memory.confidence:.2f}",
        f"utterance:  {memory.utterance_index}",
        f"created_at: {memory.created_at}",
        f"text:       {memory.text}",
    ]
    if memory.superseded_by:
        lines.append(f"superseded_by: {memory.superseded_by}")
    for key in sorted(memory.metadata):
        lines.append(f"meta.{key}: {memory.metadata[key]}")
    for span in memory.evidence:
        lines.append(f"evidence:   [{span.start}:{span.end}] {span.text}")
    return lines


def _print_json(data: object) -> None:
    """Print ``data`` as pretty JSON to standard output."""
    print(json.dumps(data, indent=2, ensure_ascii=False))


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
