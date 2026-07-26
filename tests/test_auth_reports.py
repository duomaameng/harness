import json

from harness.auth import CredentialService
from harness.reports import ReportExporter


def test_report_export_redacts_api_key_from_action_trace():
    report = {
        "task_request": "Add a status endpoint",
        "action_trace": [
            {
                "tool": "run_command",
                "excerpt": "request failed with api_key=sk-test-secret",
            }
        ],
        "final_status": "failure",
    }

    exporter = ReportExporter(report)
    markdown = exporter.to_markdown()
    payload = json.loads(exporter.to_json())

    assert "sk-test-secret" not in markdown
    assert "sk-test-secret" not in json.dumps(payload)


def test_report_export_redacts_bearer_token_from_action_trace():
    report = {
        "action_trace": [
            {
                "tool": "run_command",
                "excerpt": "Authorization: Bearer secret-token-value",
            }
        ],
    }

    markdown = ReportExporter(report).to_markdown()
    payload = json.loads(ReportExporter(report).to_json())

    assert "secret-token-value" not in markdown
    assert "secret-token-value" not in json.dumps(payload)


def test_report_export_redacts_quoted_secret_values_with_spaces():
    report = {
        "action_trace": [
            {
                "tool": "run_command",
                "excerpt": 'login failed with password="value with spaces"',
            }
        ],
    }

    markdown = ReportExporter(report).to_markdown()
    payload = json.loads(ReportExporter(report).to_json())

    assert "with spaces" not in markdown
    assert "with spaces" not in json.dumps(payload)


def test_report_export_redacts_escaped_quoted_secret_values():
    report = {
        "action_trace": [
            {
                "tool": "run_command",
                "excerpt": 'login failed with password="a\\"b c"',
            }
        ],
    }

    markdown = ReportExporter(report).to_markdown()
    payload = json.loads(ReportExporter(report).to_json())

    assert "b c" not in markdown
    assert "b c" not in json.dumps(payload)


def test_report_export_redacts_json_string_secret_fields():
    report = {
        "action_trace": [
            {
                "tool": "run_command",
                "excerpt": '{"password": "hunter2"}',
            }
        ],
    }

    markdown = ReportExporter(report).to_markdown()
    payload = json.loads(ReportExporter(report).to_json())

    assert "hunter2" not in markdown
    assert "hunter2" not in json.dumps(payload)


class FakeKeyring:
    def __init__(self):
        self.values = {}

    def set_password(self, service, username, password):
        self.values[(service, username)] = password

    def get_password(self, service, username):
        return self.values.get((service, username))

    def delete_password(self, service, username):
        self.values.pop((service, username), None)


class BrokenKeyring:
    def get_password(self, service, username):
        raise RuntimeError("backend unavailable at C:/Users/secret-store")


def test_credentials_use_keyring_for_set_status_and_clear():
    keyring = FakeKeyring()
    credentials = CredentialService(keyring_backend=keyring)

    credentials.set("sk-keyring-secret")

    status = credentials.status()
    assert status == {
        "configured": True,
        "provider": "openai-compatible",
        "source": "keyring",
        "risk": None,
    }
    assert credentials.clear() is True
    assert credentials.status()["configured"] is False


def test_credentials_status_reports_provider_when_unconfigured():
    status = CredentialService(keyring_backend=FakeKeyring()).status()

    assert status["provider"] == "openai-compatible"
    assert status["configured"] is False


def test_credentials_status_reports_keyring_backend_errors():
    status = CredentialService(keyring_backend=BrokenKeyring()).status()

    assert status["configured"] is False
    assert status["source"] == "keyring"
    assert "unavailable" in status["risk"].lower()
    assert "C:/Users/secret-store" not in status["risk"]


