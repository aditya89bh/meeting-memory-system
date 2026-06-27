# Meeting Memory Extraction (Phase 2)

This document describes the deterministic, rule-based memory extraction layer:
the pipeline, the memory schema, how confidence is scored, the supported trigger
phrases, the known limitations, and the planned extension point for an
LLM-backed extractor.

Phase 2 is intentionally **not** a generic summarizer. It extracts discrete,
auditable *memory primitives* from a parsed `Meeting`, with no external LLM APIs,
no network access, and no randomness — the same input always produces the same
output.

## Pipeline

```
Meeting
  │
  ▼  scan each utterance in order
Extractor registry  ──▶  memory candidates
  │
  ▼  deduplicate (optional)
  ▼  validate (drop invalid records, collect warnings)
  ▼  filter by minimum confidence (optional)
ExtractionResult
```

Implemented by `meeting_memory.extraction.ExtractionPipeline` (and the
module-level `extract_memories` convenience):

1. **Scan.** Every utterance is passed to every *active* extractor. Each
   extractor inspects a single utterance and returns zero or one memory of its
   type, so extraction is `O(utterances × extractors)` and order-stable.
2. **Deduplicate.** Records of the same type whose text matches after light
   normalization (lowercase, punctuation stripped, whitespace collapsed) are
   collapsed, keeping the highest-confidence record. See `dedup.py`.
