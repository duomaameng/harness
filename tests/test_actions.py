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
