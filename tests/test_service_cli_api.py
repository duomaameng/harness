import json
import sqlite3

import pytest
from fastapi import HTTPException
from typer.testing import CliRunner

from harness.api import create_app
from harness.cli import app
from harness.domain import Action, ToolResult
from harness.llm import MockLLM, OpenAICompatibleClient
from harness.service import CoreService


def test_repository_registry_persists_registration_selection_rename_and_safe_removal(tmp_path):
    from harness.repository_registry import RepositoryRegistry

    config_dir = tmp_path / "application-config"
    first_repository_path = tmp_path / "first-repository"
    second_repository_path = tmp_path / "second-repository"
    first_repository_path.mkdir()
    second_repository_path.mkdir()

    registry = RepositoryRegistry(config_dir)
    first = registry.register(first_repository_path)
    second = registry.register(second_repository_path)

    assert first == {
        "id": first["id"],
        "path": str(first_repository_path.resolve()),
        "name": "first-repository",
    }
    assert registry.current() == second
    assert registry.select(first["id"]) == first

    renamed = registry.rename(first["id"], "Primary repository")

    assert renamed == {
        "id": first["id"],
        "path": str(first_repository_path.resolve()),
        "name": "Primary repository",
    }
    persisted_registry = RepositoryRegistry(config_dir)
    assert persisted_registry.list() == [renamed, second]
    assert persisted_registry.current() == renamed

    assert persisted_registry.remove(first["id"]) == renamed
    assert first_repository_path.is_dir()
    assert persisted_registry.current() == second
    assert RepositoryRegistry(config_dir).list() == [second]


def test_repository_registry_rejects_valid_json_with_incomplete_schema(tmp_path):
    from harness.repository_registry import RepositoryRegistry

    config_dir = tmp_path / "application-config"
    config_dir.mkdir()
    registry_path = config_dir / "repositories.json"

    registry_path.write_text('{"repositories": []}', encoding="utf-8")
    with pytest.raises(ValueError, match="repositories.json"):
        RepositoryRegistry(config_dir).current()

    registry_path.write_text(
        '{"repositories": [{"id": "repository-1", "name": "Missing path"}], '
        '"current_repository_id": null}',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="repositories.json"):
        RepositoryRegistry(config_dir).list()


def _endpoint(app, path, method):
    for route in app.routes:
        if getattr(route, "path", None) == path and method in getattr(route, "methods", set()):
            return route.endpoint
    raise AssertionError(f"missing route {method} {path}")


def test_webui_repository_switches_task_service_and_isolates_tasks(tmp_path):
    from harness.repository_registry import RepositoryRegistry

    config_dir = tmp_path / "application-config"
    first_repository_path = tmp_path / "first-repository"
    second_repository_path = tmp_path / "second-repository"
    first_repository_path.mkdir()
    second_repository_path.mkdir()
    registry = RepositoryRegistry(config_dir)
    first = registry.register(first_repository_path)
    service = CoreService(first_repository_path, llm=MockLLM([]))
    api = create_app(service, registry=registry)
    second = _endpoint(api, "/ui/repositories", "POST")({"path": str(second_repository_path)})

    task = _endpoint(api, "/ui/tasks", "POST")({"title": "Only in second"})
    html = _endpoint(api, "/", "GET")().body.decode("utf-8")

    assert registry.current() == second
    assert second["name"] in html
    assert "Only in second" in html
    assert CoreService(first["path"]).list_tasks() == []
    assert task["task_id"]


def test_webui_repository_rename_and_delete_routes_update_registry(tmp_path):
    from harness.repository_registry import RepositoryRegistry

    repository_path = tmp_path / "repository"
    repository_path.mkdir()
    registry = RepositoryRegistry(tmp_path / "application-config")
    repository = registry.register(repository_path)
    api = create_app(CoreService(repository_path, llm=MockLLM([])), registry=registry)

    renamed = _endpoint(api, "/ui/repositories/{repository_id}/rename", "POST")(
        repository["id"], {"name": "Renamed repository"}
    )
    response = _endpoint(api, "/ui/repositories/{repository_id}/delete", "POST")(
        repository["id"]
    )

    assert renamed["name"] == "Renamed repository"
    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert registry.list() == []


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

    assert "selected_context" in response


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


