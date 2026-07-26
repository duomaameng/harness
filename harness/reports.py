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
        r"(\"(?:\\.|[^\"])*\"|'(?:\\.|[^'])*'|[^\s,;}]+)",
        re.IGNORECASE,
    )

    def __init__(self, report: Mapping[str, Any]):
        self.report = report

    def to_json(self) -> str:
        return json.dumps(self._redact(self.report), ensure_ascii=False, indent=2)

    export_json = to_json

    def to_markdown(self) -> str:
        redacted = self._redact(self.report)
        lines = ["# \u8fd0\u884c\u62a5\u544a", ""]
        self._render_overview(lines, redacted)
        self._render_conclusion(lines, redacted)
        self._render_context(lines, redacted)
        self._render_actions(lines, redacted)
        self._render_feedback(lines, redacted)
        self._render_approvals(lines, redacted)
        self._render_changed_files(lines, redacted)
        lines.extend(("## \u5ba1\u8ba1\u539f\u59cb\u6570\u636e", "", "<details>", "<summary>\u5ba1\u8ba1\u539f\u59cb\u6570\u636e</summary>", "", "```json", json.dumps(redacted, ensure_ascii=False, indent=2), "```", "", "</details>", ""))
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
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, (Mapping, list)):
                return json.dumps(cls._redact(parsed), ensure_ascii=False)
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

    @staticmethod
    def _section(lines: list[str], title: str) -> None:
        lines.extend((f"## {title}", ""))

    @staticmethod
    def _value(value: Any) -> str:
        return str(value) if value not in (None, "") else "-"

    def _render_overview(self, lines: list[str], report: Mapping[str, Any]) -> None:
        self._section(lines, "\u8fd0\u884c\u6982\u89c8")
        for label, key in (("\u4efb\u52a1", "task_request"), ("\u72b6\u6001", "final_status"), ("\u505c\u6b62\u539f\u56e0", "stop_reason")):
            if key in report:
                lines.append(f"- {label}: {self._value(report[key])}")
        lines.append("")

    def _render_conclusion(self, lines: list[str], report: Mapping[str, Any]) -> None:
        self._section(lines, "\u6700\u7ec8\u7ed3\u8bba")
        summary = ""
        for action in report.get("action_trace", []):
            if not isinstance(action, Mapping) or self._action_name(action) != "finish":
                continue
            args = self._action_args(action)
            if isinstance(args, Mapping):
                summary = self._value(args.get("summary")) if args.get("summary") else ""
            if not summary:
                summary = self._value(action.get("excerpt"))
        lines.extend((summary or "-", ""))

    def _render_context(self, lines: list[str], report: Mapping[str, Any]) -> None:
        self._section(lines, "\u5df2\u9009\u4e0a\u4e0b\u6587")
        context = report.get("selected_context", [])
        lines.append("| \u6587\u4ef6 | \u7c7b\u578b | \u9009\u62e9\u539f\u56e0 | \u8bc4\u5206 |")
        lines.append("| --- | --- | --- | --- |")
        rendered = False
        for package in context:
            items = package.get("items", []) if isinstance(package, Mapping) else [package]
            for item in items:
                if not isinstance(item, Mapping):
                    continue
                metadata = item.get("metadata") if isinstance(item.get("metadata"), Mapping) else {}
                path = item.get("source_path") or item.get("file")
                if self._is_absolute_path(path):
                    continue
                lines.append("| {} | {} | {} | {} |".format(
                    self._value(path), self._value(item.get("kind") or item.get("type")),
                    self._value(item.get("summary") or item.get("reason")),
                    self._value(metadata.get("score") or item.get("score")),
                ))
                rendered = True
        if not rendered:
            lines.append("| - | - | - | - |")
        lines.append("")

    def _render_actions(self, lines: list[str], report: Mapping[str, Any]) -> None:
        self._section(lines, "\u52a8\u4f5c\u8f68\u8ff9")
        actions = report.get("action_trace", [])
        for action in actions:
            if not isinstance(action, Mapping):
                lines.append(f"- {self._value(action)}")
                continue
            tool = self._action_name(action)
            args = self._action_args(action)
            path = action.get("path") or (args.get("path") if isinstance(args, Mapping) else None)
            if tool == "read_file" and path:
                lines.append(f"- \u8bfb\u53d6\u6587\u4ef6: {path}")
            elif args:
                rendered = json.dumps(args, ensure_ascii=False) if isinstance(args, (Mapping, list)) else str(args)
                lines.append(f"- {tool}: {rendered}")
            else:
                lines.append(f"- {tool}: {self._value(action.get('excerpt'))}")
        if not actions:
            lines.append("- -")
        lines.append("")

    def _render_feedback(self, lines: list[str], report: Mapping[str, Any]) -> None:
        self._section(lines, "\u9a8c\u8bc1\u4e0e\u53cd\u9988")
        feedback = report.get("feedback", [])
        results = report.get("tool_results", [])
        for item in [*feedback, *results]:
            if isinstance(item, Mapping):
                lines.append(f"- {self._render_record(item)}")
            else:
                lines.append(f"- {self._value(item)}")
        if not feedback and not results:
            lines.append("- -")
        lines.append("")

    def _render_approvals(self, lines: list[str], report: Mapping[str, Any]) -> None:
        self._section(lines, "\u5ba1\u6279\u8bb0\u5f55")
        approvals = report.get("approval_decisions", [])
        for approval in approvals:
            if isinstance(approval, Mapping):
                lines.append(f"- {self._render_record(approval)}")
            else:
                lines.append(f"- {self._value(approval)}")
        if not approvals:
            lines.append("- -")
        lines.append("")

    def _render_changed_files(self, lines: list[str], report: Mapping[str, Any]) -> None:
        self._section(lines, "\u53d8\u66f4\u6587\u4ef6")
        files = report.get("changed_files", [])
        for path in files:
            lines.append(f"- {self._value(path)}")
        if not files:
            lines.append("- -")
        lines.append("")

    @staticmethod
    def _action_args(action: Mapping[str, Any]) -> Any:
        args = action.get("args") if "args" in action else action.get("args_json")
        if not isinstance(args, str):
            return args
        try:
            return json.loads(args)
        except json.JSONDecodeError:
            return args

    @staticmethod
    def _action_name(action: Mapping[str, Any]) -> str:
        return str(action.get("action_type") or action.get("tool") or "-")

    @staticmethod
    def _is_absolute_path(value: Any) -> bool:
        return isinstance(value, str) and (value.startswith(("/", "\\")) or bool(re.match(r"^[A-Za-z]:[\\/]", value)))

    def _render_record(self, record: Mapping[str, Any]) -> str:
        preferred = ("state", "status", "reason", "result", "comment", "excerpt")
        values = [f"{key}: {self._value(record[key])}" for key in preferred if key in record]
        if values:
            return "; ".join(values)
        return "; ".join(f"{key}: {self._value(value)}" for key, value in record.items()) or "-"
