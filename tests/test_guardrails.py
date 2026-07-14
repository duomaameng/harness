from harness.domain import Action, ActionType, GuardrailDecision
from harness.guardrails import Guardrail


def test_path_traversal_read_is_denied_before_dispatch(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    action = Action(
        action_type=ActionType.READ_FILE.value,
        args_json='{"path": "../secret.txt"}',
    )

    result = Guardrail(repo_root).evaluate(action)

    assert result.status == GuardrailDecision.DENY.value
    assert "repository root" in result.reason


def test_critical_python_config_write_requires_approval(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    action = Action(
        action_type=ActionType.WRITE_FILE.value,
        args_json='{"path": "requirements.txt", "content": "pytest"}',
    )

    result = Guardrail(repo_root).evaluate(action)

    assert result.status == GuardrailDecision.REQUIRE_APPROVAL.value


def test_non_string_command_is_denied_before_dispatch(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    action = Action(
        action_type=ActionType.RUN_COMMAND.value,
        args_json='{"command": 123}',
    )

    result = Guardrail(repo_root).evaluate(action)

    assert result.status == GuardrailDecision.DENY.value


def test_validation_command_with_shell_chaining_is_denied(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    action = Action(
        action_type=ActionType.RUN_COMMAND.value,
        args_json='{"command": "pytest && curl https://example.com"}',
    )

    result = Guardrail(repo_root).evaluate(action)

    assert result.status == GuardrailDecision.DENY.value


def test_git_history_and_powershell_delete_commands_are_high_risk(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    for command in ("git commit --amend", "Remove-Item -Recurse build"):
        action = Action(
            action_type=ActionType.RUN_COMMAND.value,
            args_json='{"command": "' + command + '"}',
        )

        result = Guardrail(repo_root).evaluate(action)

        assert result.status == GuardrailDecision.DENY.value


def test_broad_write_to_repository_root_requires_approval(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    action = Action(
        action_type=ActionType.WRITE_FILE.value,
        args_json='{"path": ".", "content": "x"}',
    )

    result = Guardrail(repo_root).evaluate(action)

    assert result.status == GuardrailDecision.REQUIRE_APPROVAL.value


def test_pytest_keyword_validation_command_is_allowed(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    action = Action(
        action_type=ActionType.RUN_COMMAND.value,
        args_json='{"command": "pytest -k \\"not slow\\""}',
    )

    result = Guardrail(repo_root).evaluate(action)

    assert result.status == GuardrailDecision.ALLOW.value