def test_cli_run_without_mock_llm_uses_offline_mock_default(tmp_path):
    repo = tmp_path / "real-llm-repo"
    repo.mkdir()

    result = CliRunner().invoke(app, ["run", "Update app", "--repo", str(repo)])

    assert result.exit_code == 0, result.output
    assert "task_run_id" in result.output


def test_core_service_uses_offline_mock_default(tmp_path):
    repo = tmp_path / "service-real-llm-repo"
    repo.mkdir()
    service = CoreService(repo)
    task = service.create_task("Update app", "Update app")

    run = service.run_task(task.id, max_rounds=1)

    assert run.status in {"succeeded", "stopped"}


def test_core_service_uses_openai_compatible_client_when_credentials_are_configured(tmp_path, monkeypatch):
    repo = tmp_path / "configured-real-llm-repo"
    repo.mkdir()
    (repo / ".env").write_text("HARNESS_API_KEY=sk-dotenv-secret\n", encoding="utf-8")
    monkeypatch.setenv("HARNESS_LLM_BASE_URL", "https://api.example.test/v1")
    monkeypatch.setenv("HARNESS_LLM_MODEL", "example-model")

    service = CoreService(repo)

    assert isinstance(service.llm, OpenAICompatibleClient)
    assert service.llm.base_url == "https://api.example.test/v1"
    assert service.llm.model == "example-model"
    assert service.llm.api_key == "sk-dotenv-secret"


def test_core_service_defaults_configured_provider_to_deepseek_chat_model(tmp_path, monkeypatch):
    repo = tmp_path / "default-real-llm-repo"
    repo.mkdir()
    (repo / ".env").write_text("DEEPSEEK_API_KEY=deepseek-secret\n", encoding="utf-8")
    monkeypatch.delenv("HARNESS_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("HARNESS_LLM_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)

    service = CoreService(repo)

    assert isinstance(service.llm, OpenAICompatibleClient)
    assert service.llm.base_url == "https://api.deepseek.com"
    assert service.llm.model == "deepseek-v4-pro"
    assert service.llm.api_key == "deepseek-secret"


def test_default_api_run_rejects_without_explicit_llm(tmp_path):
    repo = tmp_path / "api-real-llm-repo"
    repo.mkdir()
    app = create_app(repo_path=repo)
    task = _endpoint(app, "/tasks", "POST")({"title": "Update app"})

    run = _endpoint(app, "/tasks/{task_id}/runs", "POST")(task["id"], {"max_rounds": 1})

    assert run["status"] in {"succeeded", "stopped"}


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
    assert isinstance(_endpoint(app, "/runs/{run_id}/feedback", "GET")(run_id), list)
    assert "content" in _endpoint(app, "/runs/{run_id}/report", "GET")(run_id)


