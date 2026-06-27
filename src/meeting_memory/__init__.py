"""Meeting Memory System.

Phase 1 provides the ingestion and parsing foundation: it converts raw meeting
transcripts (plain text or JSON) into a clean, typed internal representation.

This phase intentionally performs **no** AI extraction (no decisions, tasks, or
summaries). Its sole responsibility is parsing and normalizing meeting data.
"""

from __future__ import annotations

__version__ = "0.5.0"

__all__ = ["__version__"]
