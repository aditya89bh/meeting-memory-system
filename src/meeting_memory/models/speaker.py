"""Speaker model representing a meeting participant."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Speaker:
    """A meeting participant.

    Equality and hashing are based on :attr:`name`, which is treated as the
    canonical identity of a participant. :attr:`aliases` records any alternative
    labels seen in the source transcript without affecting identity.
    """

    name: str
    aliases: frozenset[str] = field(default=frozenset(), compare=False)

    @property
    def is_named(self) -> bool:
        """Whether the speaker has a non-empty name."""
        return bool(self.name.strip())

    def to_dict(self) -> dict[str, object]:
        """Serialise the speaker into JSON-compatible primitives."""
        return {"name": self.name, "aliases": sorted(self.aliases)}

    def __str__(self) -> str:
        return self.name