def test_api_approval_decisions_update_pending_request(tmp_path):
    approve_repo = tmp_path / "approval-approve-repo"
    reject_repo = tmp_path / "approval-reject-repo"
    approve_repo.mkdir()
    reject_repo.mkdir()
    approve_service = CoreService(
        approve_repo,
        llm=MockLLM([
            '{"thought_summary":"needs approval","action":"run_command",'
            '"args":{"command":"python script.py"}}'
        ]),
    )
    reject_service = CoreService(
        reject_repo,
        llm=MockLLM([
            '{"thought_summary":"needs approval","action":"run_command",'
            '"args":{"command":"python script.py"}}'
        ]),
    )
    approve_app = create_app(approve_service)
    reject_app = create_app(reject_service)
    approve_task_id = _endpoint(approve_app, "/tasks", "POST")({"title": "Run command"})["id"]
    reject_task_id = _endpoint(reject_app, "/tasks", "POST")({"title": "Run command"})["id"]
    approve_run_id = _endpoint(approve_app, "/tasks/{task_id}/runs", "POST")(
        approve_task_id, {"max_rounds": 1}
    )["id"]
    reject_run_id = _endpoint(reject_app, "/tasks/{task_id}/runs", "POST")(
        reject_task_id, {"max_rounds": 1}
    )["id"]
    approve_id = _endpoint(approve_app, "/runs/{run_id}/approvals", "GET")(approve_run_id)[0]["id"]
    reject_id = _endpoint(reject_app, "/runs/{run_id}/approvals", "GET")(reject_run_id)[0]["id"]

    approved = _endpoint(approve_app, "/approvals/{approval_id}/approve", "POST")(
        approve_id, {"decided_by": "tester"}
    )
    rejected = _endpoint(reject_app, "/approvals/{approval_id}/reject", "POST")(
        reject_id, {"decided_by": "tester"}
    )

    assert approved["status"] == "approved"
    assert rejected["status"] == "rejected"


def test_rejected_approval_creates_guardrail_feedback(tmp_path):
    repo = tmp_path / "approval-feedback-repo"
    repo.mkdir()
    service = CoreService(
        repo,
        llm=MockLLM([
            '{"thought_summary":"needs approval","action":"run_command",'
            '"args":{"command":"npm install left-pad"}}'
        ]),
    )
    app = create_app(service)
    task_id = _endpoint(app, "/tasks", "POST")({"title": "Install dependency"})["id"]
    run_id = _endpoint(app, "/tasks/{task_id}/runs", "POST")(task_id, {"max_rounds": 1})["id"]
    approval_id = _endpoint(app, "/runs/{run_id}/approvals", "GET")(run_id)[0]["id"]

    _endpoint(app, "/approvals/{approval_id}/reject", "POST")(
        approval_id, {"decided_by": "tester"}
    )
    feedback = _endpoint(app, "/runs/{run_id}/feedback", "GET")(run_id)

    assert feedback
    assert feedback[0]["source"] == "guardrail"
    assert "rejected" in feedback[0]["summary"].lower()


def test_approval_can_only_be_decided_once(tmp_path):
    repo = tmp_path / "approval-once-repo"
    repo.mkdir()
    service = CoreService(
        repo,
        llm=MockLLM([
            '{"thought_summary":"needs approval","action":"run_command",'
            '"args":{"command":"npm install left-pad"}}'
        ]),
    )
    app = create_app(service)
    task_id = _endpoint(app, "/tasks", "POST")({"title": "Install dependency"})["id"]
    run_id = _endpoint(app, "/tasks/{task_id}/runs", "POST")(task_id, {"max_rounds": 1})["id"]
    approval_id = _endpoint(app, "/runs/{run_id}/approvals", "GET")(run_id)[0]["id"]
    _endpoint(app, "/approvals/{approval_id}/approve", "POST")(
        approval_id, {"decided_by": "tester"}
    )

    with pytest.raises(HTTPException) as exc:
        _endpoint(app, "/approvals/{approval_id}/reject", "POST")(
            approval_id, {"decided_by": "tester"}
        )

    assert exc.value.status_code == 409


def test_json_report_endpoint_returns_structured_report_object(tmp_path):
    repo = tmp_path / "structured-report-repo"
    repo.mkdir()
    (repo / "app.py").write_text("print('api')\n", encoding="utf-8")
    app = create_app(CoreService(repo, llm=MockLLM([])))
    task_id = _endpoint(app, "/tasks", "POST")({"title": "Update app"})["id"]
    run_id = _endpoint(app, "/tasks/{task_id}/runs", "POST")(task_id, {"max_rounds": 1})["id"]

    response = _endpoint(app, "/runs/{run_id}/report", "GET")(run_id, format="json")

    assert "task_request" in response
    assert "selected_context" in response
    assert "content" not in response


