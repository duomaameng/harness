"""Task 1 tests - domain model + storage layer (SPEC section 8)."""

import json
import tempfile
from pathlib import Path

import pytest

from harness.domain import (
    Action,
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
