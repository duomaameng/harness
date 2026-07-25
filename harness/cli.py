"""Typer command line interface for the harness."""

from __future__ import annotations

from pathlib import Path

import typer

from harness.auth import CredentialService
from harness.domain import ApprovalStatus, MemoryKind
from harness.llm import MockLLM
from harness.service import CoreService, json_dumps

app = typer.Typer(help="Context-aware coding agent harness.")
auth_app = typer.Typer(help="Credential commands.")
app.add_typer(auth_app, name="auth")


def _service(repo: Path, *, mock_llm: bool = False) -> CoreService:
    llm = MockLLM([]) if mock_llm else None
    return CoreService(repo, llm=llm)


@app.command("init")
def init(repo: Path = typer.Option(Path("."), "--repo", "-r")) -> None:
    service = _service(repo)
    typer.echo(json_dumps({"repo": str(service.repo_path), "harness_dir": str(service.storage.harness_dir)}))


@app.command("run")
def run(
    task: str = typer.Argument(...),
    repo: Path = typer.Option(Path("."), "--repo", "-r"),
    mock_llm: bool = typer.Option(False, "--mock-llm"),
    max_rounds: int = typer.Option(6, "--max-rounds"),
) -> None:
    service = _service(repo, mock_llm=mock_llm)
    created = service.create_task(task, task)
    run_result = service.run_task(created.id, max_rounds=max_rounds)
    typer.echo(json_dumps({
        "task_id": created.id,
        "task_run_id": run_result.id,
        "status": run_result.status,
        "stop_reason": run_result.stop_reason,
    }))


@app.command("status")
def status(
    run_id: str = typer.Argument(...),
    repo: Path = typer.Option(Path("."), "--repo", "-r"),
) -> None:
    typer.echo(json_dumps(_service(repo).get_status(run_id)))


@auth_app.command("set")
def auth_set() -> None:
    api_key = typer.prompt("API key", hide_input=True)
    CredentialService().set(api_key)
    typer.echo(json_dumps({"configured": True, "source": "keyring"}))


@auth_app.command("status")
def auth_status(repo: Path = typer.Option(Path("."), "--repo", "-r")) -> None:
    typer.echo(json_dumps(_service(repo).credential_service().status()))


@auth_app.command("clear")
def auth_clear(repo: Path = typer.Option(Path("."), "--repo", "-r")) -> None:
    typer.echo(json_dumps({"cleared": _service(repo).credential_service().clear()}))


@app.command("memory")
def memory(
    content: str | None = typer.Argument(None),
    kind: str = typer.Option(MemoryKind.TASK_SUMMARY.value, "--kind"),
    repo: Path = typer.Option(Path("."), "--repo", "-r"),
) -> None:
    service = _service(repo)
    if content:
        typer.echo(json_dumps(service.record_memory(kind=kind, content=content)))
    else:
        typer.echo(json_dumps(service.list_memory(kind=kind)))


@app.command("export")
def export(
    run_id: str = typer.Argument(...),
    repo: Path = typer.Option(Path("."), "--repo", "-r"),
    fmt: str = typer.Option("markdown", "--format"),
) -> None:
    typer.echo(_service(repo).export_report(run_id, fmt=fmt))


@app.command("approve")
def approve(
    approval_id: str = typer.Argument(...),
    repo: Path = typer.Option(Path("."), "--repo", "-r"),
    decided_by: str = typer.Option("cli", "--decided-by"),
) -> None:
    typer.echo(json_dumps(
        _service(repo).decide_approval(
            approval_id, ApprovalStatus.APPROVED.value, decided_by
        )
    ))


@app.command("reject")
def reject(
    approval_id: str = typer.Argument(...),
    repo: Path = typer.Option(Path("."), "--repo", "-r"),
    decided_by: str = typer.Option("cli", "--decided-by"),
) -> None:
    typer.echo(json_dumps(
        _service(repo).decide_approval(
            approval_id, ApprovalStatus.REJECTED.value, decided_by
        )
    ))
