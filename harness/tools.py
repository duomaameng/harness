"""Controlled tool dispatcher for already-approved actions."""

from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from harness.domain import (
    Action,
    ActionType,
    GuardrailDecision,
    MemoryEntry,
    SchemaStatus,
    ToolResult,
    ToolResultStatus,
)
from harness.storage import HarnessStorage, _redact


@dataclass(frozen=True)
class ToolLimits:
    stdout_chars: int = 4000
    stderr_chars: int = 4000
    file_chars: int = 4000
    search_chars: int = 4000
    command_timeout_seconds: int = 30


class ToolDispatcher:
    """Execute only actions that have already passed schema and guardrails."""

    def __init__(self, storage: HarnessStorage, limits: ToolLimits | None = None) -> None:
        self.storage = storage
        self.limits = limits or ToolLimits()

    def dispatch(self, action: Action, *, repo_root: str | Path) -> ToolResult:
        repo = Path(repo_root).resolve()
        self._require_allowed(action)
        args = self._load_args(action)

        handlers = {
            ActionType.READ_FILE.value: self._read_file,
            ActionType.WRITE_FILE.value: self._write_file,
            ActionType.SEARCH.value: self._search,
            ActionType.LIST_FILES.value: self._list_files,
            ActionType.RUN_COMMAND.value: self._run_command,
            ActionType.SHOW_DIFF.value: self._show_diff,
            ActionType.RECORD_MEMORY.value: self._record_memory,
        }
        handler = handlers.get(action.action_type)
        if handler is None:
            raise ValueError(f"Unsupported tool action: {action.action_type}")

        start = time.perf_counter()
        try:
            stdout, stderr, exit_code, changed_files = handler(action, args, repo)
            stdout_limit = (
                self.limits.file_chars
                if action.action_type == ActionType.READ_FILE.value
                else self.limits.search_chars
                if action.action_type == ActionType.SEARCH.value
                else self.limits.stdout_chars
            )
            status = (
                ToolResultStatus.SUCCESS.value
                if exit_code in (None, 0)
                else ToolResultStatus.ERROR.value
            )
        except subprocess.TimeoutExpired as exc:
            stdout = self._decode(exc.stdout)
            stderr = self._decode(exc.stderr) or "Command timed out."
            exit_code = None
            changed_files = getattr(exc, "changed_files", None)
            stdout_limit = self.limits.stdout_chars
            status = ToolResultStatus.TIMEOUT.value
        except Exception as exc:
            stdout = None
            stderr = str(exc)
            exit_code = 1
            changed_files = None
            stdout_limit = self.limits.stdout_chars
            status = ToolResultStatus.ERROR.value
        duration_ms = int((time.perf_counter() - start) * 1000)

        stdout_excerpt, stdout_meta = self._safe_excerpt_with_metadata(
            stdout, stdout_limit
        )
        stderr_excerpt, stderr_meta = self._safe_excerpt_with_metadata(
            stderr, self.limits.stderr_chars
        )

        result = ToolResult(
            action_id=action.id,
            status=status,
            stdout_excerpt=stdout_excerpt,
            stderr_excerpt=stderr_excerpt,
            exit_code=exit_code,
            changed_files=changed_files,
            duration_ms=duration_ms,
            metadata={
                "stdout_redacted": stdout_meta["redacted"],
                "stdout_truncated": stdout_meta["truncated"],
                "stdout_limit": stdout_limit,
                "stderr_redacted": stderr_meta["redacted"],
                "stderr_truncated": stderr_meta["truncated"],
                "stderr_limit": self.limits.stderr_chars,
            },
        )
        self.storage.create_tool_result(result)
        return result

    def _require_allowed(self, action: Action) -> None:
        if action.schema_status != SchemaStatus.VALID.value:
            raise ValueError("Cannot dispatch action that failed schema validation")
        if action.guardrail_status != GuardrailDecision.ALLOW.value:
            raise ValueError("Cannot dispatch action before guardrail allow decision")

    def _load_args(self, action: Action) -> dict[str, object]:
        try:
            value = json.loads(action.args_json or "{}")
        except json.JSONDecodeError as exc:
            raise ValueError("Action args_json must be valid JSON") from exc
        if not isinstance(value, dict):
            raise ValueError("Action args_json must decode to an object")
        return value

    def _read_file(
        self, action: Action, args: dict[str, object], repo: Path
    ) -> tuple[str, str | None, int | None, list[str] | None]:
        del action
        path = self._repo_path(repo, self._string_arg(args, "path"))
        return path.read_text(encoding="utf-8"), None, 0, None

    def _write_file(
        self, action: Action, args: dict[str, object], repo: Path
    ) -> tuple[str, str | None, int | None, list[str] | None]:
        del action
        raw_path = self._string_arg(args, "path")
        path = self._repo_path(repo, raw_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self._string_arg(args, "content"), encoding="utf-8")
        return "", None, 0, [self._relative(repo, path)]

    def _search(
        self, action: Action, args: dict[str, object], repo: Path
    ) -> tuple[str, str | None, int | None, list[str] | None]:
        del action
        query = self._string_arg(args, "query")
        root = self._repo_path(repo, str(args.get("path") or "."))
        files = [root] if root.is_file() else [p for p in root.rglob("*") if p.is_file()]
        matches: list[str] = []
        for path in files:
            if self._skip_path(repo, path):
                continue
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except UnicodeDecodeError:
                continue
            for lineno, line in enumerate(lines, start=1):
                if query in line:
                    matches.append(f"{self._relative(repo, path)}:{lineno}:{line}")
        return "\n".join(matches), None, 0, None

    def _list_files(
        self, action: Action, args: dict[str, object], repo: Path
    ) -> tuple[str, str | None, int | None, list[str] | None]:
        del action
        root = self._repo_path(repo, str(args.get("path") or "."))
        files = [root] if root.is_file() else [p for p in root.rglob("*") if p.is_file()]
        listed = [
            self._relative(repo, path)
            for path in sorted(files)
            if not self._skip_path(repo, path)
        ]
        return "\n".join(listed), None, 0, None

    def _run_command(
        self, action: Action, args: dict[str, object], repo: Path
    ) -> tuple[str, str | None, int | None, list[str] | None]:
        del action
        command = self._command_arg(args)
        before = self._changed_file_snapshot(repo)
        try:
            completed = subprocess.run(
                command,
                cwd=repo,
                text=True,
                capture_output=True,
                shell=True,
                timeout=self.limits.command_timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            exc.changed_files = self._changed_files_since(repo, before)
            raise
        changed = self._changed_files_since(repo, before)
        return completed.stdout, completed.stderr, completed.returncode, changed or None

    def _show_diff(
        self, action: Action, args: dict[str, object], repo: Path
    ) -> tuple[str, str | None, int | None, list[str] | None]:
        del action
        command = ["git", "diff", "--"]
        if args.get("path"):
            diff_path = self._repo_path(repo, self._string_arg(args, "path"))
            command.append(self._relative(repo, diff_path))
        completed = subprocess.run(
            command,
            cwd=repo,
            text=True,
            capture_output=True,
            shell=False,
            check=False,
        )
        return completed.stdout, completed.stderr, completed.returncode, None

    def _record_memory(
        self, action: Action, args: dict[str, object], repo: Path
    ) -> tuple[str, str | None, int | None, list[str] | None]:
        entry = MemoryEntry(
            repo_path=str(repo),
            kind=self._string_arg(args, "kind"),
            content=self._string_arg(args, "content"),
            source_task_id=action.task_run_id or None,
        )
        self.storage.create_memory_entry(entry)
        return entry.id, None, 0, None

    def _repo_path(self, repo: Path, raw_path: str) -> Path:
        candidate = (repo / raw_path).resolve()
        if candidate != repo and repo not in candidate.parents:
            raise ValueError("Tool path must stay inside repository root")
        return candidate

    def _string_arg(self, args: dict[str, object], name: str) -> str:
        value = args.get(name)
        if not isinstance(value, str):
            raise ValueError(f"Missing or invalid string argument: {name}")
        return value

    def _command_arg(self, args: dict[str, object]) -> str:
        value = args.get("command")
        if isinstance(value, str):
            return value
        raise ValueError("Missing or invalid command argument")

    def _changed_files(self, repo: Path) -> list[str]:
        completed = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo,
            text=True,
            capture_output=True,
            shell=False,
            check=False,
        )
        if completed.returncode != 0:
            return []
        changed: list[str] = []
        for line in completed.stdout.splitlines():
            path = line[3:] if len(line) > 3 else ""
            if " -> " in path:
                path = path.split(" -> ", 1)[1]
            if path:
                changed.append(path)
        return changed

    def _changed_file_snapshot(self, repo: Path) -> dict[str, tuple[int, int]]:
        snapshot: dict[str, tuple[int, int]] = {}
        for path in self._changed_files(repo):
            candidate = repo / path
            if candidate.is_file():
                stat = candidate.stat()
                snapshot[path] = (stat.st_mtime_ns, stat.st_size)
            else:
                snapshot[path] = (-1, -1)
        return snapshot

    def _changed_files_since(
        self, repo: Path, before: dict[str, tuple[int, int]]
    ) -> list[str] | None:
        changed: list[str] = []
        for path in self._changed_files(repo):
            candidate = repo / path
            if candidate.is_file():
                stat = candidate.stat()
                current = (stat.st_mtime_ns, stat.st_size)
            else:
                current = (-1, -1)
            if path not in before or before[path] != current:
                changed.append(path)
        return sorted(changed) or None

    def _safe_excerpt(self, value: str | None, limit: int) -> str | None:
        return self._safe_excerpt_with_metadata(value, limit)[0]

    def _safe_excerpt_with_metadata(
        self, value: str | None, limit: int
    ) -> tuple[str | None, dict[str, bool]]:
        if value is None:
            return None, {"redacted": False, "truncated": False}
        redacted = str(_redact(value))
        was_redacted = redacted != value
        if len(redacted) <= limit:
            return redacted, {"redacted": was_redacted, "truncated": False}
        return (
            redacted[: max(limit - 3, 0)] + "...",
            {"redacted": was_redacted, "truncated": True},
        )

    def _relative(self, repo: Path, path: Path) -> str:
        return path.resolve().relative_to(repo).as_posix()

    def _skip_path(self, repo: Path, path: Path) -> bool:
        rel_parts = path.resolve().relative_to(repo).parts
        return ".git" in rel_parts or ".harness" in rel_parts or "__pycache__" in rel_parts

    def _decode(self, value: str | bytes | None) -> str | None:
        if value is None or isinstance(value, str):
            return value
        return value.decode("utf-8", errors="replace")
