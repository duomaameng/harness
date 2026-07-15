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
    for section in report:
        assert section.replace("_", " ").title() in markdown