def test_credentials_status_uses_env_fallback_when_keyring_backend_errors(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("HARNESS_API_KEY=sk-dotenv-secret\n", encoding="utf-8")

    status = CredentialService(keyring_backend=BrokenKeyring(), env_file=env_file).status()

    assert status["configured"] is True
    assert status["source"] == ".env"
    assert "plaintext" in status["risk"].lower()
    assert "sk-dotenv-secret" not in json.dumps(status)


def test_credentials_clear_handles_keyring_backend_errors():
    assert CredentialService(keyring_backend=BrokenKeyring()).clear() is False


def test_credentials_report_env_fallback_as_plaintext_risk_without_secret(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("HARNESS_API_KEY=sk-dotenv-secret\n", encoding="utf-8")

    status = CredentialService(keyring_backend=FakeKeyring(), env_file=env_file).status()

    assert status["configured"] is True
    assert status["source"] == ".env"
    assert "plaintext" in status["risk"].lower()
    assert "sk-dotenv-secret" not in json.dumps(status)


def test_credentials_report_export_style_env_fallback_without_secret(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text('export OPENAI_API_KEY="sk-export-secret"\n', encoding="utf-8")

    status = CredentialService(keyring_backend=FakeKeyring(), env_file=env_file).status()

    assert status["configured"] is True
    assert status["source"] == ".env"
    assert "plaintext" in status["risk"].lower()
    assert "sk-export-secret" not in json.dumps(status)


def test_credentials_get_prefers_keyring_secret_over_env_fallback(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("HARNESS_API_KEY=sk-env-secret\n", encoding="utf-8")
    keyring = FakeKeyring()
    credentials = CredentialService(keyring_backend=keyring, env_file=env_file)
    credentials.set("sk-keyring-secret")

    assert credentials.get() == "sk-keyring-secret"


def test_credentials_get_reads_deployment_environment_secret(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    monkeypatch.setenv("DEEPSEEK_API_KEY", "deployment-secret")

    assert CredentialService(keyring_backend=FakeKeyring(), env_file=env_file).get() == "deployment-secret"


def test_credentials_get_prefers_deployment_secret_over_env_file(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("DEEPSEEK_API_KEY=file-secret\n", encoding="utf-8")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "deployment-secret")

    assert CredentialService(keyring_backend=FakeKeyring(), env_file=env_file).get() == "deployment-secret"


def test_credentials_get_reads_export_style_openai_key_from_env(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text('export OPENAI_API_KEY="sk-export-secret"\n', encoding="utf-8")

    assert CredentialService(keyring_backend=FakeKeyring(), env_file=env_file).get() == "sk-export-secret"


def test_credentials_get_reads_deepseek_key_from_env(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("DEEPSEEK_API_KEY=deepseek-secret\n", encoding="utf-8")

    assert CredentialService(keyring_backend=FakeKeyring(), env_file=env_file).get() == "deepseek-secret"


def test_report_export_preserves_run_sections():
    report = {
        "task_request": "Add endpoint",
        "selected_context": ["harness/domain.py"],
        "action_trace": [{"tool": "run_command", "excerpt": "ok"}],
        "changed_files": ["harness/reports.py"],
        "validation": [{"command": "pytest", "result": "passed"}],
        "repair_rounds": 1,
        "approval_decisions": [{"status": "approved"}],
        "final_status": "success",
        "stop_reason": "completed",
    }

    payload = json.loads(ReportExporter(report).to_json())
    markdown = ReportExporter(report).to_markdown()

    assert payload == report
    assert "# 运行报告" in markdown
    for section in (
        "运行概览", "最终结论", "已选上下文", "动作轨迹", "验证与反馈",
        "审批记录", "变更文件", "审计原始数据",
    ):
        assert f"## {section}" in markdown


def test_report_export_reads_service_payload_field_names():
    report = {
        "selected_context": [{"items": [{
            "source_path": "pyproject.toml", "kind": "project_convention",
            "summary": "\u9879\u76ee\u914d\u7f6e", "metadata": {"score": 17},
        }]}],
        "action_trace": [
            {"action_type": "read_file", "args_json": '{"path": "pyproject.toml"}'},
            {"action_type": "finish", "args_json": '{"summary": "\u4f9d\u8d56\u603b\u7ed3\u5b8c\u6210"}'},
        ],
    }

    markdown = ReportExporter(report).to_markdown()

    assert "\u4f9d\u8d56\u603b\u7ed3\u5b8c\u6210" in markdown
    assert "\u8bfb\u53d6\u6587\u4ef6: pyproject.toml" in markdown
    assert "| pyproject.toml | project_convention | \u9879\u76ee\u914d\u7f6e | 17 |" in markdown


def test_report_export_renders_readable_run_sections():
    report = {
        "task_request": "Summarize the report export",
        "context_packages": [
            {
                "package": "harness",
                "items": [
                    {
                        "file": "pyproject.toml",
                        "type": "configuration",
                        "reason": "project dependencies",
                        "score": 0.95,
                    }
                ],
            }
        ],
        "selected_context": [
            {
                "file": "pyproject.toml",
                "type": "configuration",
                "reason": "project dependencies",
                "score": 0.95,
            },
            {
                "file": "C:/workspace/project/private.py",
                "type": "source",
                "reason": "absolute repository path",
                "score": 0.5,
            },
            "C:/workspace/project/scalar-private.py",
        ],
        "action_trace": [
            {"tool": "read_file", "path": "pyproject.toml"},
            {"tool": "finish", "excerpt": "报告汇总完成"},
        ],
        "tool_results": [{"tool": "read_file", "result": "[project]"}],
        "changed_files": ["harness/reports.py"],
        "feedback": [{
            "state": "verified",
            "reason": "The output is easy to scan.",
            "result": "passed",
        }],
        "approval_decisions": [{
            "status": "approved",
            "reason": "Ready",
            "result": "published",
        }],
        "final_status": "success",
        "stop_reason": "completed",
    }

    markdown = ReportExporter(report).to_markdown()

    assert "## 运行概览" in markdown
    assert "## 最终结论" in markdown
    assert "报告汇总完成" in markdown
    assert "## 已选上下文" in markdown
    assert "| 文件 | 类型 | 选择原因 | 评分 |" in markdown
    assert "pyproject.toml" in markdown
    assert "## 动作轨迹" in markdown
    assert "读取文件: " in markdown
    assert "pyproject.toml" in markdown
    assert "## 审计原始数据" in markdown
    assert "```json" not in markdown.split("## 审计原始数据", 1)[0]
    context_section = markdown.split("## 审计原始数据", 1)[0]
    assert "C:/workspace/project/private.py" not in context_section
    assert "C:/workspace/project/scalar-private.py" not in context_section
    empty_context = ReportExporter({"selected_context": ["C:/workspace/project/only-private.py"]}).to_markdown()
    empty_context_section = empty_context.split("## 审计原始数据", 1)[0]
    assert "| - | - | - | - |" in empty_context_section
    assert "- state: verified; reason: The output is easy to scan.; result: passed" in markdown
    assert "- status: approved; reason: Ready; result: published" in markdown
    assert json.loads(ReportExporter(report).to_json()) == report
