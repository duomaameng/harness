"""Structured action schema parser (SPEC section 5.6).

Validates LLM JSON output against the supported action protocol,
converting invalid output into structured schema-validation feedback
without executing any tool.
"""

from __future__ import annotations

import json
from typing import Any

from harness.domain import (
    Action,
    ActionType,
    Feedback,
    FeedbackCategory,
    FeedbackSource,
    MemoryKind,
    SchemaStatus,
)

# -- Per-action argument schemas ------------------------------------
#
# SPEC section 5.6 defines eight action types.  Required argument fields and
# their expected types are derived from the action names and the tool
# descriptions in SPEC section 5.8 / section 6.1.  The SPEC does not provide an
# exhaustive per-action argument table, so these schemas represent the
# minimum necessary validation.

_ACTION_SCHEMAS: dict[str, dict[str, Any]] = {
    ActionType.READ_FILE.value: {
        "required": ["path"],
        "optional": [],
        "types": {"path": str},
    },
    ActionType.WRITE_FILE.value: {
        "required": ["path", "content"],
        "optional": [],
        "types": {"path": str, "content": str},
    },
    ActionType.SEARCH.value: {
        "required": ["query"],
        "optional": ["path"],
        "types": {"query": str, "path": str},
    },
    ActionType.LIST_FILES.value: {
        "required": [],
        "optional": ["path"],
        "types": {"path": str},
    },
    ActionType.RUN_COMMAND.value: {
        "required": ["command"],
        "optional": [],
        "types": {"command": str},
    },
    ActionType.SHOW_DIFF.value: {
        "required": [],
        "optional": ["path"],
        "types": {"path": str},
    },
    ActionType.RECORD_MEMORY.value: {
        "required": ["kind", "content"],
        "optional": [],
        "types": {"kind": str, "content": str},
    },
    ActionType.FINISH.value: {
        "required": ["summary"],
        "optional": [],
        "types": {"summary": str},
    },
}

_VALID_ACTIONS = set(_ACTION_SCHEMAS.keys())
_VALID_MEMORY_KINDS = {kind.value for kind in MemoryKind}


# -- Parser ---------------------------------------------------------


