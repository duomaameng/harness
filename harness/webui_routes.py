"""HTTP routes for the Harness WebUI."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from harness.domain import ApprovalStatus
from harness.repository_registry import RepositoryRegistry
from harness.service import CoreService
from harness.webui_services import WebUIServiceProvider


def include_webui(
    app: FastAPI,
    service: CoreService | None = None,
    *,
    repo_path: str | Path = ".",
    registry: RepositoryRegistry | None = None,
    service_factory: Callable[[Path], CoreService] | None = None,
) -> FastAPI:
    """Attach the workbench, run detail, repository, and approval routes."""

    if getattr(app.state, "webui_included", False):
        return app

    core = service or getattr(app.state, "core_service", None) or CoreService(repo_path)
    app.state.core_service = core
    provider = WebUIServiceProvider(core, service_factory=service_factory)
    app.state.webui_included = True

    def current_core() -> CoreService:
        if registry is None:
            return core
        repository = registry.current()
        if repository is None:
            raise HTTPException(status_code=400, detail="Select or add a repository first")
        return provider.for_repository(repository["path"])

    def required_registry() -> RepositoryRegistry:
        if registry is None:
            raise HTTPException(status_code=400, detail="Repository registry is not configured")
        return registry

    def mark_current_repository_used() -> None:
        if registry is None:
            return
        repository = registry.current()
        if repository is not None:
            registry.mark_used(repository["id"])

    @app.get("/", response_class=HTMLResponse)
    def workbench() -> HTMLResponse:
        from harness.webui import _render_workbench

        active = registry.current() if registry is not None else None
        return HTMLResponse(
            _render_workbench(
                current_core() if registry is None or active is not None else None,
                repositories=registry.list() if registry is not None else None,
                current_repository_id=active["id"] if active is not None else None,
            )
        )

    @app.get("/ui", response_class=HTMLResponse)
    def workbench_alias() -> HTMLResponse:
        return workbench()

    @app.post("/ui/repositories")
    def register_repository(payload: dict[str, Any]) -> dict[str, str]:
        try:
            return required_registry().register(str(payload.get("path") or ""))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/ui/repositories/pick", response_model=None)
    def pick_repository() -> dict[str, str] | Response:
        directory = _choose_repository_directory()
        if directory is None:
            return Response(status_code=204)
        try:
            return required_registry().register_or_select(directory)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/ui/repositories/{repository_id}/select")
    def select_repository(repository_id: str) -> RedirectResponse:
        try:
            required_registry().select(repository_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return RedirectResponse("/", status_code=303)

    @app.post("/ui/repositories/{repository_id}/rename")
    def rename_repository(repository_id: str, payload: dict[str, Any]) -> dict[str, str]:
        try:
            return required_registry().rename(repository_id, str(payload.get("name") or ""))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/ui/repositories/{repository_id}/delete")
    def delete_repository(repository_id: str) -> RedirectResponse:
        if required_registry().remove(repository_id) is None:
            raise HTTPException(status_code=404, detail=f"Unknown repository id: {repository_id}")
        return RedirectResponse("/", status_code=303)

    @app.post("/ui/tasks")
    def create_task(payload: dict[str, Any]) -> dict[str, Any]:
        task = current_core().create_task(
            _required_title(payload), str(payload.get("description") or "")
        )
        mark_current_repository_used()
        return {"task_id": task.id, "detail_url": None}

    @app.post("/ui/tasks/run")
    def create_and_run_task(payload: dict[str, Any]) -> dict[str, Any]:
        active_core = current_core()
        task = active_core.create_task(
            _required_title(payload), str(payload.get("description") or "")
        )
        run = active_core.run_task(task.id, max_rounds=_max_rounds(payload))
        mark_current_repository_used()
        return {"task_id": task.id, "run_id": run.id, "detail_url": f"/ui/runs/{run.id}"}

    @app.get("/ui/runs/{run_id}", response_class=HTMLResponse)
    def run_detail(run_id: str) -> HTMLResponse:
        from harness.webui import _render_run_detail

        return HTMLResponse(_render_run_detail(current_core(), run_id))

    @app.post("/ui/approvals/{approval_id}/approve")
    def approve(approval_id: str) -> RedirectResponse:
        approval = current_core().decide_approval(
            approval_id,
            ApprovalStatus.APPROVED.value,
            decided_by="webui",
        )
        return RedirectResponse(f"/ui/runs/{approval.get('task_run_id')}", status_code=303)

    @app.post("/ui/approvals/{approval_id}/reject")
    def reject(approval_id: str) -> RedirectResponse:
        approval = current_core().decide_approval(
            approval_id,
            ApprovalStatus.REJECTED.value,
            decided_by="webui",
        )
        return RedirectResponse(f"/ui/runs/{approval.get('task_run_id')}", status_code=303)

    return app


def _required_title(payload: dict[str, Any]) -> str:
    title = str(payload.get("title") or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="Task title is required")
    return title


def _max_rounds(payload: dict[str, Any]) -> int:
    try:
        max_rounds = int(payload.get("max_rounds") or 1)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="max_rounds must be an integer") from exc
    if max_rounds < 1:
        raise HTTPException(status_code=400, detail="max_rounds must be at least 1")
    return max_rounds


def _choose_repository_directory() -> Path | None:
    """Open the local Windows directory picker and return the selected folder."""
    try:
        from tkinter import Tk, filedialog
    except ImportError as exc:
        raise HTTPException(status_code=501, detail="Native directory picker is unavailable") from exc

    root = Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        selected = filedialog.askdirectory(title="Select repository folder", mustexist=True)
    finally:
        root.destroy()
    return Path(selected) if selected else None


__all__ = ["include_webui"]
