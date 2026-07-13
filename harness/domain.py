"""Domain model dataclasses and enums for the harness.

All types follow SPEC.md Section 8 (Data Model) and Section 5 (Functional Spec).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

# -- Enums ----------------------------------------------------------


class TaskStatus(str, Enum):
    """SPEC section 8.2 - TaskRun statuses."""
    PENDING = "pending"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    STOPPED = "stopped"


class SchemaStatus(str, Enum):
    """Result of structured-action schema validation (SPEC section 5.6, section 8.5)."""
    VALID = "valid"
    INVALID = "invalid"


class GuardrailDecision(str, Enum):
    """Guardrail evaluation result (SPEC section 5.7)."""
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"


class ApprovalStatus(str, Enum):
    """Approval request lifecycle (SPEC section 8.8)."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ReportStatus(str, Enum):
    """Final report outcome (SPEC section 5.11)."""
    SUCCESS = "success"
    FAILURE = "failure"


class ActionType(str, Enum):
    """Supported structured action types (SPEC section 5.6)."""
    READ_FILE = "read_file"
    WRITE_FILE = "write_file"
    SEARCH = "search"
    LIST_FILES = "list_files"
    RUN_COMMAND = "run_command"
    SHOW_DIFF = "show_diff"
    RECORD_MEMORY = "record_memory"
    FINISH = "finish"


class FeedbackSource(str, Enum):
    """Source of validation / mechanism feedback (SPEC section 8.7)."""
    TEST = "test"
    LINT = "lint"
    TYPECHECK = "typecheck"
    BUILD = "build"
    SCHEMA_VALIDATION = "schema_validation"
    GUARDRAIL = "guardrail"


class FeedbackCategory(str, Enum):
    """Category of a feedback entry (SPEC section 8.7)."""
    ASSERTION_FAILURE = "assertion_failure"
    SYNTAX_ERROR = "syntax_error"
    TYPE_ERROR = "type_error"
    STYLE_VIOLATION = "style_violation"
    UNSAFE_ACTION = "unsafe_action"
    INVALID_ACTION = "invalid_action"
    UNKNOWN = "unknown"


class ContextItemKind(str, Enum):
    """Kind of a ContextItem (SPEC section 8.3)."""
    CODE_STRUCTURE = "code_structure"
    PROJECT_CONVENTION = "project_convention"
    DECISION_MEMORY = "decision_memory"
    TEST_MAPPING = "test_mapping"


class MemoryKind(str, Enum):
    """Kind of a MemoryEntry (SPEC section 5.10)."""
    MODULE_RESPONSIBILITY = "module_responsibility"
    PROJECT_CONVENTION = "project_convention"
    HISTORICAL_DECISION = "historical_decision"
    REJECTED_ALTERNATIVE = "rejected_alternative"
    FAILURE_PATTERN = "failure_pattern"
    TASK_SUMMARY = "task_summary"


class ToolResultStatus(str, Enum):
    """Result of tool execution."""
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"


# -- Dataclasses ----------------------------------------------------


def _new_id() -> str:
    return uuid.uuid4().hex


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Task:
    """SPEC section 8.1 - User feature request."""
    id: str = field(default_factory=_new_id)
    title: str = ""
    description: str = ""
    repo_path: str = ""
    status: str = TaskStatus.PENDING.value
    created_at: str = field(default_factory=_utcnow)


@dataclass
class TaskRun:
    """SPEC section 8.2 - One execution attempt."""
    id: str = field(default_factory=_new_id)
    task_id: str = ""
    status: str = TaskStatus.PENDING.value
    max_repair_rounds: int = 6
    current_round: int = 0
    stop_reason: str | None = None
    started_at: str = field(default_factory=_utcnow)
    finished_at: str | None = None


@dataclass
class ContextItem:
    """SPEC section 8.3 - Retrievable context unit."""
    id: str = field(default_factory=_new_id)
    repo_path: str = ""
    kind: str = ""
    source_path: str | None = None
    symbol: str | None = None
    summary: str = ""
    content_ref: str | None = None
    metadata: dict[str, Any] | None = None
    updated_at: str = field(default_factory=_utcnow)


@dataclass
class ContextPackage:
    """SPEC section 8.4 - Context selected for one round.

    `items` holds the list of ContextItem ids included in this package.
    """
    id: str = field(default_factory=_new_id)
    task_run_id: str = ""
    round_index: int = 0
    items: list[str] = field(default_factory=list)
    token_estimate: int = 0
    selection_reason: str = ""
    created_at: str = field(default_factory=_utcnow)


@dataclass
class Action:
    """SPEC section 8.5 - One LLM proposed action."""
    id: str = field(default_factory=_new_id)
    task_run_id: str = ""
    round_index: int = 0
    action_type: str = ""
    args_json: str = "{}"
    schema_status: str = SchemaStatus.VALID.value
    guardrail_status: str | None = None
    created_at: str = field(default_factory=_utcnow)


@dataclass
class ToolResult:
    """SPEC section 8.6 - Result of executing a tool."""
    id: str = field(default_factory=_new_id)
    action_id: str = ""
    status: str = ToolResultStatus.SUCCESS.value
    stdout_excerpt: str | None = None
    stderr_excerpt: str | None = None
    exit_code: int | None = None
    changed_files: list[str] | None = None
    duration_ms: int | None = None
    created_at: str = field(default_factory=_utcnow)


@dataclass
class Feedback:
    """SPEC section 8.7 - Validation or mechanism feedback."""
    id: str = field(default_factory=_new_id)
    task_run_id: str = ""
    round_index: int = 0
    source: str = ""
    category: str = ""
    summary: str = ""
    locations: list[str] | None = None
    raw_excerpt: str | None = None
    created_at: str = field(default_factory=_utcnow)


@dataclass
class ApprovalRequest:
    """SPEC section 8.8 - Pending human approval."""
    id: str = field(default_factory=_new_id)
    task_run_id: str = ""
    action_id: str = ""
    risk_level: str = ""
    reason: str = ""
    status: str = ApprovalStatus.PENDING.value
    decided_by: str | None = None
    decided_at: str | None = None


@dataclass
class MemoryEntry:
    """SPEC section 8.9 - Long-term repository memory."""
    id: str = field(default_factory=_new_id)
    repo_path: str = ""
    kind: str = ""
    content: str = ""
    source_task_id: str | None = None
    confidence: float = 0.5
    created_at: str = field(default_factory=_utcnow)
    superseded_by: str | None = None


@dataclass
class TaskProfile:
    """Deterministic discovery hints extracted from a task request."""
    task_type: str = "feature"
    keywords: list[str] = field(default_factory=list)
    symbols: list[str] = field(default_factory=list)
    likely_modules: list[str] = field(default_factory=list)
    validation_requirements: list[str] = field(default_factory=list)
    out_of_scope: bool = False
    decomposition_reason: str = ""


# -- Audit event helpers --------------------------------------------

# SPEC section 8.10 lists these event types:
#   task.created, context.selected, action.received, schema.invalid,
#   guardrail.blocked, approval.requested, approval.decided,
#   tool.completed, feedback.generated, run.finished


def make_audit_event(event_type: str, **fields: Any) -> dict[str, Any]:
    """Create an audit event dict with timestamp."""
    return {"type": event_type, "timestamp": _utcnow(), **fields}