class ActionParser:
    """Parse LLM JSON output into a validated Action + optional Feedback.

    SPEC section 5.6: the LLM must return structured JSON with:
      - thought_summary (str)
      - action (str)  - one of eight supported types
      - args (object) - per-action required fields with correct types

    Invalid JSON, unknown action types, missing fields, and wrong
    argument types are *not* executed - they become structured
    Feedback with source="schema_validation" and category="invalid_action".
    """

    @staticmethod
    def parse(raw: str, task_run_id: str = "", round_index: int = 0) -> tuple[Action, Feedback | None]:
        """Parse *raw* LLM output.

        Returns:
            (Action, Feedback | None) - Feedback is populated only when
            schema validation fails.
        """
        # 1. Parse JSON
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            action = Action(
                task_run_id=task_run_id,
                round_index=round_index,
                action_type="",
                args_json=raw,
                schema_status=SchemaStatus.INVALID.value,
            )
            fb = Feedback(
                task_run_id=task_run_id,
                round_index=round_index,
                source=FeedbackSource.SCHEMA_VALIDATION.value,
                category=FeedbackCategory.INVALID_ACTION.value,
                summary=f"Invalid JSON: {exc.msg}",
                raw_excerpt=raw[:500],
            )
            return action, fb

        if not isinstance(data, dict):
            action = Action(
                task_run_id=task_run_id,
                round_index=round_index,
                action_type="",
                args_json=raw,
                schema_status=SchemaStatus.INVALID.value,
            )
            fb = Feedback(
                task_run_id=task_run_id,
                round_index=round_index,
                source=FeedbackSource.SCHEMA_VALIDATION.value,
                category=FeedbackCategory.INVALID_ACTION.value,
                summary="LLM output is not a JSON object",
                raw_excerpt=raw[:500],
            )
            return action, fb

        # 2. Validate top-level fields
        missing_toplevel = []
        for field in ("thought_summary", "action", "args"):
            if field not in data:
                missing_toplevel.append(field)

        if missing_toplevel:
            action = Action(
                task_run_id=task_run_id,
                round_index=round_index,
                action_type=data.get("action", ""),
                args_json=json.dumps(data.get("args", {}), ensure_ascii=False),
                schema_status=SchemaStatus.INVALID.value,
            )
            fb = Feedback(
                task_run_id=task_run_id,
                round_index=round_index,
                source=FeedbackSource.SCHEMA_VALIDATION.value,
                category=FeedbackCategory.INVALID_ACTION.value,
                summary=f"Missing required fields: {', '.join(missing_toplevel)}",
                raw_excerpt=raw[:500],
            )
            return action, fb

        action_name = data["action"]
        args = data["args"]

        if not isinstance(data["thought_summary"], str):
            action = Action(
                task_run_id=task_run_id,
                round_index=round_index,
                action_type=action_name if isinstance(action_name, str) else "",
                args_json=json.dumps(args, ensure_ascii=False),
                schema_status=SchemaStatus.INVALID.value,
            )
            fb = Feedback(
                task_run_id=task_run_id,
                round_index=round_index,
                source=FeedbackSource.SCHEMA_VALIDATION.value,
                category=FeedbackCategory.INVALID_ACTION.value,
                summary="'thought_summary' expected str",
                raw_excerpt=raw[:500],
            )
            return action, fb

        if not isinstance(action_name, str):
            action = Action(
                task_run_id=task_run_id,
                round_index=round_index,
                action_type="",
                args_json=json.dumps(args, ensure_ascii=False),
                schema_status=SchemaStatus.INVALID.value,
            )
            fb = Feedback(
                task_run_id=task_run_id,
                round_index=round_index,
                source=FeedbackSource.SCHEMA_VALIDATION.value,
                category=FeedbackCategory.INVALID_ACTION.value,
                summary="'action' expected str",
                raw_excerpt=raw[:500],
            )
            return action, fb

        if not isinstance(args, dict):
            action = Action(
                task_run_id=task_run_id,
                round_index=round_index,
                action_type=action_name,
                args_json=json.dumps(args, ensure_ascii=False),
                schema_status=SchemaStatus.INVALID.value,
            )
            fb = Feedback(
                task_run_id=task_run_id,
                round_index=round_index,
                source=FeedbackSource.SCHEMA_VALIDATION.value,
                category=FeedbackCategory.INVALID_ACTION.value,
                summary="'args' must be a JSON object",
                raw_excerpt=raw[:500],
            )
            return action, fb

        # 3. Validate action type
        if action_name not in _VALID_ACTIONS:
            action = Action(
                task_run_id=task_run_id,
                round_index=round_index,
                action_type=action_name,
                args_json=json.dumps(args, ensure_ascii=False),
                schema_status=SchemaStatus.INVALID.value,
            )
            fb = Feedback(
                task_run_id=task_run_id,
                round_index=round_index,
                source=FeedbackSource.SCHEMA_VALIDATION.value,
                category=FeedbackCategory.INVALID_ACTION.value,
                summary=f"Unknown action type: '{action_name}'. "
                f"Supported: {', '.join(sorted(_VALID_ACTIONS))}",
                raw_excerpt=raw[:500],
            )
            return action, fb

        # 4. Validate per-action arguments
        schema = _ACTION_SCHEMAS[action_name]
        required = schema["required"]
        optional = schema["optional"]
        allowed = set(required) | set(optional)
        type_map = schema["types"]

        # Check for unknown argument keys
        unknown_args = [k for k in args if k not in allowed]
        if unknown_args:
            action = Action(
                task_run_id=task_run_id,
                round_index=round_index,
                action_type=action_name,
                args_json=json.dumps(args, ensure_ascii=False),
                schema_status=SchemaStatus.INVALID.value,
            )
            fb = Feedback(
                task_run_id=task_run_id,
                round_index=round_index,
                source=FeedbackSource.SCHEMA_VALIDATION.value,
                category=FeedbackCategory.INVALID_ACTION.value,
                summary=f"Unknown argument(s) for '{action_name}': {', '.join(unknown_args)}. "
                f"Allowed: {', '.join(sorted(allowed))}",
                raw_excerpt=raw[:500],
            )
            return action, fb

        # Check for missing required arguments
        missing_args = [k for k in required if k not in args]
        if missing_args:
            action = Action(
                task_run_id=task_run_id,
                round_index=round_index,
                action_type=action_name,
                args_json=json.dumps(args, ensure_ascii=False),
                schema_status=SchemaStatus.INVALID.value,
            )
            fb = Feedback(
                task_run_id=task_run_id,
                round_index=round_index,
                source=FeedbackSource.SCHEMA_VALIDATION.value,
                category=FeedbackCategory.INVALID_ACTION.value,
                summary=f"'{action_name}' requires: {', '.join(missing_args)}",
                raw_excerpt=raw[:500],
            )
            return action, fb

        # Check argument types
        for key, expected_type in type_map.items():
            if key in args and not isinstance(args[key], expected_type):
                action = Action(
                    task_run_id=task_run_id,
                    round_index=round_index,
                    action_type=action_name,
                    args_json=json.dumps(args, ensure_ascii=False),
                    schema_status=SchemaStatus.INVALID.value,
                )
                fb = Feedback(
                    task_run_id=task_run_id,
                    round_index=round_index,
                    source=FeedbackSource.SCHEMA_VALIDATION.value,
                    category=FeedbackCategory.INVALID_ACTION.value,
                    summary=f"'{action_name}.{key}' expected {expected_type.__name__}, "
                    f"got {type(args[key]).__name__}",
                    raw_excerpt=raw[:500],
                )
                return action, fb

        if action_name == ActionType.RECORD_MEMORY.value and args["kind"] not in _VALID_MEMORY_KINDS:
            action = Action(
                task_run_id=task_run_id,
                round_index=round_index,
                action_type=action_name,
                args_json=json.dumps(args, ensure_ascii=False),
                schema_status=SchemaStatus.INVALID.value,
            )
            fb = Feedback(
                task_run_id=task_run_id,
                round_index=round_index,
                source=FeedbackSource.SCHEMA_VALIDATION.value,
                category=FeedbackCategory.INVALID_ACTION.value,
                summary=f"'record_memory.kind' unknown value: {args['kind']}. "
                f"Supported: {', '.join(sorted(_VALID_MEMORY_KINDS))}",
                raw_excerpt=raw[:500],
            )
            return action, fb

        # 5. Success
        action = Action(
            task_run_id=task_run_id,
            round_index=round_index,
            action_type=action_name,
            args_json=json.dumps(args, ensure_ascii=False),
            schema_status=SchemaStatus.VALID.value,
        )
        return action, None
