from pathlib import Path

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

