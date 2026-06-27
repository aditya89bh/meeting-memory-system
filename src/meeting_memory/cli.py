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
from .graph import (
    EXPORT_FORMATS,
    EntityType,
    GraphEdge,
    GraphEngine,
    GraphNode,
    RelationshipType,
    SQLiteGraphStore,
    build_graph,
    export_graph,
)
from .intelligence import (
    REPORT_FORMATS,
    AnalysisFilters,
    InsightReport,
    InsightType,
    IntelligenceEngine,
)
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


def _build_graph_store(db: Path) -> SQLiteGraphStore:
    """Build the graph from the memory store and return an open graph store."""
    graph_store = SQLiteGraphStore(db)
    with SQLiteMemoryStore(db) as memory_store:
        build_graph(memory_store, graph_store)
    return graph_store


def _filtered_graph(
    store: SQLiteGraphStore,
    node_types: frozenset[EntityType] | None,
    limit: int | None,
) -> tuple[list[GraphNode], list[GraphEdge]]:
    """Return nodes (optionally filtered/limited) and the edges among them."""
    nodes = store.list_nodes(node_types=node_types, limit=limit)
    keep = {node.node_id for node in nodes}
    edges = [
        edge for edge in store.list_edges() if edge.source_id in keep and edge.target_id in keep
    ]
    return nodes, edges


def _handle_graph(args: argparse.Namespace) -> int:
    """Execute the ``graph`` subcommand."""
    store = _build_graph_store(args.db)
    try:
        by_node_type: dict[str, int] = {}
        for node in store.list_nodes():
            by_node_type[node.node_type.value] = by_node_type.get(node.node_type.value, 0) + 1
        by_relationship: dict[str, int] = {}
        for edge in store.list_edges():
            by_relationship[edge.relationship.value] = (
                by_relationship.get(edge.relationship.value, 0) + 1
            )
        listed = store.list_nodes(node_types=args.type, limit=args.limit)
        summary = {
            "nodes": store.count_nodes(),
            "edges": store.count_edges(),
            "by_node_type": dict(sorted(by_node_type.items())),
            "by_relationship": dict(sorted(by_relationship.items())),
            "listed": [node.to_dict() for node in listed],
        }
    finally:
        store.close()

    if args.json:
        _print_json(summary)
        return 0
    print(f"Nodes: {summary['nodes']}")
    print(f"Edges: {summary['edges']}")
    print("By node type:")
    for name, count in sorted(by_node_type.items()):
        print(f"  {name}: {count}")
    print("By relationship:")
    for name, count in sorted(by_relationship.items()):
        print(f"  {name}: {count}")
    if args.type is not None or args.limit is not None:
        print("Nodes:")
        for node in listed:
            print(f"  {_format_node_line(node)}")
    return 0


def _handle_neighbors(args: argparse.Namespace) -> int:
    """Execute the ``neighbors`` subcommand."""
    store = _build_graph_store(args.db)
    try:
        node = store.get_node(args.node_id)
        result = GraphEngine(store).neighbors(
            args.node_id,
            depth=args.depth,
            relationships=args.relationship,
            node_types=args.type,
            limit=args.limit,
        )
        payload = result.to_dict()
        related = [n for n in result.nodes if n.node_id != args.node_id]
        edges = list(result.edges)
    finally:
        store.close()

    if args.json:
        _print_json(payload)
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
    store = _build_graph_store(args.db)
    try:
        path = GraphEngine(store).find_path(
            args.source, args.target, max_depth=args.depth, relationships=args.relationship
        )
        payload = path.to_dict() if path is not None else None
    finally:
        store.close()

    if args.json:
        _print_json(payload)
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
    store = _build_graph_store(args.db)
    try:
        nodes, edges = _filtered_graph(store, args.type, args.limit)
        rendered = export_graph(nodes, edges, args.format)
    finally:
        store.close()

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
    with SQLiteMemoryStore(args.db) as memory_store:
        graph_store = SQLiteGraphStore(args.db)
        try:
            return IntelligenceEngine().analyze(memory_store, graph_store, filters=filters)
        finally:
            graph_store.close()


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

    if args.json:
        _print_json(health.to_dict())
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
    rendered = IntelligenceEngine().render(report, args.format)
    if args.output is not None:
        suffix = "" if rendered.endswith("\n") else "\n"
        args.output.write_text(rendered + suffix, encoding="utf-8")
        print(f"Wrote report to {args.output}")
    else:
        print(rendered, end="" if rendered.endswith("\n") else "\n")
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
