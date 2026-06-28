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
import tempfile
import time
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .benchmarks import (
    DATASET_PRESETS,
    get_preset,
    run_benchmarks,
    write_dataset,
    write_report_charts,
)
from .connectors import (
    JsonlFileLogSink,
    StructuredLogger,
    default_registry,
    simulate,
    utc_now,
)
from .exceptions import MeetingMemoryError
from .extraction import ExtractionConfig, MemoryType, extract_memories
from .graph import (
    EXPORT_FORMATS,
    EntityType,
    GraphNode,
    RelationshipType,
)
from .intelligence import (
    REPORT_FORMATS,
    AnalysisFilters,
    InsightReport,
    InsightType,
    OrganizationalHealth,
)
from .observability import MetricsCollector, SystemMetrics, profile_cpu, profile_memory
from .parser import MeetingParser, validate_meeting
from .recovery import BackupManager, export_snapshot, import_snapshot
from .replay import ReplayEngine, ReplayFilter, ReplayResult, ReplayTimeline
from .retrieval import (
    ContextWindow,
    RankedMemory,
    RetrievalQuery,
)
from .services import (
    AutomationService,
    ExportService,
    GraphService,
    IntelligenceService,
    MeetingService,
    MemoryService,
    RetrievalService,
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


def _parse_entity_types(value: str) -> frozenset[EntityType]:
    """Parse a comma-separated list of graph node (entity) types into a set."""
    valid = {member.value: member for member in EntityType}
    selected: set[EntityType] = set()
    for raw_name in value.split(","):
        name = raw_name.strip().lower()
        if not name:
            continue
        if name not in valid:
            choices = ", ".join(sorted(valid))
            raise argparse.ArgumentTypeError(f"unknown node type {name!r}; choose from: {choices}")
        selected.add(valid[name])
    if not selected:
        raise argparse.ArgumentTypeError("no valid node types provided")
    return frozenset(selected)


def _parse_relationship_types(value: str) -> frozenset[RelationshipType]:
    """Parse a comma-separated list of relationship types into a set."""
    valid = {member.value: member for member in RelationshipType}
    selected: set[RelationshipType] = set()
    for raw_name in value.split(","):
        name = raw_name.strip().lower()
        if not name:
            continue
        if name not in valid:
            choices = ", ".join(sorted(valid))
            raise argparse.ArgumentTypeError(
                f"unknown relationship {name!r}; choose from: {choices}"
            )
        selected.add(valid[name])
    if not selected:
        raise argparse.ArgumentTypeError("no valid relationships provided")
    return frozenset(selected)


def _parse_insight_types(value: str) -> frozenset[InsightType]:
    """Parse a comma-separated list of insight types into a set."""
    valid = {member.value: member for member in InsightType}
    selected: set[InsightType] = set()
    for raw_name in value.split(","):
        name = raw_name.strip().lower()
        if not name:
            continue
        if name not in valid:
            choices = ", ".join(sorted(valid))
            raise argparse.ArgumentTypeError(
                f"unknown insight type {name!r}; choose from: {choices}"
            )
        selected.add(valid[name])
    if not selected:
        raise argparse.ArgumentTypeError("no valid insight types provided")
    return frozenset(selected)


def _parse_meeting_ids(value: str) -> frozenset[str]:
    """Parse a comma-separated list of meeting ids into a set."""
    ids = {item.strip() for item in value.split(",") if item.strip()}
    if not ids:
        raise argparse.ArgumentTypeError("no valid meeting ids provided")
    return frozenset(ids)


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
    _add_graph_commands(subcommands)
    _add_intelligence_commands(subcommands)
    _add_connector_commands(subcommands)
    _add_ops_commands(subcommands)
    _add_demo_command(subcommands)
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
    memories = MemoryService(args.db).query(query)
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
    memory = MemoryService(args.db).get_memory(args.memory_id)
    if args.json:
        _print_json(memory.to_dict())
    else:
        print("\n".join(_format_memory_detail(memory)))
    return 0


def _handle_meetings(args: argparse.Namespace) -> int:
    """Execute the ``meetings`` subcommand."""
    meetings = MeetingService(args.db).list_meetings(limit=args.limit)
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
    summary = MeetingService(args.db).stats()
    meetings = summary.meetings
    total = summary.memories
    by_type = summary.by_type
    by_status = summary.by_status
    if args.json:
        _print_json(summary.to_dict())
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
    result = RetrievalService(args.db).search(query)
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
    result = RetrievalService(args.db).timeline(query)
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
    explained = RetrievalService(args.db).explain(args.memory_id, context_size=args.context)
    memory = explained.memory
    explanation = explained.explanation
    context = explained.context
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


def _add_graph_commands(subcommands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the organizational-graph subcommands."""
    graph_cmd = subcommands.add_parser(
        "graph",
        help="Build and summarise the organizational memory graph.",
        description="Build the graph from stored memories and show node/edge counts.",
    )
    _add_db_argument(graph_cmd)
    graph_cmd.add_argument("--type", type=_parse_entity_types, default=None, metavar="T1,T2,...")
    graph_cmd.add_argument("--limit", type=int, default=None, help="Maximum nodes to list.")
    graph_cmd.add_argument("--json", action="store_true", help="Emit the summary as JSON.")
    graph_cmd.set_defaults(handler=_handle_graph)

    neighbors_cmd = subcommands.add_parser(
        "neighbors",
        help="Show the neighbourhood of a graph node.",
        description="Traverse the graph from a node up to a given depth.",
    )
    neighbors_cmd.add_argument("node_id", help="The node id to start from.")
    _add_db_argument(neighbors_cmd)
    neighbors_cmd.add_argument("--depth", type=int, default=1, help="Traversal depth (default: 1).")
    neighbors_cmd.add_argument(
        "--type", type=_parse_entity_types, default=None, metavar="T1,T2,..."
    )
    neighbors_cmd.add_argument(
        "--relationship", type=_parse_relationship_types, default=None, metavar="R1,R2,..."
    )
    neighbors_cmd.add_argument("--limit", type=int, default=None, help="Maximum nodes to list.")
    neighbors_cmd.add_argument("--json", action="store_true", help="Emit results as JSON.")
    neighbors_cmd.set_defaults(handler=_handle_neighbors)

    path_cmd = subcommands.add_parser(
        "path",
        help="Find the shortest path between two graph nodes.",
        description="Search for a deterministic shortest path between two nodes.",
    )
    path_cmd.add_argument("source", help="The source node id.")
    path_cmd.add_argument("target", help="The target node id.")
    _add_db_argument(path_cmd)
    path_cmd.add_argument("--depth", type=int, default=6, help="Maximum path length (default: 6).")
    path_cmd.add_argument(
        "--relationship", type=_parse_relationship_types, default=None, metavar="R1,R2,..."
    )
    path_cmd.add_argument("--json", action="store_true", help="Emit the path as JSON.")
    path_cmd.set_defaults(handler=_handle_path)

    export_cmd = subcommands.add_parser(
        "export-graph",
        help="Export the organizational memory graph.",
        description="Export the graph as JSON, Mermaid, or Graphviz DOT.",
    )
    _add_db_argument(export_cmd)
    export_cmd.add_argument(
        "--format", choices=EXPORT_FORMATS, default="json", help="Export format (default: json)."
    )
    export_cmd.add_argument("--type", type=_parse_entity_types, default=None, metavar="T1,T2,...")
    export_cmd.add_argument("--limit", type=int, default=None, help="Maximum nodes to include.")
    export_cmd.set_defaults(handler=_handle_export_graph)


def _handle_graph(args: argparse.Namespace) -> int:
    """Execute the ``graph`` subcommand."""
    summary = GraphService(args.db).summary(node_types=args.type, limit=args.limit)
    if args.json:
        _print_json(summary.to_dict())
        return 0
    print(f"Nodes: {summary.nodes}")
    print(f"Edges: {summary.edges}")
    print("By node type:")
    for name, count in sorted(summary.by_node_type.items()):
        print(f"  {name}: {count}")
    print("By relationship:")
    for name, count in sorted(summary.by_relationship.items()):
        print(f"  {name}: {count}")
    if args.type is not None or args.limit is not None:
        print("Nodes:")
        for node in summary.listed:
            print(f"  {_format_node_line(node)}")
    return 0


def _handle_neighbors(args: argparse.Namespace) -> int:
    """Execute the ``neighbors`` subcommand."""
    neighborhood = GraphService(args.db).neighbors(
        args.node_id,
        depth=args.depth,
        relationships=args.relationship,
        node_types=args.type,
        limit=args.limit,
    )
    node = neighborhood.node
    result = neighborhood.result
    related = [n for n in result.nodes if n.node_id != args.node_id]
    edges = list(result.edges)

    if args.json:
        _print_json(result.to_dict())
        return 0
    print(f"node: {_format_node_line(node)}")
    print(f"neighbors ({len(related)}):")
    for neighbor in related:
        print(f"  {_format_node_line(neighbor)}")
    print(f"edges ({len(edges)}):")
    for edge in edges:
        print(f"  {edge.source_id} -{edge.relationship.value}-> {edge.target_id}")
    return 0


def _handle_path(args: argparse.Namespace) -> int:
    """Execute the ``path`` subcommand."""
    path = GraphService(args.db).path(
        args.source, args.target, max_depth=args.depth, relationships=args.relationship
    )
    if args.json:
        _print_json(path.to_dict() if path is not None else None)
        return 0
    if path is None:
        print("No path found.")
        return 0
    print(f"path (length {path.length}):")
    print(f"  {_format_node_line(path.nodes[0])}")
    for index, edge in enumerate(path.edges):
        print(f"  -{edge.relationship.value}->")
        print(f"  {_format_node_line(path.nodes[index + 1])}")
    return 0


def _handle_export_graph(args: argparse.Namespace) -> int:
    """Execute the ``export-graph`` subcommand."""
    rendered = GraphService(args.db).export(args.format, node_types=args.type, limit=args.limit)
    if isinstance(rendered, dict):
        _print_json(rendered)
    else:
        print(rendered, end="")
    return 0


def _add_filter_arguments(command: argparse.ArgumentParser) -> None:
    """Attach the shared intelligence filter options to a subcommand."""
    command.add_argument("--project", default=None, help="Restrict analysis to one project.")
    command.add_argument("--person", default=None, help="Restrict analysis to one person.")
    command.add_argument("--meeting", type=_parse_meeting_ids, default=None, metavar="ID1,ID2,...")


def _add_intelligence_commands(
    subcommands: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the decision-intelligence subcommands."""
    insights_cmd = subcommands.add_parser(
        "insights",
        help="Discover organizational insights across meetings.",
        description="Run every insight provider over stored memory and the graph.",
    )
    _add_db_argument(insights_cmd)
    _add_filter_arguments(insights_cmd)
    insights_cmd.add_argument(
        "--type", type=_parse_insight_types, default=None, metavar="T1,T2,..."
    )
    insights_cmd.add_argument("--limit", type=int, default=None, help="Maximum insights to show.")
    insights_cmd.add_argument("--json", action="store_true", help="Emit insights as JSON.")
    insights_cmd.set_defaults(handler=_handle_insights)

    metrics_cmd = subcommands.add_parser(
        "metrics",
        help="Compute organizational-health metrics.",
        description="Compute deterministic health metrics from stored memory.",
    )
    _add_db_argument(metrics_cmd)
    _add_filter_arguments(metrics_cmd)
    metrics_cmd.add_argument("--json", action="store_true", help="Emit metrics as JSON.")
    metrics_cmd.add_argument(
        "--format",
        choices=["text", "json", "prometheus"],
        default="text",
        help="Output format (default: text). 'prometheus' adds runtime/system metrics.",
    )
    metrics_cmd.add_argument(
        "-o", "--output", type=Path, default=None, help="Write metrics to this file."
    )
    metrics_cmd.set_defaults(handler=_handle_metrics)

    rec_cmd = subcommands.add_parser(
        "recommendations",
        help="Generate evidence-backed recommendations.",
        description="Turn discovered insights into prioritised recommendations.",
    )
    _add_db_argument(rec_cmd)
    _add_filter_arguments(rec_cmd)
    rec_cmd.add_argument("--limit", type=int, default=None, help="Maximum recommendations.")
    rec_cmd.add_argument("--json", action="store_true", help="Emit recommendations as JSON.")
    rec_cmd.set_defaults(handler=_handle_recommendations)

    report_cmd = subcommands.add_parser(
        "report",
        help="Generate a full organizational-intelligence report.",
        description="Assemble metrics, insights, and recommendations into a report.",
    )
    _add_db_argument(report_cmd)
    _add_filter_arguments(report_cmd)
    report_cmd.add_argument(
        "--format", choices=REPORT_FORMATS, default="text", help="Report format (default: text)."
    )
    report_cmd.add_argument(
        "-o", "--output", type=Path, default=None, help="Write the report to this file."
    )
    report_cmd.set_defaults(handler=_handle_report)


def _filters_from_args(args: argparse.Namespace) -> AnalysisFilters:
    """Build :class:`AnalysisFilters` from shared CLI options."""
    return AnalysisFilters(
        project=args.project,
        person=args.person,
        meetings=args.meeting if args.meeting is not None else frozenset(),
    )


def _build_report(args: argparse.Namespace) -> InsightReport:
    """Open the stores, build the graph, and produce a report for ``args``."""
    filters = _filters_from_args(args)
    return IntelligenceService(args.db).report(filters)


def _handle_insights(args: argparse.Namespace) -> int:
    """Execute the ``insights`` subcommand."""
    report = _build_report(args)
    insights = list(report.insights)
    if args.type is not None:
        insights = [insight for insight in insights if insight.type in args.type]
    if args.limit is not None:
        insights = insights[: args.limit]

    if args.json:
        _print_json([insight.to_dict() for insight in insights])
        return 0
    if not insights:
        print("No insights found.")
        return 0
    for insight in insights:
        print(f"[{insight.severity}] ({insight.category}) {insight.title}")
        print(f"    {insight.detail}")
    return 0


def _handle_metrics(args: argparse.Namespace) -> int:
    """Execute the ``metrics`` subcommand."""
    report = _build_report(args)
    health = report.health

    fmt = "json" if args.json else args.format
    if fmt == "prometheus":
        text = _metrics_to_prometheus(health, args.db)
        _write_or_print(text, args.output)
        return 0
    if fmt == "json":
        payload = health.to_dict()
        if args.output is not None:
            args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
            print(f"Wrote metrics to {args.output}")
        else:
            _print_json(payload)
        return 0

    print(f"Reference date: {health.reference_date or 'n/a'}")
    print(f"Overall health: {health.overall:.4f}")
    print("Scores:")
    for key in sorted(health.scores):
        print(f"  {key}: {health.scores[key]:.4g}")
    print("Decisions:", health.decision.to_dict())
    print("Commitments:", health.commitment.to_dict())
    print("Risks:", health.risk.to_dict())
    print("Meetings:", health.meeting.to_dict())
    return 0


def _handle_recommendations(args: argparse.Namespace) -> int:
    """Execute the ``recommendations`` subcommand."""
    report = _build_report(args)
    recommendations = list(report.recommendations)
    if args.limit is not None:
        recommendations = recommendations[: args.limit]

    if args.json:
        _print_json([rec.to_dict() for rec in recommendations])
        return 0
    if not recommendations:
        print("No recommendations.")
        return 0
    for rec in recommendations:
        print(f"[{rec.priority}] ({rec.category}) {rec.title}")
        print(f"    {rec.detail}")
    return 0


def _handle_report(args: argparse.Namespace) -> int:
    """Execute the ``report`` subcommand."""
    report = _build_report(args)
    rendered = IntelligenceService(args.db).render(report, args.format)
    if args.output is not None:
        suffix = "" if rendered.endswith("\n") else "\n"
        args.output.write_text(rendered + suffix, encoding="utf-8")
        print(f"Wrote report to {args.output}")
    else:
        print(rendered, end="" if rendered.endswith("\n") else "\n")
    return 0


def _logs_path(db: Path) -> Path:
    """Return the structured-log JSON Lines path beside a database."""
    return db.with_name(db.name + ".logs.jsonl")


def _cli_logger(db: Path) -> StructuredLogger:
    """Build a logger that writes structured records beside the database."""
    return StructuredLogger(
        sink=JsonlFileLogSink(_logs_path(db)),
        clock=time.monotonic,
        now=utc_now,
    )


def _add_connector_commands(
    subcommands: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the connector, automation, scheduling, and logging subcommands."""
    import_dir_cmd = subcommands.add_parser(
        "import-dir",
        help="Import every supported transcript in a directory.",
        description="Import a directory of transcripts (txt/json/markdown/csv).",
    )
    import_dir_cmd.add_argument("path", type=Path, help="Directory of transcripts to import.")
    _add_db_argument(import_dir_cmd)
    import_dir_cmd.add_argument(
        "--recursive", action="store_true", help="Recurse into subdirectories."
    )
    import_dir_cmd.add_argument(
        "--pattern", default="*", help="Glob pattern for matching files (default: *)."
    )
    import_dir_cmd.add_argument(
        "--limit", type=int, default=None, help="Import at most this many files."
    )
    import_dir_cmd.add_argument(
        "--dry-run", action="store_true", help="Parse and count without writing."
    )
    import_dir_cmd.add_argument("--json", action="store_true", help="Emit the summary as JSON.")
    import_dir_cmd.set_defaults(handler=_handle_import_dir)

    export_choices = sorted(default_registry().export_formats())
    export_cmd = subcommands.add_parser(
        "export",
        help="Export organizational data to a destination.",
        description="Export reports, memories, graphs, or summaries in various formats.",
    )
    _add_db_argument(export_cmd)
    export_cmd.add_argument(
        "--format",
        choices=export_choices,
        default="markdown",
        help="Export format (default: markdown).",
    )
    export_cmd.add_argument(
        "-o", "--output", type=Path, default=None, help="Write the export to this file."
    )
    export_cmd.add_argument(
        "--dry-run", action="store_true", help="Render without writing the destination."
    )
    export_cmd.add_argument("--json", action="store_true", help="Emit the result as JSON.")
    export_cmd.set_defaults(handler=_handle_export)

    automate_cmd = subcommands.add_parser(
        "automate",
        help="Run a declarative pipeline (YAML or JSON).",
        description="Validate and run an import -> graph -> intelligence -> export pipeline.",
    )
    automate_cmd.add_argument("config", type=Path, help="Pipeline configuration file.")
    _add_db_argument(automate_cmd)
    automate_cmd.add_argument(
        "--dry-run", action="store_true", help="Run the pipeline without writing."
    )
    automate_cmd.add_argument("--json", action="store_true", help="Emit the result as JSON.")
    automate_cmd.set_defaults(handler=_handle_automate)

    jobs_cmd = subcommands.add_parser(
        "jobs",
        help="List recorded automation runs.",
        description="Show the history of automation runs recorded beside the database.",
    )
    _add_db_argument(jobs_cmd)
    jobs_cmd.add_argument("--limit", type=int, default=None, help="Show at most this many runs.")
    jobs_cmd.add_argument("--json", action="store_true", help="Emit the history as JSON.")
    jobs_cmd.set_defaults(handler=_handle_jobs)

    schedule_cmd = subcommands.add_parser(
        "schedule",
        help="Show upcoming run times for a pipeline schedule.",
        description="Simulate the next run times for a pipeline's schedule (no daemon).",
    )
    schedule_cmd.add_argument("config", type=Path, help="Pipeline configuration file.")
    schedule_cmd.add_argument(
        "--after",
        type=_parse_iso_datetime,
        default=None,
        metavar="ISO8601",
        help="Compute runs after this time (default: now).",
    )
    schedule_cmd.add_argument(
        "--count", type=int, default=5, help="Number of upcoming runs to show (default: 5)."
    )
    schedule_cmd.add_argument("--json", action="store_true", help="Emit the schedule as JSON.")
    schedule_cmd.set_defaults(handler=_handle_schedule)

    logs_cmd = subcommands.add_parser(
        "logs",
        help="Show structured connector/automation logs.",
        description="Read machine-readable logs recorded beside the database.",
    )
    _add_db_argument(logs_cmd)
    logs_cmd.add_argument("--correlation", default=None, help="Filter logs by correlation id.")
    logs_cmd.add_argument("--limit", type=int, default=None, help="Show at most this many records.")
    logs_cmd.add_argument("--json", action="store_true", help="Emit logs as JSON.")
    logs_cmd.set_defaults(handler=_handle_logs)


def _handle_import_dir(args: argparse.Namespace) -> int:
    """Execute the ``import-dir`` subcommand."""
    logger = _cli_logger(args.db)
    result = MeetingService(args.db).import_path(
        args.path,
        recursive=args.recursive,
        pattern=args.pattern,
        dry_run=args.dry_run,
        limit=args.limit,
        logger=logger,
    )
    if args.json:
        _print_json(result.to_dict())
    else:
        print("\n".join(result.summary_lines()))
    return 0


def _handle_export(args: argparse.Namespace) -> int:
    """Execute the ``export`` subcommand."""
    logger = _cli_logger(args.db)
    result = ExportService(args.db).export(
        args.format,
        destination=str(args.output) if args.output is not None else None,
        dry_run=args.dry_run,
        logger=logger,
    )
    if args.json:
        _print_json(result.to_dict())
    elif result.destination is not None or args.dry_run:
        print("\n".join(result.summary_lines()))
    else:
        content = result.content or ""
        print(content, end="" if content.endswith("\n") else "\n")
    return 0


def _handle_automate(args: argparse.Namespace) -> int:
    """Execute the ``automate`` subcommand."""
    result = AutomationService(args.db).run_file(args.config, dry_run=args.dry_run)
    if args.json:
        _print_json(result.to_dict())
    else:
        print("\n".join(result.summary_lines()))
    return 1 if result.status.value == "failure" else 0


def _handle_jobs(args: argparse.Namespace) -> int:
    """Execute the ``jobs`` subcommand."""
    records = AutomationService(args.db).jobs(limit=args.limit)
    if args.json:
        _print_json(records)
        return 0
    if not records:
        print("No automation runs recorded.")
        return 0
    for record in records:
        stages = record.get("stages", [])
        count = len(stages) if isinstance(stages, list) else 0
        print(
            f"{record['started_at']}  {record['job']}  [{record['status']}]  "
            f"{count} stages  {record['correlation_id']}"
        )
    return 0


def _handle_schedule(args: argparse.Namespace) -> int:
    """Execute the ``schedule`` subcommand."""
    job = AutomationService.load(args.config)
    after = args.after if args.after is not None else datetime.now(timezone.utc)
    runs = simulate(job.schedule, start=after, count=args.count)
    if args.json:
        _print_json(
            {
                "job": job.name,
                "frequency": job.schedule.frequency.value,
                "runs": [run.isoformat() for run in runs],
            }
        )
        return 0
    print(f"job: {job.name}")
    print(f"frequency: {job.schedule.frequency.value}")
    if not runs:
        print("No upcoming runs (manual schedule or already elapsed).")
    else:
        for run in runs:
            print(run.isoformat())
    return 0


def _handle_logs(args: argparse.Namespace) -> int:
    """Execute the ``logs`` subcommand."""
    records = AutomationService(args.db).logs(correlation_id=args.correlation, limit=args.limit)
    if args.json:
        _print_json(records)
        return 0
    if not records:
        print("No logs recorded.")
        return 0
    for record in records:
        stage = record.get("stage") or "-"
        connector = record.get("connector")
        suffix = f" ({connector})" if connector else ""
        print(
            f"[{record['level']}] {record['correlation_id']} {stage}{suffix}: {record['message']}"
        )
    return 0


def _format_node_line(node: GraphNode) -> str:
    """Render a one-line summary of a graph node."""
    text = " ".join(node.label.split())
    if len(text) > 60:
        text = text[:59].rstrip() + "…"
    return f"{node.node_id}  [{node.node_type.value}]  {text}"


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


def _positive_int(value: str) -> int:
    """Argparse type that accepts only integers greater than or equal to one."""
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("value must be >= 1")
    return number


def _add_demo_command(subcommands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the guided end-to-end ``demo`` subcommand."""
    demo_cmd = subcommands.add_parser(
        "demo",
        help="Run a guided, end-to-end demonstration of the whole system.",
        description=(
            "Import example meetings, build memory, search, build the graph, "
            "generate intelligence, and render a report — all in under a minute."
        ),
    )
    demo_cmd.add_argument(
        "--db",
        type=Path,
        default=None,
        help="Database path (default: a temporary database that is discarded).",
    )
    demo_cmd.add_argument(
        "--dataset",
        choices=sorted(DATASET_PRESETS),
        default="small",
        help="Example dataset to import (default: small).",
    )
    demo_cmd.add_argument(
        "--query",
        default="risk",
        help="Search query to demonstrate retrieval (default: 'risk').",
    )
    demo_cmd.add_argument(
        "--keep",
        action="store_true",
        help="Keep the generated database instead of discarding it.",
    )
    demo_cmd.set_defaults(handler=_handle_demo)


def _demo_step(number: int, title: str) -> None:
    """Print a numbered demo section header."""
    print()
    print(f"[{number}/6] {title}")
    print("-" * 60)


def _run_demo(db: Path, dataset: str, query: str) -> None:
    """Execute the end-to-end demo flow against ``db``."""
    spec = get_preset(dataset)

    _demo_step(1, "Import example meetings")
    with tempfile.TemporaryDirectory(prefix="mm-demo-") as tmp:
        data_dir = Path(tmp) / "history"
        write_dataset(spec, data_dir)
        result = MeetingService(db).import_path(data_dir, recursive=True)
    print(
        f"Imported {result.meetings_imported} meetings and stored "
        f"{result.memories_stored} memories from the '{spec.name}' dataset."
    )

    _demo_step(2, "Build organizational memory")
    stats = MeetingService(db).stats()
    print(f"Stored memory now spans {stats.meetings} meetings / {stats.memories} memories:")
    for memory_type in sorted(stats.by_type):
        print(f"  {memory_type:<12} {stats.by_type[memory_type]}")

    _demo_step(3, "Retrieve memories")
    search = RetrievalService(db).search(RetrievalQuery(text=query, limit=3))
    print(f"Top matches for {query!r}:")
    for ranked in search.ranked[:3]:
        speaker = ranked.memory.speaker or "?"
        print(
            f"  ({ranked.score:.3f}) [{ranked.memory.memory_type}] {speaker}: {ranked.memory.text}"
        )

    _demo_step(4, "Build the organizational graph")
    summary = GraphService(db).summary()
    print(f"Graph: {summary.nodes} nodes, {summary.edges} edges.")
    for node_type in sorted(summary.by_node_type):
        print(f"  {node_type:<14} {summary.by_node_type[node_type]}")

    _demo_step(5, "Generate intelligence")
    report = IntelligenceService(db).report(AnalysisFilters())
    print(f"Overall health: {report.health.overall:.3f}")
    print(f"Discovered {len(report.insights)} insights:")
    for insight in list(report.insights)[:3]:
        print(f"  [{insight.severity}] {insight.title}")
    for recommendation in list(report.recommendations)[:1]:
        print(f"Top recommendation: {recommendation.title}")

    _demo_step(6, "Render a report")
    rendered = IntelligenceService(db).render(report, "markdown")
    preview = rendered.strip().splitlines()
    for line in preview[:8]:
        print(f"  {line}")
    print(f"  ... ({len(preview)} total lines)")


def _handle_demo(args: argparse.Namespace) -> int:
    """Execute the ``demo`` subcommand."""
    start = time.perf_counter()
    print("=" * 60)
    print("  Meeting Memory System — guided demo")
    print("=" * 60)

    if args.db is not None:
        _run_demo(args.db, args.dataset, args.query)
        database = args.db
    else:
        with tempfile.TemporaryDirectory(prefix="mm-demo-db-") as tmp:
            database = Path(tmp) / "demo.db"
            _run_demo(database, args.dataset, args.query)
            if args.keep:
                kept = Path.cwd() / "demo.db"
                kept.write_bytes(database.read_bytes())
                database = kept

    elapsed = time.perf_counter() - start
    print()
    print("=" * 60)
    print(f"Demo complete in {elapsed:.2f}s.")
    if args.db is not None or args.keep:
        print(f"Explore the data with: meeting-memory report --db {database}")
        print(f"Serve the API + dashboard: MEETING_MEMORY_DB={database} \\")
        print("    uvicorn meeting_memory.api.app:app --port 8000")
        print("Then open http://127.0.0.1:8000/dashboard and http://127.0.0.1:8000/docs")
    else:
        print("Re-run with --keep to persist the database and explore the API/dashboard:")
        print("  meeting-memory demo --keep")
    print("=" * 60)
    return 0


def _add_ops_commands(subcommands: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the Phase 9 production-operations subcommands."""
    bench_cmd = subcommands.add_parser(
        "benchmark",
        help="Run reproducible performance benchmarks over a seeded dataset.",
        description="Generate a deterministic dataset and benchmark the core operations.",
    )
    bench_cmd.add_argument(
        "--dataset",
        choices=sorted(DATASET_PRESETS),
        default="small",
        help="Benchmark dataset size (default: small).",
    )
    bench_cmd.add_argument(
        "--iterations",
        type=_positive_int,
        default=1,
        help="Number of iterations per benchmark (default: 1).",
    )
    bench_cmd.add_argument("--json", action="store_true", help="Emit the report as JSON.")
    bench_cmd.add_argument("-o", "--output", type=Path, default=None, help="Write the report here.")
    bench_cmd.add_argument(
        "--charts",
        type=Path,
        default=None,
        metavar="DIR",
        help="Render per-operation SVG charts into this directory.",
    )
    bench_cmd.set_defaults(handler=_handle_benchmark)

    replay_cmd = subcommands.add_parser(
        "replay",
        help="Replay stored meetings in chronological order.",
        description="Reconstruct and replay the meeting timeline, optionally filtered.",
    )
    _add_db_argument(replay_cmd)
    replay_cmd.add_argument("--project", default=None, help="Only replay this project.")
    replay_cmd.add_argument("--person", default=None, help="Only replay meetings with this person.")
    replay_cmd.add_argument("--date", default=None, help="Only replay meetings on this date.")
    replay_cmd.add_argument(
        "--from", dest="date_from", default=None, help="Earliest meeting date (inclusive)."
    )
    replay_cmd.add_argument(
        "--to", dest="date_to", default=None, help="Latest meeting date (inclusive)."
    )
    replay_cmd.add_argument(
        "--speed", type=float, default=1.0, help="Replay speed multiplier (default: 1.0)."
    )
    replay_cmd.add_argument(
        "--step-delay",
        type=float,
        default=0.0,
        help="Base seconds to wait between steps before scaling by --speed.",
    )
    replay_cmd.add_argument(
        "--timeline", action="store_true", help="Print the reconstructed timeline instead of a run."
    )
    replay_cmd.add_argument("--json", action="store_true", help="Emit output as JSON.")
    replay_cmd.add_argument("-o", "--output", type=Path, default=None, help="Write output here.")
    replay_cmd.set_defaults(handler=_handle_replay)

    backup_cmd = subcommands.add_parser(
        "backup",
        help="Back up the database (physical copy or logical snapshot).",
        description="Create a checksummed backup or a portable JSON snapshot.",
    )
    _add_db_argument(backup_cmd)
    backup_cmd.add_argument(
        "-o", "--output", type=Path, required=True, help="Destination backup/snapshot path."
    )
    backup_cmd.add_argument(
        "--snapshot", action="store_true", help="Write a logical JSON snapshot instead of a copy."
    )
    backup_cmd.add_argument("--json", action="store_true", help="Emit the manifest as JSON.")
    backup_cmd.set_defaults(handler=_handle_backup)

    restore_cmd = subcommands.add_parser(
        "restore",
        help="Restore the database from a backup or snapshot.",
        description="Restore a checksummed backup or import a logical JSON snapshot.",
    )
    _add_db_argument(restore_cmd)
    restore_cmd.add_argument("input", type=Path, help="Backup/snapshot file to restore from.")
    restore_cmd.add_argument(
        "--snapshot", action="store_true", help="Treat the input as a logical JSON snapshot."
    )
    restore_cmd.add_argument(
        "--no-verify", action="store_true", help="Skip integrity/checksum verification."
    )
    restore_cmd.add_argument("--json", action="store_true", help="Emit the report as JSON.")
    restore_cmd.set_defaults(handler=_handle_restore)

    profile_cmd = subcommands.add_parser(
        "profile",
        help="Profile CPU and memory for a core operation.",
        description="Run an operation under cProfile and tracemalloc and report hot paths.",
    )
    _add_db_argument(profile_cmd)
    profile_cmd.add_argument(
        "--operation",
        choices=["import", "search", "graph", "intelligence", "report"],
        default="intelligence",
        help="Operation to profile (default: intelligence).",
    )
    profile_cmd.add_argument(
        "--dataset",
        choices=sorted(DATASET_PRESETS),
        default="small",
        help="Dataset to import when profiling 'import' (default: small).",
    )
    profile_cmd.add_argument(
        "--top", type=_positive_int, default=10, help="Number of hot entries to show (default: 10)."
    )
    profile_cmd.add_argument("--json", action="store_true", help="Emit the profile as JSON.")
    profile_cmd.add_argument("-o", "--output", type=Path, default=None, help="Write output here.")
    profile_cmd.set_defaults(handler=_handle_profile)


def _write_or_print(text: str, output: Path | None) -> None:
    """Write ``text`` to ``output`` (newline-terminated) or print it to stdout."""
    if output is not None:
        suffix = "" if text.endswith("\n") else "\n"
        output.write_text(text + suffix, encoding="utf-8")
        print(f"Wrote output to {output}")
    else:
        print(text)


def _metrics_to_prometheus(health: OrganizationalHealth, db: Path) -> str:
    """Render organizational-health, store, and system metrics as Prometheus text."""
    collector = MetricsCollector()
    collector.gauge("meeting_memory_health_overall").set(health.overall)
    for key, value in health.scores.items():
        collector.gauge(f"meeting_memory_health_score_{key}").set(value)

    stats = MeetingService(db).stats()
    collector.gauge("meeting_memory_meetings_total").set(stats.meetings)
    collector.gauge("meeting_memory_memories_total").set(stats.memories)
    for memory_type, count in stats.by_type.items():
        collector.gauge(f"meeting_memory_memories_type_{memory_type}").set(count)

    system = SystemMetrics.capture()
    collector.gauge("meeting_memory_process_max_rss_bytes").set(system.max_rss_bytes)
    collector.gauge("meeting_memory_process_user_cpu_seconds").set(system.user_cpu_seconds)
    collector.gauge("meeting_memory_process_threads").set(system.thread_count)
    return collector.to_prometheus()


def _handle_benchmark(args: argparse.Namespace) -> int:
    """Execute the ``benchmark`` subcommand."""
    report = run_benchmarks(get_preset(args.dataset), iterations=args.iterations)
    if args.json:
        _write_or_print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False), args.output)
    else:
        _write_or_print(report.render_text(), args.output)
    if args.charts is not None:
        written = write_report_charts(report, args.charts)
        for path in written:
            print(f"chart: {path}")
    return 0


def _render_replay_timeline(timeline: ReplayTimeline) -> str:
    """Render a reconstructed replay timeline as readable text."""
    start, end = timeline.date_range
    lines = [
        f"Timeline: {timeline.filter.describe()}",
        f"  meetings={timeline.meeting_count} memories={timeline.memory_count} "
        f"range={start or '-'}..{end or '-'}",
    ]
    for event in timeline.events:
        lines.append(
            f"  [{event.index + 1:>3}] {event.meeting.date or '-'}  "
            f"{event.meeting.title or event.meeting.meeting_id}  "
            f"(+{len(event.memories)}, total {event.cumulative_memories})"
        )
    return "\n".join(lines)


def _render_replay_result(result: ReplayResult) -> str:
    """Render a completed replay run as readable text."""
    lines = [
        f"Replay: {result.timeline.filter.describe()}",
        f"  steps={result.steps_played} meetings={result.timeline.meeting_count} "
        f"memories={result.memories_played} speed={result.speed}",
    ]
    for memory_type in sorted(result.final_by_type):
        lines.append(f"  {memory_type}: {result.final_by_type[memory_type]}")
    return "\n".join(lines)


def _handle_replay(args: argparse.Namespace) -> int:
    """Execute the ``replay`` subcommand."""
    flt = ReplayFilter(
        project=args.project,
        person=args.person,
        date=args.date,
        date_from=args.date_from,
        date_to=args.date_to,
    )
    engine = ReplayEngine(args.db)
    if args.timeline:
        timeline = engine.timeline(flt)
        if args.json:
            _write_or_print(
                json.dumps(timeline.to_dict(), indent=2, ensure_ascii=False), args.output
            )
        else:
            _write_or_print(_render_replay_timeline(timeline), args.output)
        return 0

    result = engine.replay(flt, speed=args.speed, step_delay=args.step_delay)
    if args.json:
        _write_or_print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False), args.output)
    else:
        _write_or_print(_render_replay_result(result), args.output)
    return 0


def _handle_backup(args: argparse.Namespace) -> int:
    """Execute the ``backup`` subcommand."""
    if args.snapshot:
        snapshot = export_snapshot(args.db, args.output)
        payload = {
            "type": "snapshot",
            "output": str(args.output),
            "meetings": len(snapshot.meetings),
            "memories": len(snapshot.memories),
            "schema_version": snapshot.schema_version,
            "checksum": snapshot.checksum,
        }
        if args.json:
            _print_json(payload)
        else:
            print(
                f"Wrote snapshot to {args.output} "
                f"({payload['meetings']} meetings, {payload['memories']} memories)"
            )
            print(f"checksum: {snapshot.checksum}")
        return 0

    manifest = BackupManager(args.db).backup(args.output)
    if args.json:
        _print_json(manifest.to_dict())
    else:
        print(
            f"Backed up {manifest.meetings} meetings / {manifest.memories} memories "
            f"to {manifest.backup_path}"
        )
        print(f"checksum: {manifest.checksum}")
    return 0


def _handle_restore(args: argparse.Namespace) -> int:
    """Execute the ``restore`` subcommand."""
    verify = not args.no_verify
    if args.snapshot:
        report = import_snapshot(args.input, args.db, verify=verify)
    else:
        report = BackupManager(args.db).restore(args.input, verify=verify)
    if args.json:
        _print_json(report.to_dict())
    else:
        print(
            f"Restored: ok={report.ok} meetings={report.meetings} "
            f"memories={report.memories} integrity={report.integrity}"
        )
    return 0


def _profile_search(db: Path) -> object:
    """Profiling target: a representative ranked retrieval query."""
    return RetrievalService(db).search(RetrievalQuery(text="risk", limit=20))


def _profile_graph(db: Path) -> object:
    """Profiling target: build and summarise the knowledge graph."""
    return GraphService(db).summary()


def _profile_intelligence(db: Path) -> object:
    """Profiling target: generate the full intelligence report."""
    return IntelligenceService(db).report(AnalysisFilters())


def _profile_report(db: Path) -> object:
    """Profiling target: render the intelligence report to markdown."""
    service = IntelligenceService(db)
    return service.render(service.report(AnalysisFilters()), "markdown")


def _profile_import(db: Path, data_dir: Path) -> object:
    """Profiling target: import a generated dataset."""
    return MeetingService(db).import_path(data_dir, recursive=True)


def _handle_profile(args: argparse.Namespace) -> int:
    """Execute the ``profile`` subcommand."""
    operation = args.operation
    if operation == "import":
        with tempfile.TemporaryDirectory(prefix="mm-profile-") as tmp:
            data_dir = Path(tmp) / "data"
            write_dataset(get_preset(args.dataset), data_dir)
            db_path = Path(tmp) / "profile.db"
            _, cpu = profile_cpu(_profile_import, db_path, data_dir, top=args.top)
            _, memory = profile_memory(_profile_import, db_path, data_dir, top=args.top)
    else:
        targets = {
            "search": _profile_search,
            "graph": _profile_graph,
            "intelligence": _profile_intelligence,
            "report": _profile_report,
        }
        target = targets[operation]
        _, cpu = profile_cpu(target, args.db, top=args.top)
        _, memory = profile_memory(target, args.db, top=args.top)

    payload = {"operation": operation, "cpu": cpu.to_dict(), "memory": memory.to_dict()}
    if args.json:
        _write_or_print(json.dumps(payload, indent=2, ensure_ascii=False), args.output)
        return 0

    lines = [
        f"Profile: {operation}",
        f"  cpu total: {cpu.total_seconds:.6f}s",
        f"  memory peak: {memory.peak_bytes} bytes",
        "  hot functions:",
    ]
    for entry in cpu.entries:
        lines.append(f"    {entry.cumulative_seconds:.6f}s  {entry.calls:>6}x  {entry.function}")
    _write_or_print("\n".join(lines), args.output)
    return 0


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
