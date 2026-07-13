"""Task 1 tests - domain model + storage layer (SPEC section 8)."""

import json
import sqlite3
import tempfile
from pathlib import Path

import pytest

from harness.domain import (
    Action,
    ContextItem,
    ContextPackage,
    Feedback,
    MemoryEntry,
    SchemaStatus,
    Task,
    TaskRun,
    TaskStatus,
    ReportStatus,
    ToolResult,
)
from harness.storage import HarnessStorage


@pytest.fixture
def storage():
    """Return a HarnessStorage pointed at a fresh temp directory."""
    with tempfile.TemporaryDirectory() as tmp:
        store = HarnessStorage(Path(tmp) / "repo")
        store.init()
        yield store


class TestStorageCreatesTaskRunAndAuditEvent:
    """PLAN Task 1 first failing test."""

    def test_creates_task(self, storage):
        task = Task(title="Add logging", description="Add structured logging",
                    repo_path=str(storage.repo_path))
        storage.create_task(task)

        row = storage.get_task(task.id)
        assert row is not None
        assert row["title"] == "Add logging"
        assert row["status"] == "pending"

    def test_creates_task_run(self, storage):
        task = Task(title="Test", description="...", repo_path=str(storage.repo_path))
        storage.create_task(task)
        run = TaskRun(task_id=task.id, max_repair_rounds=6)
        storage.create_task_run(run)

        row = storage.get_task_run(run.id)
        assert row is not None
        assert row["task_id"] == task.id
        assert row["status"] == "pending"

    def test_task_created_audit_event(self, storage):
        task = Task(title="Audit check", description="...",
                    repo_path=str(storage.repo_path))
        storage.create_task(task)

        # Read JSONL audit log
        audit_path = storage.audit_path
        assert audit_path.exists(), "audit.jsonl should exist after a write"
        lines = audit_path.read_text(encoding="utf-8").strip().splitlines()
        events = [json.loads(line) for line in lines]
        task_events = [e for e in events if e["type"] == "task.created"]
        assert len(task_events) == 1
        assert task_events[0]["task_id"] == task.id

    def test_invalid_action_stored_without_tool_result(self, storage):
        """Invalid actions must be storable with schema_status='invalid'
        and no tool result (SPEC section 8.5, PLAN Task 1)."""
        task = Task(title="X", description="X", repo_path=str(storage.repo_path))
        storage.create_task(task)
        run = TaskRun(task_id=task.id)
        storage.create_task_run(run)

        action = Action(
            task_run_id=run.id,
            round_index=0,
            action_type="unknown_action",
            args_json='{"foo": 1}',
            schema_status=SchemaStatus.INVALID.value,
        )
        storage.create_action(action)

        row = storage.get_action(action.id)
        assert row is not None
        assert row["schema_status"] == "invalid"

        # No tool result should exist for this invalid action
        # (tool results are only created for executed actions)


def test_report_statuses_match_spec():
    """Reports expose the success/failure statuses required by SPEC 5.11."""
    assert {status.value for status in ReportStatus} == {"success", "failure"}


class TestMemoryStorage:
    """Memory entry persistence tests (SPEC section 5.10, section 8.9)."""

    def test_create_and_list_memory(self, storage):
        entry = MemoryEntry(
            repo_path=str(storage.repo_path),
            kind="historical_decision",
            content="Use SQLite for structured state",
            confidence=0.9,
        )
        storage.create_memory_entry(entry)

        entries = storage.list_memory_entries(repo_path=str(storage.repo_path))
        assert len(entries) == 1
        assert entries[0]["content"] == "Use SQLite for structured state"

    def test_supersession_preserves_old(self, storage):
        """PLAN Task 4 test - but exercising storage layer."""
        old = MemoryEntry(
            repo_path=str(storage.repo_path),
            kind="historical_decision",
            content="v1 decision",
        )
        new = MemoryEntry(
            repo_path=str(storage.repo_path),
            kind="historical_decision",
            content="v2 decision",
        )
        storage.create_memory_entry(old)
        storage.create_memory_entry(new)
        storage.supersede_memory(old.id, new.id)

        # Active list excludes superseded
        active = storage.list_memory_entries(repo_path=str(storage.repo_path))
        assert len(active) == 1
        assert active[0]["id"] == new.id

        # Old entry still exists with superseded_by set
        old_row = storage.get_memory_entry(old.id)
        assert old_row is not None
        assert old_row["superseded_by"] == new.id


class TestFeedbackStorage:
    """Feedback persistence tests (SPEC section 8.7)."""

    def test_create_and_list_feedback(self, storage):
        task = Task(title="T", description="D", repo_path=str(storage.repo_path))
        storage.create_task(task)
        run = TaskRun(task_id=task.id)
        storage.create_task_run(run)

        fb = Feedback(
            task_run_id=run.id,
            round_index=0,
            source="schema_validation",
            category="invalid_action",
            summary="Unknown action type 'delete_file'",
            locations=["action.json"],
            raw_excerpt='{"action": "delete_file"}',
        )
        storage.create_feedback(fb)

        items = storage.list_feedback_for_run(run.id)
        assert len(items) == 1
        assert items[0]["source"] == "schema_validation"
        assert items[0]["category"] == "invalid_action"


