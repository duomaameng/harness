from __future__ import annotations

from harness.actions import ActionParser
from harness.domain import ActionType, FeedbackCategory, FeedbackSource, SchemaStatus


def test_unknown_action_becomes_schema_feedback_and_is_not_executable() -> None:
    parser = ActionParser()

    action, feedback = parser.parse(
        '{"thought_summary": "remove obsolete file", "action": "delete_file", "args": {"path": "old.py"}}'
    )

    assert action.schema_status == SchemaStatus.INVALID.value
    assert action.action_type == "delete_file"
    assert feedback is not None
    assert feedback.source == FeedbackSource.SCHEMA_VALIDATION.value
    assert feedback.category == FeedbackCategory.INVALID_ACTION.value


def test_supported_action_with_required_args_is_valid() -> None:
    parser = ActionParser()

    action, feedback = parser.parse(
        '{"thought_summary": "inspect file", "action": "read_file", "args": {"path": "harness/domain.py"}}'
    )

    assert action.schema_status == SchemaStatus.VALID.value
    assert action.action_type == ActionType.READ_FILE.value
    assert action.args_json == '{"path": "harness/domain.py"}'
    assert feedback is None


def test_invalid_json_becomes_schema_feedback() -> None:
    action, feedback = ActionParser().parse("{not json")

    assert action.schema_status == SchemaStatus.INVALID.value
    assert feedback is not None
    assert feedback.source == FeedbackSource.SCHEMA_VALIDATION.value
    assert feedback.category == FeedbackCategory.INVALID_ACTION.value


def test_missing_required_top_level_field_becomes_schema_feedback() -> None:
    action, feedback = ActionParser().parse(
        '{"thought_summary": "inspect file", "args": {"path": "harness/domain.py"}}'
    )

    assert action.schema_status == SchemaStatus.INVALID.value
    assert feedback is not None
    assert feedback.category == FeedbackCategory.INVALID_ACTION.value


def test_wrong_argument_type_becomes_schema_feedback() -> None:
    action, feedback = ActionParser().parse(
        '{"thought_summary": "inspect file", "action": "read_file", "args": {"path": 7}}'
    )

    assert action.schema_status == SchemaStatus.INVALID.value
    assert feedback is not None
    assert feedback.category == FeedbackCategory.INVALID_ACTION.value


def test_spec_optional_path_actions_accept_missing_path() -> None:
    parser = ActionParser()

    for payload in (
        '{"thought_summary": "list repo", "action": "list_files", "args": {}}',
        '{"thought_summary": "show changes", "action": "show_diff", "args": {}}',
        '{"thought_summary": "finish task", "action": "finish", "args": {"summary": "done"}}',
    ):
        action, feedback = parser.parse(payload)

        assert action.schema_status == SchemaStatus.VALID.value
        assert feedback is None


def test_optional_path_argument_must_be_string_when_present() -> None:
    parser = ActionParser()

    for payload in (
        '{"thought_summary": "search repo", "action": "search", "args": {"query": "foo", "path": 7}}',
        '{"thought_summary": "show changes", "action": "show_diff", "args": {"path": 7}}',
        '{"thought_summary": "list repo", "action": "list_files", "args": {"path": 7}}',
    ):
        action, feedback = parser.parse(payload)

        assert action.schema_status == SchemaStatus.INVALID.value
        assert feedback is not None
        assert feedback.category == FeedbackCategory.INVALID_ACTION.value


def test_record_memory_kind_must_be_supported_memory_kind() -> None:
    action, feedback = ActionParser().parse(
        '{"thought_summary": "remember choice", "action": "record_memory", "args": {"kind": "anything", "content": "Use pytest."}}'
    )

    assert action.schema_status == SchemaStatus.INVALID.value
    assert feedback is not None
    assert feedback.category == FeedbackCategory.INVALID_ACTION.value


def test_unknown_argument_field_becomes_schema_feedback() -> None:
    action, feedback = ActionParser().parse(
        '{"thought_summary": "read file", "action": "read_file", "args": {"path": "a.py", "command": "rm -rf ."}}'
    )

    assert action.schema_status == SchemaStatus.INVALID.value
    assert feedback is not None
    assert feedback.category == FeedbackCategory.INVALID_ACTION.value
    assert "command" in feedback.summary


def test_blank_required_string_becomes_schema_feedback() -> None:
    action, feedback = ActionParser().parse(
        '{"thought_summary": "run tests", "action": "run_command", "args": {"command": "   "}}'
    )

    assert action.schema_status == SchemaStatus.INVALID.value
    assert feedback is not None
    assert feedback.category == FeedbackCategory.INVALID_ACTION.value
    assert "command" in feedback.summary


def test_schema_feedback_raw_excerpt_is_redacted_and_truncated() -> None:
    payload = (
        '{"thought_summary": "bad", "action": "read_file", '
        '"args": {"path": "a.py", "api_key": "sk-test-secret", '
        '"extra": "'
        + ("x" * 500)
        + '"}}'
    )

    action, feedback = ActionParser().parse(payload)

    assert action.schema_status == SchemaStatus.INVALID.value
    assert feedback is not None
    assert "sk-test-secret" not in (feedback.raw_excerpt or "")
    assert "[REDACTED]" in (feedback.raw_excerpt or "")
    assert len(feedback.raw_excerpt or "") <= 240


def test_write_file_allows_empty_content_string() -> None:
    action, feedback = ActionParser().parse(
        '{"thought_summary": "empty file", "action": "write_file", "args": {"path": "empty.txt", "content": ""}}'
    )

    assert action.schema_status == SchemaStatus.VALID.value
    assert feedback is None


def test_schema_feedback_redacts_non_string_sensitive_json_values() -> None:
    action, feedback = ActionParser().parse(
        '{"thought_summary": "bad", "action": "read_file", "args": {"path": "a.py", "password": 123456, "extra": true}}'
    )

    assert action.schema_status == SchemaStatus.INVALID.value
    assert feedback is not None
    assert "123456" not in (feedback.raw_excerpt or "")
    assert "[REDACTED]" in (feedback.raw_excerpt or "")
