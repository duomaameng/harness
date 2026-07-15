"""Redacted Markdown and JSON exports for completed harness runs."""

from __future__ import annotations

import json
import re
from typing import Any, Mapping


class ReportExporter:
    """Serialize a run report without exposing credentials or secret-like values."""

    _SECRET_VALUE = re.compile(r"\bsk-[A-Za-z0-9_-]+\b")
    _BEARER = re.compile(r"\bBearer\s+[^\s,;}]+", re.IGNORECASE)
    _SENSITIVE_ASSIGNMENT = re.compile(
        r"(\b[A-Za-z0-9_-]*(?:api[_-]?key|access[_-]?token|auth[_-]?token|"
        r"password|passwd|secret|credential|private[_-]?key|token)\s*[:=]\s*)"
        r"([^\s,;}]+)",
        re.IGNORECASE,
    )

    def __init__(self, report: Mapping[str, Any]):
        self.report = report

    def to_json(self) -> str:
        return json.dumps(self._redact(self.report), ensure_ascii=False, indent=2)

    export_json = to_json

    def to_markdown(self) -> str:
        redacted = self._redact(self.report)
        lines = ["# Harness Run Report", ""]
        for key, value in redacted.items():
            lines.extend((f"## {key.replace('_', ' ').title()}", "", self._format(value), ""))
        return "\n".join(lines).rstrip() + "\n"

    export_markdown = to_markdown

    @classmethod
    def _redact(cls, value: Any, key: str | None = None) -> Any:
        if key is not None and cls._is_sensitive_key(key):
            return "[REDACTED]"
        if isinstance(value, Mapping):
            return {str(item_key): cls._redact(item, str(item_key)) for item_key, item in value.items()}
        if isinstance(value, list):
            return [cls._redact(item) for item in value]
        if isinstance(value, tuple):
            return [cls._redact(item) for item in value]
        if isinstance(value, str):
            value = cls._SENSITIVE_ASSIGNMENT.sub(r"\1[REDACTED]", value)
            value = cls._BEARER.sub("Bearer [REDACTED]", value)
            return cls._SECRET_VALUE.sub("[REDACTED]", value)
        return value

    @staticmethod
    def _is_sensitive_key(key: str) -> bool:
        snake_key = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", key)
        normalized = re.sub(r"[^a-z0-9]+", "_", snake_key.lower()).strip("_")
        return (
            normalized in {
                "api_key", "access_token", "auth_token", "password", "passwd",
                "secret", "credential", "credentials", "private_key", "token",
            }
            or normalized.endswith(("_secret", "_token", "_api_key", "_private_key"))
        )

    @staticmethod
    def _format(value: Any) -> str:
        if isinstance(value, (dict, list)):
            return "```json\n" + json.dumps(value, ensure_ascii=False, indent=2) + "\n```"
        return str(value)
