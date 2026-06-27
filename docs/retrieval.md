# Retrieval engine (Phase 4)

Phase 4 turns the persistent store from Phase 3 into a searchable organizational
memory. It answers questions that span many meetings — "show every decision about
Project X", "what commitments are still active?", "which risks appeared in March?"
— and explains why each result was returned.

Like every other layer, retrieval is **deterministic**: the same database and the
same query always produce the same ranked, explained output. There are no LLM
APIs, embeddings, vector databases, or external search engines anywhere in the
pipeline.

## Architecture

```
meeting_memory/retrieval/
├── models.py     # RetrievalQuery, RetrievalFilter, RankedMemory, ContextWindow, ...
├── planner.py    # QueryPlanner + PlannerVocabulary (text ▶ filters)
├── engine.py     # MemoryRetriever (filter ▶ rank ▶ order ▶ paginate ▶ enrich)
├── ranking.py    # deterministic six-factor scoring model
├── context.py    # ContextAssembler (re-reads source transcripts)
└── explain.py    # rule-based explanation builder
```

The engine depends only on the storage layer's public interface
(`MemoryStore`, `StoredMemory`, `StoredMeeting`, `MemoryQuery`) and the parser
(for context assembly). It adds no new persistence and changes no schema.

## Retrieval pipeline

A single `MemoryRetriever.retrieve(query)` call runs six deterministic stages:

```
RetrievalQuery
   │  1. plan          QueryPlanner turns text + explicit fields into a RetrievalFilter
   ▼
RetrievalFilter
   │  2. select        store.query(...) for structured filters, then in-memory
   │                   keyword (AND), participant, and month filtering
   ▼
candidates
   │  3. rank          score each candidate in [0, 1] (ranking.py)
   │  4. order         relevance / chronological / reverse-chronological
   │  5. paginate      offset + limit
   │  6. enrich        attach a ContextWindow and a RetrievalExplanation
   ▼
RetrievalResult  (query, applied_filter, ranked[], stats)
```

### AND semantics

Every populated filter must be satisfied. Structured filters (type, speaker,
status, meeting, confidence, date range) are pushed down to SQLite via
`MemoryQuery`. Keyword terms, participant filters, and month filters are applied
in Python over the returned rows. Keyword matching requires **all** terms to be
present in the memory's searchable text (its text, speaker, metadata values, and
the owning meeting's title/participants).

### Stable ordering and pagination

Results are ordered by one of three modes:

- **relevance** (default): score descending, then meeting date descending, then
  `created_at` descending, then `memory_id` ascending.
- **chronological**: meeting date ascending, then utterance index, then id.
- **reverse-chronological**: meeting date descending, then `created_at`, then id.

All ordering uses stable, total tiebreakers ending in `memory_id`, so equal
scores never reorder between runs. Pagination is a simple `offset`/`limit` slice
applied after ordering; `RetrievalStats` reports the total candidate count so
callers can page predictably.

## Query planner

`QueryPlanner.plan(query, vocabulary)` converts a `RetrievalQuery` into an
executable `RetrievalFilter`. Free text is lowercased, tokenised, and classified
against fixed lexicons:

| Token kind        | Examples                                  | Becomes              |
| ----------------- | ----------------------------------------- | -------------------- |
| memory type       | `decision`, `risks`, `assumption`         | `memory_types`       |
| open-loop bigram  | `open loop`, `open loops`                 | `memory_types`       |
| lifecycle status  | `active`, `resolved`, `archived`          | `statuses`           |
| month name        | `january`/`jan` ... `december`/`dec`      | `months`             |
| known speaker     | a name in `vocabulary.speakers`           | `speakers`           |
| known participant | a name in `vocabulary.participants`       | `participants`       |
| stopword          | `show`, `every`, `about`, `the`, ...      | dropped              |
| anything else     | `postgres`, `project`, `x`                | keyword `terms`      |