def test_report_payload_includes_top_level_changed_files(tmp_path):
    repo = tmp_path / "changed-files-report-repo"
    repo.mkdir()
    service = CoreService(repo)
    task = service.create_task("Update app", "Update app")
    run = service.run_task(task.id, max_rounds=1)
    action = service.storage.create_action(Action(
        task_run_id=run.id,
        action_type="write_file",
        args_json=json.dumps({"path": "app.py", "content": "print('ok')"}),
    ))
    service.storage.create_tool_result(ToolResult(
        action_id=action.id,
        changed_files=["app.py"],
    ))

    payload = service.report_payload(run.id)

    assert payload["changed_files"] == ["app.py"]


def test_approval_action_args_are_redacted_for_api_and_webui(tmp_path):
    from harness.webui import include_webui

    repo = tmp_path / "approval-secret-repo"
    repo.mkdir()
    secret = "sk-test-secret"
    service = CoreService(
        repo,
        llm=MockLLM([
            '{"thought_summary":"needs approval","action":"run_command",'
            f'"args":{{"command":"npm install left-pad --token {secret}"}}}}'
        ]),
    )
    api = create_app(service)
    include_webui(api, service)
    task_id = _endpoint(api, "/tasks", "POST")({"title": "Install dependency"})["id"]
    run_id = _endpoint(api, "/tasks/{task_id}/runs", "POST")(task_id, {"max_rounds": 1})["id"]

    approval = _endpoint(api, "/runs/{run_id}/approvals", "GET")(run_id)[0]
    html = _endpoint(api, "/ui/runs/{run_id}", "GET")(run_id).body.decode("utf-8")

    assert secret not in json.dumps(approval)
    assert secret not in html
    assert "[REDACTED]" in json.dumps(approval)
    assert "[REDACTED]" in html


def test_webui_root_renders_integrated_workbench_with_existing_runs(tmp_path):
    repo = tmp_path / "webui-workbench-repo"
    repo.mkdir()
    service = CoreService(repo, llm=MockLLM([]))
    api = create_app(service)
    task = service.create_task("Update docs", "Update README with startup notes")
    run = service.run_task(task.id, max_rounds=1)

    response = _endpoint(api, "/", "GET")()
    html = response.body.decode("utf-8")

    assert "Harness Workbench" in html
    assert "新建任务" in html
    assert "Update docs" in html
    assert f"/ui/runs/{run.id}" in html
    assert str(repo) in html


def test_webui_sidebar_task_links_to_its_run_detail(tmp_path):
    repo = tmp_path / "webui-sidebar-task-link-repo"
    repo.mkdir()
    service = CoreService(repo, llm=MockLLM([]))
    api = create_app(service)
    task = service.create_task("Reopen this task", "Open its prior run from the sidebar")
    run = service.run_task(task.id, max_rounds=1)

    html = _endpoint(api, "/", "GET")().body.decode("utf-8")

    assert (
        f'<a class="task-item" href="/ui/runs/{run.id}">'
        '<span class="badge">succeeded</span>'
        '<h5 class="task-item-title">Reopen this task</h5>'
        "</a>"
    ) in html


def test_webui_create_and_run_endpoint_returns_detail_url(tmp_path):
    repo = tmp_path / "webui-create-run-repo"
    repo.mkdir()
    service = CoreService(repo, llm=MockLLM([]))
    api = create_app(service)

    result = _endpoint(api, "/ui/tasks/run", "POST")({
        "title": "Run from workbench",
        "description": "Create through WebUI form",
        "max_rounds": 1,
    })

    assert result["task_id"]
    assert result["run_id"]
    assert result["detail_url"] == f"/ui/runs/{result['run_id']}"
    assert service.get_status(result["run_id"])["task"]["title"] == "Run from workbench"


def test_webui_task_endpoints_return_bad_request_for_invalid_input(tmp_path):
    repo = tmp_path / "webui-invalid-input-repo"
    repo.mkdir()
    service = CoreService(repo, llm=MockLLM([]))
    api = create_app(service)

    with pytest.raises(HTTPException) as missing_title:
        _endpoint(api, "/ui/tasks", "POST")({"title": "   "})

    with pytest.raises(HTTPException) as bad_rounds:
        _endpoint(api, "/ui/tasks/run", "POST")({
            "title": "Run from workbench",
            "max_rounds": "bad",
        })

    assert missing_title.value.status_code == 400
    assert bad_rounds.value.status_code == 400


