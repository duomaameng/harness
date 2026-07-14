from pathlib import Path

import pytest

from harness.domain import MemoryEntry
from harness.memory import MemoryStore
from harness.storage import HarnessStorage


def test_memory_supersession_preserves_old_entry(tmp_path: Path):
    storage = HarnessStorage(tmp_path / "repo")
    storage.init()
    memories = MemoryStore(storage)

    original = memories.record(
        repo_path=str(storage.repo_path),
        kind="historical_decision",
        content="Use SQLite for durable harness state.",
        confidence=0.8,
    )
    newer = memories.record(
        repo_path=str(storage.repo_path),
        kind="historical_decision",
        content="Use SQLite with append-only supersession for durable harness state.",
        confidence=0.95,
        supersedes_id=original.id,
    )

    old_row = storage.get_memory_entry(original.id)
    assert old_row is not None
    assert old_row["content"] == "Use SQLite for durable harness state."
    assert old_row["superseded_by"] == newer.id


def test_memory_rejects_unknown_kind_before_storage(tmp_path: Path):
    storage = HarnessStorage(tmp_path / "repo")
    storage.init()
    memories = MemoryStore(storage)

    with pytest.raises(ValueError, match="Unknown memory kind"):
        memories.record(
            repo_path=str(storage.repo_path),
            kind="not_a_memory_kind",
            content="This should not be stored.",
        )

    assert storage.list_memory_entries(repo_path=str(storage.repo_path)) == []


def test_memory_query_filters_by_repo_kind_keyword_and_active_entries(tmp_path: Path):
    storage = HarnessStorage(tmp_path / "repo")
    storage.init()
    memories = MemoryStore(storage)
    repo = str(storage.repo_path)
    other_repo = str(tmp_path / "other")

    old = memories.record(
        repo_path=repo,
        kind="historical_decision",
        content="Use SQLite for durable state.",
    )
    newer = memories.record(
        repo_path=repo,
        kind="historical_decision",
        content="Use SQLite with supersession for durable state.",
        supersedes_id=old.id,
    )
    memories.record(
        repo_path=repo,
        kind="project_convention",
        content="Use pytest for validation.",
    )
    memories.record(
        repo_path=other_repo,
        kind="historical_decision",
        content="Use SQLite for another repository.",
    )

    results = memories.query(
        repo_path=repo,
        kind="historical_decision",
        keywords=["sqlite", "durable"],
    )

    assert [entry.id for entry in results] == [newer.id]

    all_results = memories.query(
        repo_path=repo,
        kind="historical_decision",
        keywords=["sqlite", "durable"],
        include_superseded=True,
    )

    assert [entry.id for entry in all_results] == [old.id, newer.id]


def test_storage_exposes_only_transactional_memory_supersession(tmp_path: Path):
    storage = HarnessStorage(tmp_path / "repo")
    storage.init()

    assert not hasattr(storage, "supersede_memory_entry")


def test_storage_rejects_mismatched_memory_supersession(tmp_path: Path):
    storage = HarnessStorage(tmp_path / "repo")
    storage.init()
    original = storage.create_memory_entry(
        MemoryEntry(
            repo_path="repo-a",
            kind="historical_decision",
            content="Use SQLite.",
        )
    )
    newer = MemoryEntry(
        repo_path="repo-b",
        kind="project_convention",
        content="Use pytest.",
    )

    with pytest.raises(ValueError, match="Unknown active memory entry"):
        storage.create_memory_entry_superseding(newer, original.id)

    assert storage.get_memory_entry(original.id)["superseded_by"] is None
    assert storage.get_memory_entry(newer.id) is None


def test_transactional_supersession_creates_active_new_memory(tmp_path: Path):
    storage = HarnessStorage(tmp_path / "repo")
    storage.init()
    original = storage.create_memory_entry(
        MemoryEntry(
            repo_path="repo",
            kind="historical_decision",
            content="Use SQLite.",
        )
    )
    newer = MemoryEntry(
        repo_path="repo",
        kind="historical_decision",
        content="Use SQLite with supersession.",
        superseded_by="stale-entry",
    )

    storage.create_memory_entry_superseding(newer, original.id)

    assert storage.get_memory_entry(newer.id)["superseded_by"] is None


def test_memory_store_does_not_expose_unplanned_search_alias(tmp_path: Path):
    storage = HarnessStorage(tmp_path / "repo")
    storage.init()

    assert not hasattr(MemoryStore(storage), "search")
