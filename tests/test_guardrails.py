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
