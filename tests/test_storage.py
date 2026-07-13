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
    SchemaStatus,
    Task,
    TaskRun,
    TaskStatus,
    ReportStatus,
    ToolResult,
)
from harness.storage import HarnessStorage
from harness.storage import _redact


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


def test_storage_redacts_bare_secret_values_and_content_refs(storage):
    task = Task(title="T", repo_path=str(storage.repo_path))
    storage.create_task(task)
    run = TaskRun(task_id=task.id)
    storage.create_task_run(run)
    action = Action(task_run_id=run.id, args_json='{"note": "sk-test-secret"}')
    storage.create_action(action)
    item = ContextItem(
        repo_path=str(storage.repo_path),
        kind="code_structure",
        content_ref="sk-test-content-ref",
    )
    storage.create_context_item(item)

    action_row = storage.get_action(action.id)
    item_row = storage.get_context_item(item.id)
    assert "sk-test-secret" not in action_row["args_json"]
    assert "sk-test-content-ref" not in item_row["content_ref"]
    assert "[REDACTED]" in action_row["args_json"]
    assert item_row["content_ref"] == "[REDACTED]"


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


def test_storage_backfills_ordinals_for_intermediate_zeroed_migration():
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        harness_dir = repo / ".harness"
        harness_dir.mkdir(parents=True)
        db_path = harness_dir / "harness.db"
        conn = sqlite3.connect(db_path)
        conn.execute(
            "CREATE TABLE context_package_item ("
            "package_id TEXT NOT NULL, item_id TEXT NOT NULL, "
            "ordinal INTEGER NOT NULL DEFAULT 0, "
            "PRIMARY KEY (package_id, item_id))"
        )
        conn.executemany(
            "INSERT INTO context_package_item (package_id, item_id, ordinal) "
            "VALUES (?, ?, ?)",
            [("package-1", "item-2", 0), ("package-1", "item-1", 0)],
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


def test_storage_does_not_redact_token_estimate_column(storage):
    assert _redact(123, "token_estimate") == 123


def test_storage_redacts_common_secret_suffix_keys():
    payload = {
        "client_secret": "secret-value",
        "refresh_token": "token-value",
        "apiKey": "api-key-value",
        "clientSecret": "client-secret-value",
        "refreshToken": "refresh-token-value",
    }

    redacted = _redact(payload)

    assert redacted == {
        "client_secret": "[REDACTED]",
        "refresh_token": "[REDACTED]",
        "apiKey": "[REDACTED]",
        "clientSecret": "[REDACTED]",
        "refreshToken": "[REDACTED]",
    }


def test_storage_redacts_context_package_selection_reason(storage):
    task = Task(title="T", repo_path=str(storage.repo_path))
    storage.create_task(task)
    run = TaskRun(task_id=task.id)
    storage.create_task_run(run)
    package = ContextPackage(
        task_run_id=run.id,
        selection_reason="included because password=top-secret",
    )

    storage.create_context_package(package)

    row = storage.get_context_package(package.id)
    assert row["selection_reason"] == "included because password=[REDACTED]"


def test_storage_redacts_env_style_secret_names_in_free_text():
    value = (
        "client_secret=client-value "
        "refresh_token=refresh-value "
        "OPENAI_API_KEY=sk-test-secret"
    )

    redacted = _redact(value)

    assert "client-value" not in redacted
    assert "refresh-value" not in redacted
    assert "sk-test-secret" not in redacted
    assert redacted == (
        "client_secret=[REDACTED] "
        "refresh_token=[REDACTED] "
        "OPENAI_API_KEY=[REDACTED]"
    )


def test_storage_preserves_valid_nonzero_ordinals_during_migration():
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        harness_dir = repo / ".harness"
        harness_dir.mkdir(parents=True)
        db_path = harness_dir / "harness.db"
        conn = sqlite3.connect(db_path)
        conn.execute(
            "CREATE TABLE context_package_item ("
            "package_id TEXT NOT NULL, item_id TEXT NOT NULL, "
            "ordinal INTEGER NOT NULL DEFAULT 0, "
            "PRIMARY KEY (package_id, item_id))"
        )
        conn.executemany(
            "INSERT INTO context_package_item (package_id, item_id, ordinal) "
            "VALUES (?, ?, ?)",
            [
                ("package-1", "item-2", 0),
                ("package-1", "item-1", 1),
                ("package-2", "item-b", 0),
                ("package-2", "item-a", 0),
            ],
        )
        conn.commit()
        conn.close()

        HarnessStorage(repo).init()

        conn = sqlite3.connect(db_path)
        package_1 = conn.execute(
            "SELECT item_id, ordinal FROM context_package_item "
            "WHERE package_id=? ORDER BY ordinal",
            ("package-1",),
        ).fetchall()
        package_2 = conn.execute(
            "SELECT item_id, ordinal FROM context_package_item "
            "WHERE package_id=? ORDER BY ordinal",
            ("package-2",),
        ).fetchall()
        conn.close()

        assert package_1 == [("item-2", 0), ("item-1", 1)]
        assert package_2 == [("item-b", 0), ("item-a", 1)]


def test_storage_backfills_duplicate_zero_ordinals_without_rewriting_valid_ordinals():
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        harness_dir = repo / ".harness"
        harness_dir.mkdir(parents=True)
        db_path = harness_dir / "harness.db"
        conn = sqlite3.connect(db_path)
        conn.execute(
            "CREATE TABLE context_package_item ("
            "package_id TEXT NOT NULL, item_id TEXT NOT NULL, "
            "ordinal INTEGER NOT NULL DEFAULT 0, "
            "PRIMARY KEY (package_id, item_id))"
        )
        conn.executemany(
            "INSERT INTO context_package_item (package_id, item_id, ordinal) "
            "VALUES (?, ?, ?)",
            [
                ("package-1", "item-zero-a", 0),
                ("package-1", "item-existing", 5),
                ("package-1", "item-zero-b", 0),
            ],
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

        assert rows == [
            ("item-zero-a", 0),
            ("item-zero-b", 1),
            ("item-existing", 5),
        ]


def test_storage_backfills_duplicate_nonzero_ordinals_without_reordering():
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        harness_dir = repo / ".harness"
        harness_dir.mkdir(parents=True)
        db_path = harness_dir / "harness.db"
        conn = sqlite3.connect(db_path)
        conn.execute(
            "CREATE TABLE context_package_item ("
            "package_id TEXT NOT NULL, item_id TEXT NOT NULL, "
            "ordinal INTEGER NOT NULL DEFAULT 0, "
            "PRIMARY KEY (package_id, item_id))"
        )
        conn.executemany(
            "INSERT INTO context_package_item (package_id, item_id, ordinal) "
            "VALUES (?, ?, ?)",
            [
                ("package-1", "item-first", 5),
                ("package-1", "item-second", 5),
            ],
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

        assert rows == [("item-first", 5), ("item-second", 6)]


def test_storage_backfills_chained_duplicate_ordinals_in_row_order():
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        harness_dir = repo / ".harness"
        harness_dir.mkdir(parents=True)
        db_path = harness_dir / "harness.db"
        conn = sqlite3.connect(db_path)
        conn.execute(
            "CREATE TABLE context_package_item ("
            "package_id TEXT NOT NULL, item_id TEXT NOT NULL, "
            "ordinal INTEGER NOT NULL DEFAULT 0, "
            "PRIMARY KEY (package_id, item_id))"
        )
        conn.executemany(
            "INSERT INTO context_package_item (package_id, item_id, ordinal) "
            "VALUES (?, ?, ?)",
            [
                ("package-1", "item-0", 0),
                ("package-1", "item-1a", 1),
                ("package-1", "item-1b", 1),
                ("package-1", "item-2", 2),
            ],
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

        assert rows == [
            ("item-0", 0),
            ("item-1a", 1),
            ("item-1b", 2),
            ("item-2", 3),
        ]
