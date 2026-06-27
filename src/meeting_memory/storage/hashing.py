"""Deterministic hashing helpers for duplicate detection.

Hashes are plain SHA-256 hex digests over normalized text, so they are stable
across processes and runs. No randomness or salting is involved.
"""

from __future__ import annotations

import hashlib

from ..extraction.dedup import normalize_text


def transcript_hash(text: str) -> str:
    """Return a stable hash of a raw transcript, used to detect re-imports."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def memory_content_hash(memory_type: str, text: str) -> str:
    """Return a stable content hash for a memory.

    The hash combines the memory type with the normalized text, so the same
    statement recorded as the same type collides regardless of punctuation,
    casing, or surrounding whitespace. Speaker and meeting are intentionally
    excluded so a recurring point can be detected across meetings.
    """
    key = f"{memory_type}\n{normalize_text(text)}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()
