import sqlite3

import pytest
from fastapi import HTTPException
from typer.testing import CliRunner

from harness.api import create_app
from harness.cli import app
from harness.llm import MockLLM
from harness.service import CoreService


def _endpoint(app, path, method):
    for route in app.routes:
        if getattr(route, "path", None) == path and method in getattr(route, "methods", set()):
            return route.endpoint
    raise AssertionError(f"missing route {method} {path}")


def test_cli_run_with_mock_llm_creates_task_run_and_context_trace(tmp_path):
    repo = tmp_path / "sample-repo"
    repo.mkdir()
    (repo / "calculator.py").write_text(
        "def add(left, right):\n    return left + right\n",
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        app,
        [
            "run",
            "Update calculator.py",
            "--repo",
            str(repo),
            "--mock-llm",
            "--max-rounds",
            "1",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "task_run_id" in result.output

    conn = sqlite3.connect(repo / ".harness" / "harness.db")
    try:
        run_count = conn.execute("SELECT COUNT(*) FROM task_run").fetchone()[0]
        package_count = conn.execute("SELECT COUNT(*) FROM context_package").fetchone()[0]
    finally:
        conn.close()

    assert run_count == 1
    assert package_count == 1


def test_core_service_exposes_run_status_memory_and_report(tmp_path):
    repo = tmp_path / "sample-repo"
    repo.mkdir()
    (repo / "README.md").write_text("hello service\n", encoding="utf-8")
    service = CoreService(repo, llm=MockLLM([]))
    task = service.create_task("Read README", "Read README with MockLLM")

    run = service.run_task(task.id, max_rounds=1)

    status = service.get_status(run.id)
    assert status["run"]["id"] == run.id
    assert status["task"]["id"] == task.id
    assert service.list_context(run.id)
    memory = service.record_memory(kind="task_summary", content="Service boundary works")
    assert memory["content"] == "Service boundary works"
    assert "Service boundary works" in service.list_memory()[0]["content"]
    report = service.export_report(run.id, fmt="json")
    assert '"task_request"' in report


def test_core_service_context_trace_includes_item_details_and_selection_reason(tmp_path):
    repo = tmp_path / "context-repo"
    repo.mkdir()
    (repo / "calculator.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    service = CoreService(repo, llm=MockLLM([]))
    task = service.create_task("Update calculator", "Update calculator.py")

    run = service.run_task(task.id, max_rounds=1)

    packages = service.list_context(run.id)
    assert packages
    first_item = packages[0]["items"][0]
    assert first_item["kind"]
    assert first_item["summary"]
    assert "selection_reason" in first_item["metadata"]


def test_api_report_endpoint_exports_redacted_json_through_http(tmp_path):
    repo = tmp_path / "report-api-repo"
    repo.mkdir()
    (repo / "app.py").write_text("print('api')\n", encoding="utf-8")
    app = create_app(CoreService(repo, llm=MockLLM([])))

    task = _endpoint(app, "/tasks", "POST")(
        {"title": "Update app", "description": "Update app.py"}
    )
    run = _endpoint(app, "/tasks/{task_id}/runs", "POST")(task["id"], {"max_rounds": 1})
    response = _endpoint(app, "/runs/{run_id}/report", "GET")(run["id"], format="json")

    assert "content" in response
    assert '"selected_context"' in response["content"]


def test_cli_auth_set_prompts_for_hidden_key_instead_of_argument(monkeypatch):
    captured = {}

    class FakeCredentialService:
        def set(self, api_key):
            captured["api_key"] = api_key

    monkeypatch.setattr("harness.cli.CredentialService", lambda: FakeCredentialService())

    result = CliRunner().invoke(app, ["auth", "set"], input="secret-value\n")

    assert result.exit_code == 0, result.output
    assert captured["api_key"] == "secret-value"
    assert "secret-value" not in result.output


def test_cli_auth_set_rejects_api_key_command_line_value(monkeypatch):
    captured = {}

    class FakeCredentialService:
        def set(self, api_key):
            captured["api_key"] = api_key

    monkeypatch.setattr("harness.cli.CredentialService", lambda: FakeCredentialService())

    result = CliRunner().invoke(app, ["auth", "set", "--api-key", "secret-value"])

    assert result.exit_code != 0
    assert "secret-value" not in captured.values()


def test_cli_auth_status_uses_repo_env_fallback(tmp_path):
    repo = tmp_path / "auth-repo"
    repo.mkdir()
    (repo / ".env").write_text("HARNESS_API_KEY=dev-key\n", encoding="utf-8")

    result = CliRunner().invoke(app, ["auth", "status", "--repo", str(repo)])

    assert result.exit_code == 0, result.output
    assert '".env"' in result.output
    assert "dev-key" not in result.output


def test_cli_run_without_mock_llm_fails_until_real_client_is_configured(tmp_path):
    repo = tmp_path / "real-llm-repo"
    repo.mkdir()

    result = CliRunner().invoke(app, ["run", "Update app", "--repo", str(repo)])

    assert result.exit_code != 0
    assert "Use --mock-llm" in result.output


def test_core_service_requires_explicit_llm_to_run(tmp_path):
    repo = tmp_path / "service-real-llm-repo"
    repo.mkdir()
    service = CoreService(repo)
    task = service.create_task("Update app", "Update app")

    with pytest.raises(ValueError, match="LLM client"):
        service.run_task(task.id, max_rounds=1)


def test_default_api_run_rejects_without_explicit_llm(tmp_path):
    repo = tmp_path / "api-real-llm-repo"
    repo.mkdir()
    app = create_app(repo_path=repo)
    task = _endpoint(app, "/tasks", "POST")({"title": "Update app"})

    with pytest.raises(HTTPException) as exc:
        _endpoint(app, "/tasks/{task_id}/runs", "POST")(task["id"], {"max_rounds": 1})

    assert exc.value.status_code == 400
    assert "LLM client" in exc.value.detail


def test_context_trace_preserves_metadata_parse_errors(tmp_path):
    repo = tmp_path / "bad-metadata-repo"
    repo.mkdir()
    (repo / "app.py").write_text("print('hello')\n", encoding="utf-8")
    service = CoreService(repo, llm=MockLLM([]))
    task = service.create_task("Update app", "Update app.py")
    run = service.run_task(task.id, max_rounds=1)
    package = service.list_context(run.id)[0]
    item_id = package["items"][0]["id"]
    service.storage._update("context_item", "id", item_id, metadata="{not-json")

    item = service.list_context(run.id)[0]["items"][0]

    assert item["metadata_parse_error"]
    assert item["metadata_raw"] == "{not-json"


def test_api_submits_task_runs_and_exposes_traces_and_report(tmp_path):
    repo = tmp_path / "api-repo"
    repo.mkdir()
    (repo / "app.py").write_text("print('api')\n", encoding="utf-8")
    app = create_app(CoreService(repo, llm=MockLLM([])))

    task = _endpoint(app, "/tasks", "POST")(
        {"title": "Update app", "description": "Update app.py"}
    )
    task_id = task["id"]

    run = _endpoint(app, "/tasks/{task_id}/runs", "POST")(task_id, {"max_rounds": 1})
    run_id = run["id"]

    assert _endpoint(app, "/runs/{run_id}", "GET")(run_id)["run"]["id"] == run_id
    assert _endpoint(app, "/runs/{run_id}/context", "GET")(run_id)
    assert _endpoint(app, "/runs/{run_id}/actions", "GET")(run_id)
    assert _endpoint(app, "/runs/{run_id}/feedback", "GET")(run_id)
    assert "content" in _endpoint(app, "/runs/{run_id}/report", "GET")(run_id)


def test_api_approval_decisions_update_pending_request(tmp_path):
    repo = tmp_path / "approval-repo"
    repo.mkdir()
    service = CoreService(
        repo,
        llm=MockLLM([
            '{"thought_summary":"needs approval","action":"run_command",'
            '"args":{"command":"python script.py"}}'
        ]),
    )
    app = create_app(service)
    task_id = _endpoint(app, "/tasks", "POST")({"title": "Run command"})["id"]
    run_id = _endpoint(app, "/tasks/{task_id}/runs", "POST")(task_id, {"max_rounds": 1})["id"]
    approvals = _endpoint(app, "/runs/{run_id}/approvals", "GET")(run_id)

    approval_id = approvals[0]["id"]
    approved = _endpoint(app, "/approvals/{approval_id}/approve", "POST")(
        approval_id, {"decided_by": "tester"}
    )
    rejected = _endpoint(app, "/approvals/{approval_id}/reject", "POST")(
        approval_id, {"decided_by": "tester"}
    )

    assert approved["status"] == "approved"
    assert rejected["status"] == "rejected"


def test_webui_run_page_renders_observability_and_approval_forms(tmp_path):
    from harness.webui import include_webui

    repo = tmp_path / "webui-repo"
    repo.mkdir()
    (repo / "script.py").write_text("print('ok')\n", encoding="utf-8")
    service = CoreService(
        repo,
        llm=MockLLM([
            '{"thought_summary":"needs approval","action":"run_command",'
            '"args":{"command":"python script.py"}}'
        ]),
    )
    api = create_app(service)
    include_webui(api, service)
    task_id = _endpoint(api, "/tasks", "POST")({"title": "Run command"})["id"]
    run_id = _endpoint(api, "/tasks/{task_id}/runs", "POST")(task_id, {"max_rounds": 1})["id"]

    response = _endpoint(api, "/ui/runs/{run_id}", "GET")(run_id)
    html = response.body.decode("utf-8")

    assert "Harness WebUI" in html
    assert "运行详情" in html
    assert "运行状态" in html
    assert "已选上下文" in html
    assert "动作轨迹" in html
    assert "反馈" in html
    assert "待审批" in html
    assert "报告" in html
    assert 'action="/ui/approvals/' in html
    assert "批准" in html
    assert "拒绝" in html
    assert "python script.py" in html
