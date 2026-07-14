"""Parse and validate structured LLM actions."""

from __future__ import annotations

import json
from typing import Any

from harness.domain import (
    Action,
    ActionType,
    Feedback,
    FeedbackCategory,
    FeedbackSource,
    SchemaStatus,
)


class ActionParser:
    """Convert an LLM JSON payload into an Action plus optional schema feedback."""

    _ARG_SCHEMA: dict[str, dict[str, type[Any]]] = {
        ActionType.READ_FILE.value: {"path": str},
        ActionType.WRITE_FILE.value: {"path": str, "content": str},
        ActionType.SEARCH.value: {"query": str},
        ActionType.LIST_FILES.value: {"path": str},
        ActionType.RUN_COMMAND.value: {"command": str},
        ActionType.SHOW_DIFF.value: {},
        ActionType.RECORD_MEMORY.value: {"kind": str, "content": str},
        ActionType.FINISH.value: {"status": str, "summary": str},
    }

    def parse(self, payload: str) -> tuple[Action, Feedback | None]:
        try:
            decoded = json.loads(payload)
        except json.JSONDecodeError as exc:
            action = self._invalid_action()
            return action, self._feedback("Invalid JSON action payload.", str(exc))

        if not isinstance(decoded, dict):
            action = self._invalid_action()
            return action, self._feedback("Action payload must be a JSON object.", payload)

        thought_summary = decoded.get("thought_summary")
        action_type = decoded.get("action")
        args = decoded.get("args")
        action = self._action(
            thought_summary=thought_summary if isinstance(thought_summary, str) else "",
            action_type=action_type if isinstance(action_type, str) else "",
            args=args if isinstance(args, dict) else {},
        )

        error = self._validation_error(thought_summary, action_type, args)
        if error is not None:
            action.schema_status = SchemaStatus.INVALID.value
            return action, self._feedback(error, payload)

        return action, None

    def _validation_error(
        self, thought_summary: object, action_type: object, args: object
    ) -> str | None:
        if not isinstance(thought_summary, str) or not thought_summary:
            return "Missing or invalid required field: thought_summary."
        if not isinstance(action_type, str) or not action_type:
            return "Missing or invalid required field: action."
        if not isinstance(args, dict):
            return "Missing or invalid required field: args."
        if action_type not in self._ARG_SCHEMA:
            return f"Unsupported action type: {action_type}."

        required_args = self._ARG_SCHEMA[action_type]
        for name, expected_type in required_args.items():
            if name not in args:
                return f"Missing required argument for {action_type}: {name}."
            if not isinstance(args[name], expected_type):
                return f"Invalid type for {action_type}.{name}: expected {expected_type.__name__}."
        return None

    def _action(self, *, thought_summary: str = "", action_type: str = "", args: dict[str, Any] | None = None) -> Action:
        normalized_args = args or {}
        return Action(
            action_type=action_type,
            args_json=json.dumps(normalized_args, ensure_ascii=False, sort_keys=True),
        )

    def _invalid_action(self) -> Action:
        action = self._action()
        action.schema_status = SchemaStatus.INVALID.value
        return action

    def _feedback(self, summary: str, raw_excerpt: str | None = None) -> Feedback:
        return Feedback(
            source=FeedbackSource.SCHEMA_VALIDATION.value,
            category=FeedbackCategory.INVALID_ACTION.value,
            summary=summary,
            raw_excerpt=raw_excerpt,
        )