3. **Validate.** Each candidate is checked (see [Validation](#validation)).
   Invalid records are dropped and reported as `warnings` instead of failing the
   whole run.
4. **Filter.** Records below `min_confidence` are removed.
5. **Order.** Surviving records are sorted by `(utterance_index, memory_type)`
   using the canonical type order for stable, readable output.

### Configuration

`ExtractionConfig` controls a run:

| Field            | Default | Meaning                                                   |
| ---------------- | ------- | --------------------------------------------------------- |
| `enabled_types`  | `None`  | Set of `MemoryType` to extract; `None` means all types.   |
| `min_confidence` | `0.0`   | Drop memories scoring below this threshold.               |
| `deduplicate`    | `True`  | Collapse duplicate memories within the meeting.           |

The pipeline is also constructed with an extractor registry (defaults to one
instance of every built-in extractor), so callers can add, remove, or reorder
extractors without changing the pipeline itself.

### Meeting id

Each result has a `meeting_id`. When not supplied explicitly it is derived from
the meeting metadata: the source file stem, then a slug of the title, falling
back to the literal `"meeting"`.

## Memory schema

All records are immutable (`frozen=True`) subclasses of `ExtractedMemory`.

### `ExtractedMemory` (shared fields)

| Field             | Type                  | Notes                                            |
| ----------------- | --------------------- | ------------------------------------------------ |
| `memory_id`       | `str`                 | Stable id: `"{meeting_id}:{type}:{utterance}"`.  |
| `memory_type`     | `MemoryType`          | Fixed per subclass (class variable).             |
| `text`            | `str`                 | The full utterance text.                         |
| `speaker`         | `str \| None`         | Speaker name, if known.                          |
| `meeting_id`      | `str`                 | Owning meeting id.                               |
| `utterance_index` | `int`                 | Index of the source utterance.                   |
| `evidence`        | `EvidenceSpan`        | Exact triggering substring + offsets.            |
| `confidence`      | `float`               | Bounded score in `[0.0, 1.0]`.                   |
| `extracted_at`    | `datetime \| None`    | When the record was produced.                    |
| `metadata`        | `dict[str, str]`      | Extra info; always includes the matched trigger. |

### `EvidenceSpan`

`utterance_index`, `start`, `end` (character offsets into the utterance text),
and the literal `text` of the span.

### Subclasses

`DecisionMemory`, `OpenLoopMemory`, `RiskMemory`, `AssumptionMemory`,
`QuestionMemory`, and `FactMemory` add no fields. `CommitmentMemory` adds:

- `owner: str | None` — the assignee (the speaker for first-person commitments,
  or the name following "assigned to …").
- `due: str | None` — an explicit deadline phrase (e.g. "by Friday").

### `ExtractionResult`

`meeting_id`, `memories` (tuple), `meeting_metadata` (dict), and `warnings`
(tuple). It also exposes `total`, `counts()` (per type, non-zero only, in
canonical order), `grouped()` (memories grouped by type), and `to_dict()` for
JSON serialization.

## Confidence scoring

Confidence is a bounded, deterministic score in `[0.0, 1.0]`, rounded to three
decimals. It is derived only from the matched phrase and a few textual signals —
there is no learning or randomness.

```
confidence = clamp(base + boost - penalty)
```

- **Base** — each trigger phrase declares a base strength:

  | Constant      | Value | Used for                                  |
  | ------------- | ----- | ----------------------------------------- |
  | `VERY_HIGH`   | 0.95  | Unambiguous phrases ("we decided", a "?") |
  | `HIGH`        | 0.85  | Strong phrases ("approved", "blocker")    |
  | `MEDIUM_HIGH` | 0.75  | Fairly strong ("we will use", "can we")   |
  | `MEDIUM`      | 0.6   | Moderate ("we will", "pending")           |
  | `LOW`         | 0.45  | Weak / generic signals                    |

- **Hedging penalty** (`-0.2`) — applied when the utterance contains uncertainty
  language such as "maybe", "might", "I think", "not sure", "could be". (Note
  this means a "might fail" risk is deliberately scored lower, because "might"
  is itself a hedge.)
- **Boosts** — corroborating signals raise the score, e.g. a commitment that
  names **both** an owner and a deadline (`+0.1`), or a fact containing a
  concrete quantitative signal — a number, percentage, currency amount, quarter,
  or year (`+0.15`).
- When the strongest rule ties on base score, the earliest match in the text
  wins.

## Supported phrases

Phrases are matched case-insensitively on word boundaries. The list below is
representative, not exhaustive — see each extractor in
`src/meeting_memory/extraction/extractors/` for the authoritative patterns.

### Decisions (`decision`)
"we decided" / "we've decided", "we agreed", "(the/final) decision is",
"final call", "let's go with", "approved", "we will use", "we'll go with".

### Commitments (`commitment`)
"I will" / "I'll", "assigned to <Name>", "please take", "please handle/own/…",
"we will", "can you", "by <weekday>", "before (the) next meeting". Owner and due
date are captured when present.

### Open loops (`open_loop`)
"need(s) to (be) decide(d)", "to be confirmed/decided/determined",
"(un)resolved" / "not resolved", "TBD", "open question", "still open",
"follow up", "circle back", "pending".

### Risks (`risk`)
"block(er/ed/ing)", "might/may/could fail", "risk(s/y)", "concern(s/ed)",
"depend(s/ency/encies/ent)", "delay(s/ed/ing)", "bottleneck".

### Assumptions (`assumption`)
"based on the assumption", "we (are) assume/assuming", "assume/assumption",
"if this holds", "presumably".

### Questions (`question`)
Any utterance ending with "?" (high confidence), plus "the question is",
"can we", "should we", "do we", "what about".

### Facts (`fact`)
Declarative statements (never questions) containing project, customer,
requirement, budget/constraint, timeline, or metric language (e.g. "customers",
"requirement", "budget", "deadline"/"launch"/"timeline", "revenue"/"uptime"/
"users"). Boosted when a concrete number/percentage/amount/quarter/year appears.

## Validation

Before a record is returned it must satisfy `check_memory`:

- `memory_id` is present,
- `memory_type` is a valid `MemoryType`,
- `confidence` is within `[0.0, 1.0]`,
- `meeting_id` is present,
- `text` is non-empty,
- `utterance_index` references a real utterance,
- `evidence.utterance_index` references a real utterance.

`validate_memory` raises `ExtractionValidationError` on the first problem;
`partition_valid` (used by the pipeline) is non-raising and turns problems into
`warnings`.

## Known limitations

- **Explicit phrases only.** Paraphrased, implicit, or unusually phrased
  statements are missed.
- **No cross-utterance reasoning.** A question that is later answered is still
  reported as a question; genuinely unanswered questions are not inferred.
- **False positives.** Trigger words used casually (e.g. "no risk there") can
  still match. Confidence and `min_confidence` help manage this.
- **No semantic understanding.** There is no summarization, paraphrasing, or
  meaning-level normalization.
- **English-centric** trigger phrases.

## Future LLM extraction extension point

The architecture is designed so a model-backed extractor can be added without
disturbing the rest of the system:

- Implement the `Extractor` protocol (a `memory_type` and an
  `extract(utterance, context) -> list[ExtractedMemory]` method), or a
  meeting-level variant, and register it with `ExtractionPipeline(extractors=…)`.
- Emit the same `ExtractedMemory` subclasses, so deduplication, validation,
  confidence handling, filtering, and serialization all continue to work
  unchanged.
- Keep the deterministic extractors as a fast, offline baseline and a fallback,
  layering the LLM extractor on top (e.g. for higher recall or paraphrase
  handling) behind a configuration flag.

This keeps Phase 2 useful and fully testable today while leaving a clean seam for
a future, optional LLM-powered phase.