def test_webui_workbench_matches_design_prototype_structure(tmp_path):
    repo = tmp_path / "prototype-workbench-repo"
    repo.mkdir()
    service = CoreService(repo, llm=MockLLM([]))
    api = create_app(service)
    task = service.create_task("Prototype task", "Render the prototype structure")
    run = service.run_task(task.id, max_rounds=1)

    html = _endpoint(api, "/", "GET")().body.decode("utf-8")

    assert 'class="dashboard-workbench"' in html
    assert 'id="view-workbench"' in html
    assert 'id="view-detail"' in html
    assert 'class="repo-list"' in html
    assert 'class="repo-group active"' in html
    assert 'class="current-repo"' in html
    assert "上下文感知编码框架" in html
    assert "工作台" in html
    assert "运行详情" in html
    assert "当前仓库" in html
    assert "创建并运行" in html
    assert "查看运行详情" in html
    assert f"/ui/runs/{run.id}" in html


def test_webui_workbench_detail_nav_links_to_latest_run(tmp_path):
    repo = tmp_path / "prototype-workbench-nav-repo"
    repo.mkdir()
    service = CoreService(repo, llm=MockLLM([]))
    api = create_app(service)
    task = service.create_task("Nav target", "Latest run should drive detail navigation")
    run = service.run_task(task.id, max_rounds=1)

    html = _endpoint(api, "/", "GET")().body.decode("utf-8")

    assert f'<a href="/ui/runs/{run.id}">运行详情</a>' in html


def test_webui_run_detail_matches_design_prototype_structure(tmp_path):
    repo = tmp_path / "prototype-detail-repo"
    repo.mkdir()
    service = CoreService(
        repo,
        llm=MockLLM([
            '{"thought_summary":"needs approval","action":"run_command",'
            '"args":{"command":"python -m pytest tests/test_calculator.py -q"}}'
        ]),
    )
    api = create_app(service)
    task_id = _endpoint(api, "/tasks", "POST")({"title": "Prototype detail"})["id"]
    run_id = _endpoint(api, "/tasks/{task_id}/runs", "POST")(task_id, {"max_rounds": 1})["id"]

    html = _endpoint(api, "/ui/runs/{run_id}", "GET")(run_id).body.decode("utf-8")

    assert 'class="run-hero"' in html
    assert 'class="detail-layout"' in html
    assert 'class="timeline"' in html
    assert 'class="approval-box"' in html
    assert 'class="context-list"' in html
    assert "返回工作台" in html
    assert "导出 MD" in html
    assert "导出 JSON" in html
    assert "时间线" in html
    assert "待审批" in html
    assert "已选上下文" in html
    assert "python -m pytest tests/test_calculator.py -q" in html


def test_webui_run_detail_shows_human_readable_finish_result(tmp_path):
    repo = tmp_path / "webui-readable-result-repo"
    repo.mkdir()
    service = CoreService(
        repo,
        llm=MockLLM([
            '{"thought_summary":"summarized dependencies","action":"finish",'
            '"args":{"summary":"Project dependencies are Typer, FastAPI, Uvicorn, and keyring."}}'
        ]),
    )
    api = create_app(service)
    task_id = _endpoint(api, "/tasks", "POST")({"title": "Summarize dependencies"})["id"]
    run_id = _endpoint(api, "/tasks/{task_id}/runs", "POST")(task_id, {"max_rounds": 1})["id"]

    html = _endpoint(api, "/ui/runs/{run_id}", "GET")(run_id).body.decode("utf-8")

    assert 'class="result-card' in html
    assert "运行结果" in html
    assert "Project dependencies are Typer, FastAPI, Uvicorn, and keyring." in html


