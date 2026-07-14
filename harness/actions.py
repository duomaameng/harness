"""Parse and validate structured LLM actions."""

from __future__ import annotations

import json
import re
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


class ActionParser:
    """Convert an LLM JSON payload into an Action plus optional schema feedback."""

    _ARG_SCHEMA: dict[str, dict[str, dict[str, type[Any]]]] = {
        ActionType.READ_FILE.value: {"required": {"path": str}, "optional": {}},
        ActionType.WRITE_FILE.value: {
            "required": {"path": str, "content": str},
            "optional": {},
        },
        ActionType.SEARCH.value: {"required": {"query": str}, "optional": {"path": str}},
        ActionType.LIST_FILES.value: {"required": {}, "optional": {"path": str}},
        ActionType.RUN_COMMAND.value: {"required": {"command": str}, "optional": {}},
        ActionType.SHOW_DIFF.value: {"required": {}, "optional": {"path": str}},
        ActionType.RECORD_MEMORY.value: {
            "required": {"kind": str, "content": str},
            "optional": {},
        },
        ActionType.FINISH.value: {"required": {"summary": str}, "optional": {}},
    }
    _MEMORY_KINDS = {kind.value for kind in MemoryKind}
    _RAW_EXCERPT_LIMIT = 240
    _ALLOW_BLANK_ARGS = {(ActionType.WRITE_FILE.value, "content")}
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
    _SECRET_VALUE = re.compile(r"\bsk-[A-Za-z0-9_-]+\b")
    _SENSITIVE_ASSIGNMENT = re.compile(
        r"(\b[A-Za-z0-9_-]*(?:api[_-]?key|access[_-]?token|auth[_-]?token|"
        r"password|passwd|secret|credential|private[_-]?key|token)\s*[:=]\s*)"
        r"([^\s,;}]+)",
        re.IGNORECASE,
    )
    _SENSITIVE_JSON_FIELD = re.compile(
        r'("(?:[^"]*(?:api[_-]?key|access[_-]?token|auth[_-]?token|'
        r'password|passwd|secret|credential|private[_-]?key|token)[^"]*)"\s*:\s*)"[^"]*"',
        re.IGNORECASE,
    )

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
        if not thought_summary.strip():
            return "Missing or invalid required field: thought_summary."
        if not isinstance(action_type, str) or not action_type:
            return "Missing or invalid required field: action."
        if not action_type.strip():
            return "Missing or invalid required field: action."
        if not isinstance(args, dict):
            return "Missing or invalid required field: args."
        if action_type not in self._ARG_SCHEMA:
            return f"Unsupported action type: {action_type}."

        required_args = self._ARG_SCHEMA[action_type]["required"]
        optional_args = self._ARG_SCHEMA[action_type]["optional"]
        allowed_args = set(required_args) | set(optional_args)
        unknown_args = sorted(set(args) - allowed_args)
        if unknown_args:
            return f"Unexpected argument(s) for {action_type}: {', '.join(unknown_args)}."
        for name, expected_type in required_args.items():
            if name not in args:
                return f"Missing required argument for {action_type}: {name}."
            if not isinstance(args[name], expected_type):
                return f"Invalid type for {action_type}.{name}: expected {expected_type.__name__}."
            if (
                expected_type is str
                and (action_type, name) not in self._ALLOW_BLANK_ARGS
                and not args[name].strip()
            ):
                return f"Argument {action_type}.{name} must not be blank."
        for name, expected_type in optional_args.items():
            if name in args and not isinstance(args[name], expected_type):
                return f"Invalid type for {action_type}.{name}: expected {expected_type.__name__}."
            if name in args and expected_type is str and not args[name].strip():
                return f"Argument {action_type}.{name} must not be blank."
        if (
            action_type == ActionType.RECORD_MEMORY.value
            and args["kind"] not in self._MEMORY_KINDS
        ):
            return f"Invalid memory kind: {args['kind']}."
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
            raw_excerpt=self._safe_excerpt(raw_excerpt),
        )

    def _safe_excerpt(self, raw_excerpt: str | None) -> str | None:
        if raw_excerpt is None:
            return None
        try:
            parsed = json.loads(raw_excerpt)
        except json.JSONDecodeError:
            redacted = raw_excerpt
        else:
            redacted = json.dumps(self._redact_sensitive_values(parsed), ensure_ascii=False)
        redacted = self._SENSITIVE_JSON_FIELD.sub(r'\1"[REDACTED]"', redacted)
        redacted = self._SENSITIVE_ASSIGNMENT.sub(r"\1[REDACTED]", redacted)
        redacted = self._SECRET_VALUE.sub("[REDACTED]", redacted)
        if len(redacted) <= self._RAW_EXCERPT_LIMIT:
            return redacted
        return redacted[: self._RAW_EXCERPT_LIMIT - 3] + "..."

    def _redact_sensitive_values(self, value: Any, key: str | None = None) -> Any:
        if key is not None and self._is_sensitive_key(key):
            return "[REDACTED]"
        if isinstance(value, dict):
            return {
                item_key: self._redact_sensitive_values(item_value, str(item_key))
                for item_key, item_value in value.items()
            }
        if isinstance(value, list):
            return [self._redact_sensitive_values(item) for item in value]
        return value

    def _is_sensitive_key(self, key: str) -> bool:
        snake_key = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", key)
        normalized = re.sub(r"[^a-z0-9]+", "_", snake_key.lower()).strip("_")
        return (
            normalized in self._SENSITIVE_KEY_NAMES
            or normalized.endswith("_secret")
            or normalized.endswith("_token")
            or normalized.endswith("_api_key")
            or normalized.endswith("_private_key")
        )
