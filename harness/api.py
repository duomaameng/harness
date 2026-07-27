"""FastAPI adapter for the harness core service."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException

from harness.domain import ApprovalStatus
from harness.repository_registry import RepositoryRegistry
from harness.service import CoreService


def create_app(
    service: CoreService | None = None,
    *,
    repo_path: str | Path = ".",
    registry: RepositoryRegistry | None = None,
) -> FastAPI:
    core = service or CoreService(repo_path)
    active_registry = registry or RepositoryRegistry(
        Path(os.environ.get("APPDATA", Path.home() / ".config")) / "harness"
    )
    if not any(
        item["path"] == str(core.repo_path.resolve()) for item in active_registry.list()
    ):
        active_registry.register(core.repo_path)
    app = FastAPI(title="Context-Aware Harness API")

    @app.post("/tasks")
    def create_task(payload: dict[str, Any]) -> dict[str, Any]:
        try:
            task = core.create_task(
                str(payload.get("title") or payload.get("description") or "Untitled task"),
                str(payload.get("description") or ""),
            )
            return vars(task)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/tasks/{task_id}/runs")
    def run_task(task_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            payload = payload or {}
            run = core.run_task(task_id, max_rounds=int(payload.get("max_rounds", 6)))
            return vars(run)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/runs/{run_id}")
    def get_run(run_id: str) -> dict[str, Any]:
        return _wrap(lambda: core.get_status(run_id))

    @app.get("/runs/{run_id}/context")
    def get_context(run_id: str) -> list[dict[str, Any]]:
        return _wrap(lambda: core.list_context(run_id))

    @app.get("/runs/{run_id}/actions")
    def get_actions(run_id: str) -> list[dict[str, Any]]:
        return _wrap(lambda: core.list_actions(run_id))

    @app.get("/runs/{run_id}/feedback")
    def get_feedback(run_id: str) -> list[dict[str, Any]]:
        return _wrap(lambda: core.list_feedback(run_id))

    @app.get("/runs/{run_id}/approvals")
    def get_approvals(run_id: str) -> list[dict[str, Any]]:
        return _wrap(lambda: core.list_approvals(run_id))

    @app.post("/approvals/{approval_id}/approve")
    def approve(approval_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        decided_by = (payload or {}).get("decided_by", "api")
        return _wrap(
            lambda: core.decide_approval(
                approval_id, ApprovalStatus.APPROVED.value, str(decided_by)
            )
        )

    @app.post("/approvals/{approval_id}/reject")
    def reject(approval_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        decided_by = (payload or {}).get("decided_by", "api")
        return _wrap(
            lambda: core.decide_approval(
                approval_id, ApprovalStatus.REJECTED.value, str(decided_by)
            )
        )

    @app.get("/runs/{run_id}/report")
    def get_report(run_id: str, format: str = "markdown") -> dict[str, Any] | dict[str, str]:
        if format == "json":
            return _wrap(lambda: core.report_payload(run_id))
        return _wrap(lambda: {"content": core.export_report(run_id, fmt=format)})

    app.state.core_service = core
    app.state.repository_registry = active_registry
    from harness.webui import include_webui

    include_webui(app, core, registry=active_registry)
    return app


def _wrap(call):
    try:
        return call()
    except ValueError as exc:
        status_code = 409 if "already decided" in str(exc) else 404
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


app = create_app()