def test_report_endpoint_and_webui_render_readable_completed_run_report(tmp_path):
    repo = tmp_path / "webui-readable-report-repo"
    repo.mkdir()
    service = CoreService(
        repo,
        llm=MockLLM([
            '{"thought_summary":"summarized dependencies","action":"finish",'
            '"args":{"summary":"Project dependencies are Typer, FastAPI, Uvicorn, and keyring."}}'
        ]),
    )
    api = create_app(service)
    task_id = _endpoint(api, "/tasks", "POST")({"title": "Summarize dependencies"})["id"]
    run_id = _endpoint(api, "/tasks/{task_id}/runs", "POST")(task_id, {"max_rounds": 1})["id"]

    report = _endpoint(api, "/runs/{run_id}/report", "GET")(run_id)["content"]
    html = _endpoint(api, "/ui/runs/{run_id}", "GET")(run_id).body.decode("utf-8")

    for consumer in (report, html):
        assert "运行概览" in consumer
        assert "最终结论" in consumer
        assert "```json" not in consumer.split("审计原始数据", 1)[0]


def test_webui_run_detail_renders_report_markdown_as_semantic_html(tmp_path):
    repo = tmp_path / "webui-semantic-report-repo"
    repo.mkdir()
    service = CoreService(repo, llm=MockLLM([]))
    api = create_app(service)
    task_id = _endpoint(api, "/tasks", "POST")({
        "title": "Render report",
        "description": "<img src=x onerror=1>",
    })["id"]
    run_id = _endpoint(api, "/tasks/{task_id}/runs", "POST")(task_id, {"max_rounds": 1})["id"]

    html = _endpoint(api, "/ui/runs/{run_id}", "GET")(run_id).body.decode("utf-8")

    assert "<h1>运行报告</h1>" in html
    assert "<table>" in html
    assert "<td>---</td>" not in html
    assert "<ul><li>" in html
    assert "&lt;img src=x onerror=1&gt;" in html
    assert "<img src=x onerror=1>" not in html
    assert "<details>" in html
    assert "<summary>" in html
    assert "<pre># 运行报告" not in html


def test_webui_run_detail_explains_invalid_model_action_as_no_usable_result(tmp_path):
    repo = tmp_path / "webui-invalid-result-repo"
    repo.mkdir()
    service = CoreService(
        repo,
        llm=MockLLM([
            '{"action":"read_and_summarize","file":"pyproject.toml",'
            '"description":"Summarize project dependencies","modify":false}'
        ]),
    )
    api = create_app(service)
    task_id = _endpoint(api, "/tasks", "POST")({"title": "Summarize dependencies"})["id"]
    run_id = _endpoint(api, "/tasks/{task_id}/runs", "POST")(task_id, {"max_rounds": 1})["id"]

    html = _endpoint(api, "/ui/runs/{run_id}", "GET")(run_id).body.decode("utf-8")

    assert 'class="result-card' in html
    assert "本次没有生成可用结果" in html
    assert "模型返回的动作格式不符合要求" in html
    assert "Missing or invalid required field: thought_summary." in html


def test_webui_pending_approval_panel_shows_redacted_action_args(tmp_path):
    from harness.webui import include_webui

    repo = tmp_path / "webui-approval-detail-repo"
    repo.mkdir()
    service = CoreService(
        repo,
        llm=MockLLM([
            '{"thought_summary":"needs approval","action":"run_command",'
            '"args":{"command":"npm install left-pad"}}'
        ]),
    )
    api = create_app(service)
    include_webui(api, service)
    task_id = _endpoint(api, "/tasks", "POST")({"title": "Install dependency"})["id"]
    run_id = _endpoint(api, "/tasks/{task_id}/runs", "POST")(task_id, {"max_rounds": 1})["id"]

    html = _endpoint(api, "/ui/runs/{run_id}", "GET")(run_id).body.decode("utf-8")
    approval_section = html.split("待审批", 1)[1]

    assert "npm install left-pad" in approval_section


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