So `"alice decisions"` plans to `speaker=Alice, type=decision`, and
`"risks march"` plans to `type=risk, month=3`. The engine builds the planner's
vocabulary from the store (distinct memory speakers and meeting participants), so
name resolution reflects the actual data and stays deterministic. Explicit query
fields are merged with whatever the text contributes.

The original query text is kept as the `phrase`; when two or more keyword terms
remain, their join is the `phrase_core` used for the exact-phrase ranking bonus.

## Ranking strategy

Scoring is a fixed weighted sum of six bounded components, each in `[0, 1]`:

| Component    | Weight | Definition                                                    |
| ------------ | ------ | ------------------------------------------------------------- |
| `text`       | 0.30   | fraction of query terms found in the memory body (1.0 if none)|
| `phrase`     | 0.15   | 1.0 if the multi-term `phrase_core` appears verbatim          |
| `confidence` | 0.20   | the memory's stored extraction confidence                     |
| `recency`    | 0.15   | rank of the meeting date among the candidate dates            |
| `status`     | 0.10   | `active=1.0`, `resolved=0.7`, `archived=0.5`, `superseded=0.3`, `deleted=0.1` |
| `meeting`    | 0.10   | fraction of query terms found in the meeting title/participants|

The weighted sum is clamped to `[0, 1]`. Weights are exposed as `RankingWeights`
and can be overridden per retriever, but the defaults sum to 1.0. Because every
component is a pure function of the data, scores are fully reproducible.

`recency` is computed per query: the distinct candidate meeting dates are sorted
and each is mapped to its position in `[0, 1]` (oldest 0.0, newest 1.0). With one
or zero distinct dates, recency is neutral (1.0) so it does not distort ranking;
undated meetings score 0.0.

## Context assembly

`ContextAssembler` re-parses the owning meeting's source transcript and returns a
`ContextWindow` of `size` utterances before and after the memory's source
utterance, with the matching utterance flagged. Parsing is deterministic and
cached per meeting, so multiple memories from one meeting reparse it once. If the
source path is missing or unreadable, the window degrades gracefully to just the
memory's own text — retrieval still succeeds.

## Explanations

`explain_match` builds an ordered list of concrete `ExplanationReason`s for each
result, each carrying the weighted score contribution from the matching factor:
matched speaker, memory type, keywords, exact phrase, confidence threshold,
status, date range, month, meeting, and participant. If nothing else applies, a
single confidence reason is emitted. Explanations are derived purely from the
filter and the stored data — there is no natural-language generation.

## CLI

| Command    | Purpose                                                       |
| ---------- | ------------------------------------------------------------ |
| `search`   | Rank memories by relevance to a query                        |
| `timeline` | List matches in chronological order                          |
| `explain`  | Show a memory's attributes, reasons, and surrounding context |

Shared options: `--db`, `--json`, `--limit`, `--offset`, `--context`, `--before`,
`--after`, `--between START END`, `--meeting`, `--speaker`, `--status`, `--type`,
and `--min-confidence`. Human output prints a ranked line plus checkmark reasons;
`--json` emits the full `RetrievalResult.to_dict()` payload.

## Future semantic-search extension

The lexical engine is a deliberate, auditable baseline. A future semantic layer
can slot in without disturbing the existing contracts:

- **Embeddings / vector index.** A new candidate-selection strategy could augment
  the keyword AND-filter with nearest-neighbour recall, feeding the *same*
  `RankedMemory` pipeline. The ranking model can incorporate a similarity
  component alongside the existing six factors.
- **Synonym / alias expansion.** The planner could expand keyword terms using a
  controlled vocabulary before matching, improving recall while staying
  deterministic.
- **Learned ranking.** `RankingWeights` already isolates the scoring policy, so a
  tuned or learned weighting could replace the defaults behind the same interface.

Each extension reuses the current models, planner, engine ordering, context
assembly, and explanation machinery; only candidate selection and scoring would
gain an optional semantic path.