class TestToolResultStorage:
    def test_rejects_unknown_status(self, storage):
        task = Task(title="T", description="D", repo_path=str(storage.repo_path))
        storage.create_task(task)
        run = TaskRun(task_id=task.id)
        storage.create_task_run(run)
        action = Action(
            task_run_id=run.id,
            round_index=0,
            action_type="run_command",
            args_json='{"command": "pytest"}',
            schema_status=SchemaStatus.VALID.value,
        )
        storage.create_action(action)

        result = ToolResult(action_id=action.id, status="interrupted")

        with pytest.raises(ValueError, match="Unknown tool result status"):
            storage.create_tool_result(result)

    def test_rejects_result_for_invalid_action(self, storage):
        task = Task(title="T", description="D", repo_path=str(storage.repo_path))
        storage.create_task(task)
        run = TaskRun(task_id=task.id)
        storage.create_task_run(run)
        action = Action(task_run_id=run.id, action_type="unknown_action",
                        schema_status=SchemaStatus.INVALID.value)
        storage.create_action(action)

        result = ToolResult(action_id=action.id)
        with pytest.raises(ValueError, match="invalid action"):
            storage.create_tool_result(result)

        assert storage.get_tool_result("missing") is None
        assert storage.get_tool_result(result.id) is None


def test_storage_creates_task_run_and_audit_event():
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        storage = HarnessStorage(repo)
        storage.init()
        task = Task(title="Required test", repo_path=str(repo))
        run = TaskRun(task_id=task.id)

        storage.create_task(task)
        storage.create_task_run(run)
        storage.write_audit({"type": "task.created", "task_id": task.id,
                             "timestamp": "2026-01-01T00:00:00+00:00"})

        assert storage.get_task(task.id)["id"] == task.id
        assert storage.get_task_run(run.id)["task_id"] == task.id
        events = [json.loads(line) for line in storage.audit_path.read_text().splitlines()]
        assert any(event["type"] == "task.created" and event["task_id"] == task.id
                   for event in events)


def test_context_package_items_preserve_input_order(storage):
    task = Task(title="T", repo_path=str(storage.repo_path))
    storage.create_task(task)
    run = TaskRun(task_id=task.id)
    storage.create_task_run(run)
    first = ContextItem(repo_path=str(storage.repo_path), kind="code_structure")
    second = ContextItem(repo_path=str(storage.repo_path), kind="project_convention")
    storage.create_context_item(first)
    storage.create_context_item(second)
    package = ContextPackage(task_run_id=run.id, items=[second.id, first.id])

    storage.create_context_package(package)

    assert storage.get_package_items(package.id) == [second.id, first.id]


def test_storage_redacts_credential_like_values_before_persistence(storage):
    task = Task(title="T", repo_path=str(storage.repo_path))
    storage.create_task(task)
    run = TaskRun(task_id=task.id)
    storage.create_task_run(run)
    action = Action(task_run_id=run.id, args_json='{"api_key": "secret-value"}')
    storage.create_action(action)
    result = ToolResult(action_id=action.id, stdout_excerpt="password=top-secret")
    storage.create_tool_result(result)
    storage.write_audit({"type": "credentials", "payload": {
        "token": "audit-secret", "nested": ["Bearer audit-token"]
    }})

    action_row = storage.get_action(action.id)
    result_row = storage.get_tool_result(result.id)
    audit_text = storage.audit_path.read_text()
    assert "secret-value" not in action_row["args_json"]
    assert "top-secret" not in result_row["stdout_excerpt"]
    assert "audit-secret" not in audit_text
    assert "audit-token" not in audit_text
    assert "[REDACTED]" in action_row["args_json"]


def test_storage_redacts_credential_like_values_in_updates(storage):
    task = Task(title="T", repo_path=str(storage.repo_path))
    storage.create_task(task)
    run = TaskRun(task_id=task.id)
    storage.create_task_run(run)

    storage.update_task_run(run.id, stop_reason="password=top-secret")

    row = storage.get_task_run(run.id)
    assert row["stop_reason"] == "password=[REDACTED]"


def test_storage_backfills_context_package_item_ordinals_for_legacy_rows():
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        harness_dir = repo / ".harness"
        harness_dir.mkdir(parents=True)
        db_path = harness_dir / "harness.db"
        conn = sqlite3.connect(db_path)
        conn.execute(
            "CREATE TABLE context_package_item ("
            "package_id TEXT NOT NULL, item_id TEXT NOT NULL, "
            "PRIMARY KEY (package_id, item_id))"
        )
        conn.executemany(
            "INSERT INTO context_package_item (package_id, item_id) VALUES (?, ?)",
            [("package-1", "item-2"), ("package-1", "item-1")],
        )
        conn.commit()
        conn.close()

        HarnessStorage(repo).init()

        conn = sqlite3.connect(db_path)
        rows = conn.execute(
            "SELECT item_id, ordinal FROM context_package_item "
            "WHERE package_id=? ORDER BY ordinal",
            ("package-1",),
        ).fetchall()
        conn.close()

        assert rows == [("item-2", 0), ("item-1", 1)]
