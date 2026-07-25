"""Shared service boundary for CLI, API, and future WebUI entry points."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from harness.auth import CredentialService
from harness.domain import ApprovalStatus, MemoryKind, Task
from harness.llm import LLMClient
from harness.memory import MemoryStore
from harness.reports import ReportExporter
from harness.runner import AgentRunner
from harness.storage import HarnessStorage


class CoreService:
    """Small application boundary over storage, runner, memory, and reports."""

    def __init__(
        self,
        repo_path: str | Path,
        *,
        llm: LLMClient | None = None,
        validation_commands: list[str | list[str]] | None = None,
    ) -> None:
        self.repo_path = Path(repo_path).resolve()
        self.storage = HarnessStorage(self.repo_path)
        self.storage.init()
        self.llm = llm
        self.validation_commands = validation_commands
        self.memory_store = MemoryStore(self.storage)

    def init(self) -> Path:
        self.storage.init()
        return self.storage.harness_dir

    def create_task(self, title: str, description: str = "") -> Task:
        return self.storage.create_task(
            Task(title=title, description=description, repo_path=str(self.repo_path))
        )

    def run_task(self, task_id: str, *, max_rounds: int = 6):
        if self.llm is None:
            raise ValueError("LLM client is required. Use MockLLM for offline tests or configure a real client.")
        runner = AgentRunner(
            storage=self.storage,
            llm=self.llm,
            repo_root=self.repo_path,
            validation_commands=self.validation_commands,
        )
        return runner.run(task_id, max_rounds=max_rounds)

    def get_status(self, run_id: str) -> dict[str, Any]:
        run = self._require_run(run_id)
        task = self.storage.get_task(run["task_id"])
        return {"run": run, "task": task}

    def list_context(self, run_id: str) -> list[dict[str, Any]]:
        self._require_run(run_id)
        packages = self.storage._fetchall(
            "SELECT * FROM context_package WHERE task_run_id=? ORDER BY round_index, created_at",
            (run_id,),
        )
        for package in packages:
            package["items"] = [
                self._context_item_payload(item_id)
                for item_id in self.storage.get_package_items(package["id"])
            ]
        return packages

    def list_actions(self, run_id: str) -> list[dict[str, Any]]:
        self._require_run(run_id)
        return self.storage.list_actions_for_run(run_id)

    def list_feedback(self, run_id: str) -> list[dict[str, Any]]:
        self._require_run(run_id)
        return self.storage.list_feedback_for_run(run_id)

    def list_approvals(self, run_id: str) -> list[dict[str, Any]]:
        self._require_run(run_id)
        return self.storage._fetchall(
            "SELECT * FROM approval_request WHERE task_run_id=? ORDER BY rowid",
            (run_id,),
        )

    def decide_approval(self, approval_id: str, status: str, decided_by: str = "cli") -> dict[str, Any]:
        if status not in {ApprovalStatus.APPROVED.value, ApprovalStatus.REJECTED.value}:
            raise ValueError(f"Unsupported approval status: {status}")
        if self.storage.get_approval_request(approval_id) is None:
            raise ValueError(f"Unknown approval request: {approval_id}")
        self.storage.update_approval_request(
            approval_id,
            status=status,
            decided_by=decided_by,
            decided_at=datetime.now(timezone.utc).isoformat(),
        )
        return self.storage.get_approval_request(approval_id) or {}

    def record_memory(
        self,
        *,
        kind: str = MemoryKind.TASK_SUMMARY.value,
        content: str,
        source_task_id: str | None = None,
        confidence: float = 0.5,
    ) -> dict[str, Any]:
        entry = self.memory_store.record(
            repo_path=str(self.repo_path),
            kind=kind,
            content=content,
            source_task_id=source_task_id,
            confidence=confidence,
        )
        return vars(entry)

    def list_memory(self, *, kind: str | None = None, keywords: list[str] | None = None) -> list[dict[str, Any]]:
        return [
            vars(entry)
            for entry in self.memory_store.query(
                repo_path=str(self.repo_path),
                kind=kind,
                keywords=keywords,
                include_superseded=False,
            )
        ]

    def report_payload(self, run_id: str) -> dict[str, Any]:
        status = self.get_status(run_id)
        run = status["run"]
        task = status["task"] or {}
        return {
            "task_request": task.get("description") or task.get("title", ""),
            "selected_context": self.list_context(run_id),
            "action_trace": self.list_actions(run_id),
            "tool_results": self.storage.list_tool_results_for_run(run_id),
            "validation": self.list_feedback(run_id),
            "repair_rounds": run.get("current_round"),
            "approval_decisions": self.list_approvals(run_id),
            "final_status": run.get("status"),
            "stop_reason": run.get("stop_reason"),
        }

    def export_report(self, run_id: str, *, fmt: str = "markdown") -> str:
        exporter = ReportExporter(self.report_payload(run_id))
        if fmt == "json":
            return exporter.to_json()
        if fmt in {"markdown", "md"}:
            return exporter.to_markdown()
        raise ValueError(f"Unsupported report format: {fmt}")

    def credential_service(self) -> CredentialService:
        return CredentialService(env_file=self.repo_path / ".env")

    def _require_run(self, run_id: str) -> dict[str, Any]:
        run = self.storage.get_task_run(run_id)
        if run is None:
            raise ValueError(f"Unknown task run: {run_id}")
        return run

    def _context_item_payload(self, item_id: str) -> dict[str, Any]:
        item = self.storage.get_context_item(item_id)
        if item is None:
            return {"id": item_id, "missing": True}
        if item.get("metadata"):
            try:
                item["metadata"] = json.loads(item["metadata"])
            except json.JSONDecodeError:
                item["metadata_raw"] = item["metadata"]
                item["metadata_parse_error"] = True
                item["metadata"] = {}
        else:
            item["metadata"] = {}
        return item


def json_dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def memory_kind_values() -> list[str]:
    return [kind.value for kind in MemoryKind]
