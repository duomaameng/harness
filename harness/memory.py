"""Long-term repository decision memory."""

from __future__ import annotations

from collections.abc import Iterable

from harness.domain import MemoryEntry
from harness.storage import HarnessStorage


class MemoryStore:
    """Record and retrieve append-only repository memory."""

    def __init__(self, storage: HarnessStorage) -> None:
        self.storage = storage

    def record(
        self,
        *,
        repo_path: str,
        kind: str,
        content: str,
        source_task_id: str | None = None,
        confidence: float = 0.5,
        supersedes_id: str | None = None,
    ) -> MemoryEntry:
        if supersedes_id is not None:
            previous = self.storage.get_memory_entry(supersedes_id)
            if previous is None:
                raise ValueError(f"Unknown memory entry: {supersedes_id}")
            if previous["superseded_by"] is not None:
                raise ValueError(f"Memory entry is already superseded: {supersedes_id}")
            if previous["repo_path"] != repo_path or previous["kind"] != kind:
                raise ValueError("Superseded memory must match repository and kind")

        entry = MemoryEntry(
            repo_path=repo_path,
            kind=kind,
            content=content,
            source_task_id=source_task_id,
            confidence=confidence,
        )
        self.storage.create_memory_entry(entry)
        if supersedes_id is not None:
            self.storage.supersede_memory_entry(supersedes_id, entry.id)
        return entry

    def query(
        self,
        *,
        repo_path: str,
        kind: str | None = None,
        keywords: Iterable[str] | None = None,
        include_superseded: bool = False,
    ) -> list[MemoryEntry]:
        rows = self.storage.list_memory_entries(
            repo_path=repo_path,
            kind=kind,
            keywords=list(keywords or []),
            include_superseded=include_superseded,
        )
        return [MemoryEntry(**row) for row in rows]

    search = query
