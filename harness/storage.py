"""SQLite persistence and JSONL audit store (SPEC section 7, section 8.10).

All structured state lives in a single SQLite database under `.harness/`.
Append-only audit events are written as one JSON object per line.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
from pathlib import Path
from typing import Any

from harness.domain import (
    Action,
    ApprovalRequest,
    ContextItem,
    ContextPackage,
    Feedback,
    MemoryEntry,
    Task,
    TaskRun,
    ToolResult,
    ToolResultStatus,
    make_audit_event,
)

# -- SQLite DDL -----------------------------------------------------

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS task (
    id              TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    description     TEXT NOT NULL DEFAULT '',
    repo_path       TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS task_run (
    id                  TEXT PRIMARY KEY,
    task_id             TEXT NOT NULL REFERENCES task(id),
    status              TEXT NOT NULL DEFAULT 'pending',
    max_repair_rounds   INTEGER NOT NULL DEFAULT 6,
    current_round       INTEGER NOT NULL DEFAULT 0,
    stop_reason         TEXT,
    started_at          TEXT NOT NULL,
    finished_at         TEXT
);

CREATE TABLE IF NOT EXISTS context_item (
    id          TEXT PRIMARY KEY,
    repo_path   TEXT NOT NULL,
    kind        TEXT NOT NULL,
    source_path TEXT,
    symbol      TEXT,
    summary     TEXT NOT NULL DEFAULT '',
    content_ref TEXT,
    metadata    TEXT,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS context_package (
    id               TEXT PRIMARY KEY,
    task_run_id      TEXT NOT NULL REFERENCES task_run(id),
    round_index      INTEGER NOT NULL DEFAULT 0,
    token_estimate   INTEGER NOT NULL DEFAULT 0,
    selection_reason TEXT NOT NULL DEFAULT '',
    created_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS context_package_item (
    package_id  TEXT NOT NULL REFERENCES context_package(id),
    item_id     TEXT NOT NULL REFERENCES context_item(id),
    ordinal     INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (package_id, item_id)
);

CREATE TABLE IF NOT EXISTS action (
    id               TEXT PRIMARY KEY,
    task_run_id      TEXT NOT NULL REFERENCES task_run(id),
    round_index      INTEGER NOT NULL DEFAULT 0,
    action_type      TEXT NOT NULL,
    args_json        TEXT NOT NULL DEFAULT '{}',
    schema_status    TEXT NOT NULL DEFAULT 'valid',
    guardrail_status TEXT,
    created_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tool_result (
    id              TEXT PRIMARY KEY,
    action_id       TEXT NOT NULL REFERENCES action(id),
    status          TEXT NOT NULL DEFAULT 'success',
    stdout_excerpt  TEXT,
    stderr_excerpt  TEXT,
    exit_code       INTEGER,
    changed_files   TEXT,
    duration_ms     INTEGER,
    metadata        TEXT,
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS feedback (
    id          TEXT PRIMARY KEY,
    task_run_id TEXT NOT NULL REFERENCES task_run(id),
    round_index INTEGER NOT NULL DEFAULT 0,
    source      TEXT NOT NULL,
    category    TEXT NOT NULL,
    summary     TEXT NOT NULL DEFAULT '',
    locations   TEXT,
    raw_excerpt TEXT,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS approval_request (
    id          TEXT PRIMARY KEY,
    task_run_id TEXT NOT NULL REFERENCES task_run(id),
    action_id   TEXT NOT NULL REFERENCES action(id),
    risk_level  TEXT NOT NULL DEFAULT '',
    reason      TEXT NOT NULL DEFAULT '',
    status      TEXT NOT NULL DEFAULT 'pending',
    decided_by  TEXT,
    decided_at  TEXT
);

CREATE TABLE IF NOT EXISTS memory_entry (
    id             TEXT PRIMARY KEY,
    repo_path      TEXT NOT NULL,
    kind           TEXT NOT NULL,
    content        TEXT NOT NULL DEFAULT '',
    source_task_id TEXT,
    confidence     REAL NOT NULL DEFAULT 0.5,
    created_at     TEXT NOT NULL,
    superseded_by  TEXT
);
"""


# -- JSONL helpers ---------------------------------------------------


def _append_jsonl(path: Path, event: dict[str, Any]) -> None:
    """Append one JSON object as a single line."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False) + "\n")


_SENSITIVE_KEY_NAMES = {
    "api_key",
    "access_token",
    "auth_token",
    "password",
    "passwd",
    "secret",
    "credential",
    "credentials",
    "private_key",
    "token",
}
_SENSITIVE_ASSIGNMENT = re.compile(
    r"(\b[A-Za-z0-9_-]*(?:api[_-]?key|access[_-]?token|auth[_-]?token|"
    r"password|passwd|secret|credential|private[_-]?key|token)\s*[:=]\s*)"
    r"([^\s,;}]+)",
    re.IGNORECASE,
)
_BEARER = re.compile(r"\bBearer\s+[^\s,;}]+", re.IGNORECASE)
_SECRET_VALUE = re.compile(r"\bsk-[A-Za-z0-9_-]+\b")


def _redact(value: Any, key: str | None = None) -> Any:
    """Redact credential-like values recursively before persistence."""
    if key and _is_sensitive_key(key):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {k: _redact(v, str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact(item) for item in value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, (dict, list)):
            return json.dumps(_redact(parsed), ensure_ascii=False)
        redacted = _SENSITIVE_ASSIGNMENT.sub(r"\1[REDACTED]", value)
        redacted = _BEARER.sub("Bearer [REDACTED]", redacted)
        return _SECRET_VALUE.sub("[REDACTED]", redacted)
    return value


def _is_sensitive_key(key: str) -> bool:
    snake_key = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", key)
    normalized = re.sub(r"[^a-z0-9]+", "_", snake_key.lower()).strip("_")
    return (
        normalized in _SENSITIVE_KEY_NAMES
        or normalized.endswith("_secret")
        or normalized.endswith("_token")
        or normalized.endswith("_api_key")
        or normalized.endswith("_private_key")
    )


def _redact_json_text(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return _redact(value)
    return json.dumps(_redact(parsed), ensure_ascii=False)


def _backfill_context_package_item_ordinals(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        "SELECT rowid, package_id, ordinal "
        "FROM context_package_item ORDER BY package_id, rowid"
    ).fetchall()
    by_package: dict[str, list[sqlite3.Row]] = {}
    for row in rows:
        by_package.setdefault(row["package_id"], []).append(row)

    for package_rows in by_package.values():
        ordinals = [row["ordinal"] for row in package_rows]
        if len(ordinals) == len(set(ordinals)):
            continue

        used: set[int] = set()
        for row in package_rows:
            ordinal = row["ordinal"]
            if ordinal not in used:
                used.add(ordinal)
                continue
            next_ordinal = ordinal + 1
            while next_ordinal in used:
                next_ordinal += 1
            conn.execute(
                "UPDATE context_package_item SET ordinal=? WHERE rowid=?",
                (next_ordinal, row["rowid"]),
            )
            used.add(next_ordinal)


# -- Storage --------------------------------------------------------


class HarnessStorage:
    """Manages SQLite persistence and JSONL audit log inside `.harness/`.

    SPEC section 7: "storage and audit layer: SQLite, JSONL Audit Store"
    """

    def __init__(self, repo_path: str | Path) -> None:
        self.repo_path = Path(repo_path).resolve()
        self.harness_dir = self.repo_path / ".harness"
        self.db_path = self.harness_dir / "harness.db"
        self.audit_path = self.harness_dir / "audit.jsonl"

    # -- init / close -------------------------------------------------

    def init(self) -> None:
        """Create `.harness/` directory and initialise the SQLite schema."""
        self.harness_dir.mkdir(parents=True, exist_ok=True)
        conn = self._connect()
        try:
            conn.executescript(SCHEMA_SQL)
            columns = {
                row[1] for row in conn.execute("PRAGMA table_info(context_package_item)")
            }
            if "ordinal" not in columns:
                conn.execute(
                    "ALTER TABLE context_package_item "
                    "ADD COLUMN ordinal INTEGER NOT NULL DEFAULT 0"
                )
            tool_columns = {
                row[1] for row in conn.execute("PRAGMA table_info(tool_result)")
            }
            if "metadata" not in tool_columns:
                conn.execute("ALTER TABLE tool_result ADD COLUMN metadata TEXT")
            _backfill_context_package_item_ordinals(conn)
            conn.commit()
        finally:
            conn.close()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        return conn

    # -- helpers ------------------------------------------------------

    def _insert(self, table: str, obj: Any, exclude: set[str] | None = None) -> None:
        """Insert a dataclass instance into *table*.  Fields in *exclude* are skipped."""
        exclude = exclude or set()
        data = {k: _redact(v, k) for k, v in vars(obj).items() if k not in exclude}
        columns = ", ".join(data.keys())
        placeholders = ", ".join("?" for _ in data)
        sql = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
        conn = self._connect()
        try:
            conn.execute(sql, list(data.values()))
            conn.commit()
        finally:
            conn.close()

    def _update(self, table: str, pk_field: str, pk_value: str, **fields: Any) -> None:
        """Update columns on a single row identified by *pk_field*."""
        if not fields:
            return
        sets = ", ".join(f"{k}=?" for k in fields)
        sql = f"UPDATE {table} SET {sets} WHERE {pk_field}=?"
        conn = self._connect()
        try:
            values = [_redact(value, key) for key, value in fields.items()]
            conn.execute(sql, values + [pk_value])
            conn.commit()
        finally:
            conn.close()

    def _fetchone(self, sql: str, params: tuple = ()) -> dict | None:
        conn = self._connect()
        try:
            row = conn.execute(sql, params).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def _fetchall(self, sql: str, params: tuple = ()) -> list[dict]:
        conn = self._connect()
        try:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    # -- audit -------------------------------------------------------

    def write_audit(self, event: dict[str, Any]) -> None:
        """Append an audit event to the JSONL log (SPEC section 8.10)."""
        _append_jsonl(self.audit_path, _redact(event))

    # -- task --------------------------------------------------------

    def create_task(self, task: Task) -> Task:
        self._insert("task", task)
        self.write_audit(make_audit_event("task.created", task_id=task.id))
        return task

    def get_task(self, task_id: str) -> dict | None:
        return self._fetchone("SELECT * FROM task WHERE id=?", (task_id,))

    # -- task_run ----------------------------------------------------

    def create_task_run(self, run: TaskRun) -> TaskRun:
        self._insert("task_run", run)
        self.write_audit(make_audit_event("run.created", task_run_id=run.id,
                                          task_id=run.task_id))
        return run

    def get_task_run(self, run_id: str) -> dict | None:
        return self._fetchone("SELECT * FROM task_run WHERE id=?", (run_id,))

    def update_task_run(self, run_id: str, **fields: Any) -> None:
        self._update("task_run", "id", run_id, **fields)

    # -- context_item ------------------------------------------------

    def create_context_item(self, item: ContextItem) -> ContextItem:
        meta_json = _redact_json_text(json.dumps(item.metadata)) if item.metadata else None
        conn = self._connect()
        try:
            conn.execute(
                """INSERT INTO context_item (id, repo_path, kind, source_path,
                   symbol, summary, content_ref, metadata, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    item.id,
                    item.repo_path,
                    item.kind,
                    item.source_path,
                    item.symbol,
                    _redact(item.summary),
                    _redact(item.content_ref),
                    meta_json,
                    item.updated_at,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return item

    def get_context_item(self, item_id: str) -> dict | None:
        return self._fetchone("SELECT * FROM context_item WHERE id=?", (item_id,))

    def list_context_items(self, repo_path: str | None = None,
                           kind: str | None = None) -> list[dict]:
        conditions = []
        params: list[Any] = []
        if repo_path is not None:
            conditions.append("repo_path = ?")
            params.append(repo_path)
        if kind is not None:
            conditions.append("kind = ?")
            params.append(kind)
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        return self._fetchall(f"SELECT * FROM context_item {where}", tuple(params))

    # -- context_package ---------------------------------------------

    def create_context_package(self, pkg: ContextPackage) -> ContextPackage:
        conn = self._connect()
        try:
            conn.execute(
                """INSERT INTO context_package (id, task_run_id, round_index,
                   token_estimate, selection_reason, created_at)
                   VALUES (?,?,?,?,?,?)""",
                (pkg.id, pkg.task_run_id, pkg.round_index, pkg.token_estimate,
                 _redact(pkg.selection_reason), pkg.created_at),
            )
            for ordinal, item_id in enumerate(pkg.items):
                conn.execute(
                    "INSERT INTO context_package_item (package_id, item_id, ordinal) VALUES (?,?,?)",
                    (pkg.id, item_id, ordinal),
                )
            conn.commit()
        finally:
            conn.close()
        self.write_audit(make_audit_event(
            "context.selected", package_id=pkg.id, task_run_id=pkg.task_run_id,
            round_index=pkg.round_index, item_count=len(pkg.items),
        ))
        return pkg

    def get_context_package(self, package_id: str) -> dict | None:
        return self._fetchone("SELECT * FROM context_package WHERE id=?", (package_id,))

    def get_package_items(self, package_id: str) -> list[str]:
        rows = self._fetchall(
            "SELECT item_id FROM context_package_item WHERE package_id=? ORDER BY ordinal",
            (package_id,),
        )
        return [r["item_id"] for r in rows]

    # -- action ------------------------------------------------------

    def create_action(self, action: Action) -> Action:
        self._insert("action", action)
        self.write_audit(make_audit_event(
            "action.received", action_id=action.id,
            task_run_id=action.task_run_id, round_index=action.round_index,
            action_type=action.action_type,
        ))
        if action.schema_status == "invalid":
            self.write_audit(make_audit_event(
                "schema.invalid", action_id=action.id,
            ))
        return action

    def get_action(self, action_id: str) -> dict | None:
        return self._fetchone("SELECT * FROM action WHERE id=?", (action_id,))

    def list_actions_for_run(self, task_run_id: str) -> list[dict]:
        return self._fetchall(
            "SELECT * FROM action WHERE task_run_id=? ORDER BY created_at",
            (task_run_id,),
        )

    def update_action_guardrail(self, action_id: str, guardrail_status: str) -> None:
        self._update("action", "id", action_id, guardrail_status=guardrail_status)

    # -- tool_result -------------------------------------------------

    def create_tool_result(self, result: ToolResult) -> ToolResult:
        valid_statuses = {status.value for status in ToolResultStatus}
        if result.status not in valid_statuses:
            raise ValueError(
                f"Unknown tool result status: {result.status}. "
                f"Supported: {', '.join(sorted(valid_statuses))}"
            )
        action = self.get_action(result.action_id)
        if action is not None and action["schema_status"] == "invalid":
            raise ValueError("Cannot create tool result for invalid action")
        conn = self._connect()
        try:
            changed = (
                _redact_json_text(json.dumps(result.changed_files))
                if result.changed_files else None
            )
            metadata = (
                _redact_json_text(json.dumps(result.metadata))
                if result.metadata else None
            )
            conn.execute(
                """INSERT INTO tool_result (id, action_id, status, stdout_excerpt,
                   stderr_excerpt, exit_code, changed_files, duration_ms, metadata, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    result.id,
                    result.action_id,
                    result.status,
                    _redact(result.stdout_excerpt),
                    _redact(result.stderr_excerpt),
                    result.exit_code,
                    changed,
                    result.duration_ms,
                    metadata,
                    result.created_at,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        self.write_audit(make_audit_event(
            "tool.completed", tool_result_id=result.id, action_id=result.action_id,
            status=result.status,
        ))
        return result

    def get_tool_result(self, result_id: str) -> dict | None:
        return self._fetchone("SELECT * FROM tool_result WHERE id=?", (result_id,))

    def list_tool_results_for_run(self, task_run_id: str) -> list[dict]:
        return self._fetchall(
            "SELECT tool_result.* FROM tool_result "
            "JOIN action ON action.id=tool_result.action_id "
            "WHERE action.task_run_id=? ORDER BY tool_result.created_at",
            (task_run_id,),
        )

    # -- feedback ----------------------------------------------------

    def create_feedback(self, fb: Feedback) -> Feedback:
        conn = self._connect()
        try:
            locs = _redact_json_text(json.dumps(fb.locations)) if fb.locations else None
            conn.execute(
                """INSERT INTO feedback (id, task_run_id, round_index, source,
                   category, summary, locations, raw_excerpt, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    fb.id,
                    fb.task_run_id,
                    fb.round_index,
                    fb.source,
                    fb.category,
                    _redact(fb.summary),
                    locs,
                    _redact(fb.raw_excerpt),
                    fb.created_at,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        self.write_audit(make_audit_event(
            "feedback.generated", feedback_id=fb.id,
            task_run_id=fb.task_run_id, source=fb.source, category=fb.category,
        ))
        return fb

    def get_feedback(self, feedback_id: str) -> dict | None:
        return self._fetchone("SELECT * FROM feedback WHERE id=?", (feedback_id,))

    def list_feedback_for_run(self, task_run_id: str) -> list[dict]:
        return self._fetchall(
            "SELECT * FROM feedback WHERE task_run_id=? ORDER BY created_at",
            (task_run_id,),
        )

    # -- approval_request --------------------------------------------

    def create_approval_request(self, ar: ApprovalRequest) -> ApprovalRequest:
        self._insert("approval_request", ar)
        self.write_audit(make_audit_event(
            "approval.requested", approval_id=ar.id, action_id=ar.action_id,
            risk_level=ar.risk_level,
        ))
        return ar

    def get_approval_request(self, approval_id: str) -> dict | None:
        return self._fetchone("SELECT * FROM approval_request WHERE id=?", (approval_id,))

    def update_approval_request(self, approval_id: str, **fields: Any) -> None:
        self._update("approval_request", "id", approval_id, **fields)
        if "status" in fields:
            self.write_audit(make_audit_event(
                "approval.decided", approval_id=approval_id,
                status=fields["status"],
            ))

    # -- memory_entry ------------------------------------------------

    def create_memory_entry(self, entry: MemoryEntry) -> MemoryEntry:
        self._insert("memory_entry", entry)
        return entry

    def create_memory_entry_superseding(
        self, entry: MemoryEntry, supersedes_id: str
    ) -> MemoryEntry:
        conn = self._connect()
        try:
            conn.execute(
                """INSERT INTO memory_entry (id, repo_path, kind, content,
                   source_task_id, confidence, created_at, superseded_by)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (
                    entry.id,
                    entry.repo_path,
                    entry.kind,
                    _redact(entry.content),
                    entry.source_task_id,
                    entry.confidence,
                    entry.created_at,
                    None,
                ),
            )
            cursor = conn.execute(
                "UPDATE memory_entry SET superseded_by=? "
                "WHERE id=? AND repo_path=? AND kind=? AND superseded_by IS NULL",
                (_redact(entry.id), supersedes_id, entry.repo_path, entry.kind),
            )
            if cursor.rowcount != 1:
                raise ValueError(f"Unknown active memory entry: {supersedes_id}")
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return entry

    def get_memory_entry(self, entry_id: str) -> dict | None:
        return self._fetchone("SELECT * FROM memory_entry WHERE id=?", (entry_id,))

    def list_memory_entries(self, repo_path: str | None = None,
                            kind: str | None = None,
                            keywords: list[str] | None = None,
                            include_superseded: bool = True) -> list[dict]:
        conditions = []
        params: list[Any] = []
        if repo_path is not None:
            conditions.append("repo_path = ?")
            params.append(repo_path)
        if kind is not None:
            conditions.append("kind = ?")
            params.append(kind)
        if not include_superseded:
            conditions.append("superseded_by IS NULL")
        for keyword in keywords or []:
            conditions.append("LOWER(content) LIKE ?")
            params.append(f"%{keyword.lower()}%")
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        return self._fetchall(
            f"SELECT * FROM memory_entry {where} ORDER BY created_at, id",
            tuple(params),
        )
