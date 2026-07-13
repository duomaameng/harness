"""Task 5 tests - action parser and schema feedback (SPEC section 5.6)."""

import json

import pytest

from harness.actions import ActionParser
from harness.domain import FeedbackCategory, FeedbackSource, SchemaStatus


# -- Helpers --------------------------------------------------------

def _make_payload(action: str, args: dict, thought: str = "test") -> str:
    return json.dumps({"thought_summary": thought, "action": action, "args": args})


# -- Valid actions --------------------------------------------------

class TestValidActions:
    def test_read_file(self):
        raw = _make_payload("read_file", {"path": "src/main.py"})
        action, fb = ActionParser.parse(raw)
        assert fb is None
        assert action.schema_status == SchemaStatus.VALID.value
        assert action.action_type == "read_file"
        parsed_args = json.loads(action.args_json)
        assert parsed_args["path"] == "src/main.py"

    def test_write_file(self):
        raw = _make_payload("write_file", {"path": "x.py", "content": "print(1)"})
        action, fb = ActionParser.parse(raw)
        assert fb is None
        assert action.schema_status == SchemaStatus.VALID.value
        assert action.action_type == "write_file"

    def test_search(self):
        raw = _make_payload("search", {"query": "def test"})
        action, fb = ActionParser.parse(raw)
        assert fb is None
        assert action.action_type == "search"

    def test_search_with_optional_path(self):
        raw = _make_payload("search", {"query": "TODO", "path": "src/"})
        action, fb = ActionParser.parse(raw)
        assert fb is None

    def test_list_files(self):
        raw = _make_payload("list_files", {})
        action, fb = ActionParser.parse(raw)
        assert fb is None
        assert action.action_type == "list_files"

    def test_list_files_with_optional_path(self):
        raw = _make_payload("list_files", {"path": "src/"})
        action, fb = ActionParser.parse(raw)
        assert fb is None

    def test_run_command(self):
        raw = _make_payload("run_command", {"command": "pytest"})
        action, fb = ActionParser.parse(raw)
        assert fb is None
        assert action.action_type == "run_command"

    def test_show_diff(self):
        raw = _make_payload("show_diff", {})
        action, fb = ActionParser.parse(raw)
        assert fb is None
        assert action.action_type == "show_diff"

    def test_record_memory(self):
        raw = _make_payload("record_memory",
                            {"kind": "historical_decision", "content": "Use SQLite"})
        action, fb = ActionParser.parse(raw)
        assert fb is None
        assert action.action_type == "record_memory"

    def test_finish(self):
        raw = _make_payload("finish", {"summary": "All tests pass"})
        action, fb = ActionParser.parse(raw)
        assert fb is None
        assert action.action_type == "finish"


# -- Invalid JSON ---------------------------------------------------

class TestInvalidJson:
    def test_malformed_json(self):
        action, fb = ActionParser.parse("not json")
        assert action.schema_status == SchemaStatus.INVALID.value
        assert fb is not None
        assert fb.source == FeedbackSource.SCHEMA_VALIDATION.value
        assert fb.category == FeedbackCategory.INVALID_ACTION.value
        assert "Invalid JSON" in fb.summary

    def test_array_not_object(self):
        action, fb = ActionParser.parse("[1, 2, 3]")
        assert action.schema_status == SchemaStatus.INVALID.value
        assert fb is not None
        assert "not a JSON object" in fb.summary


# -- Unknown action -------------------------------------------------

class TestUnknownAction:
    """PLAN Task 5 first failing test."""

    def test_unknown_action_becomes_schema_feedback_and_is_not_executable(self):
        raw = _make_payload("delete_file", {"path": "x"})
        action, fb = ActionParser.parse(raw)

        assert action.schema_status == SchemaStatus.INVALID.value, \
            "Unknown action must be marked invalid"
        assert fb is not None, \
            "Unknown action must produce feedback"
        assert fb.source == FeedbackSource.SCHEMA_VALIDATION.value
        assert fb.category == FeedbackCategory.INVALID_ACTION.value
        assert "Unknown action type" in fb.summary
        assert "delete_file" in fb.summary

        # Action is recorded but not executable (no tool result can be
        # created for a schema-invalid action - SPEC section 8.5).
        assert action.action_type == "delete_file"


# -- Missing fields -------------------------------------------------

class TestMissingFields:
    def test_missing_thought_summary(self):
        payload = json.dumps({"action": "read_file", "args": {"path": "x"}})
        action, fb = ActionParser.parse(payload)
        assert action.schema_status == SchemaStatus.INVALID.value
        assert fb is not None
        assert "thought_summary" in fb.summary

    def test_missing_action_field(self):
        payload = json.dumps({"thought_summary": "t", "args": {}})
        action, fb = ActionParser.parse(payload)
        assert fb is not None
        assert "action" in fb.summary

    def test_missing_args_field(self):
        payload = json.dumps({"thought_summary": "t", "action": "read_file"})
        action, fb = ActionParser.parse(payload)
        assert fb is not None
        assert "args" in fb.summary

    def test_args_not_a_dict(self):
        payload = json.dumps({"thought_summary": "t", "action": "read_file", "args": [1, 2]})
        action, fb = ActionParser.parse(payload)
        assert fb is not None
        assert "object" in fb.summary.lower()

    def test_thought_summary_must_be_string(self):
        payload = json.dumps({"thought_summary": ["not", "text"],
                              "action": "read_file",
                              "args": {"path": "x"}})
        action, fb = ActionParser.parse(payload)
        assert action.schema_status == SchemaStatus.INVALID.value
        assert fb is not None
        assert "thought_summary" in fb.summary
        assert "str" in fb.summary


# -- Wrong argument types -------------------------------------------

class TestWrongArgTypes:
    def test_path_must_be_string(self):
        raw = _make_payload("read_file", {"path": 42})
        action, fb = ActionParser.parse(raw)
        assert action.schema_status == SchemaStatus.INVALID.value
        assert fb is not None
        assert "path" in fb.summary
        assert "str" in fb.summary

    def test_content_must_be_string(self):
        raw = _make_payload("write_file", {"path": "x", "content": 123})
        action, fb = ActionParser.parse(raw)
        assert fb is not None
        assert "content" in fb.summary

    def test_missing_required_arg(self):
        raw = _make_payload("read_file", {})
        action, fb = ActionParser.parse(raw)
        assert fb is not None
        assert "requires" in fb.summary.lower()
        assert "path" in fb.summary

    def test_unknown_arg_key(self):
        raw = _make_payload("read_file", {"path": "x", "extra_field": 1})
        action, fb = ActionParser.parse(raw)
        assert fb is not None
        assert "Unknown argument" in fb.summary
        assert "extra_field" in fb.summary

    def test_record_memory_kind_must_be_known(self):
        raw = _make_payload("record_memory",
                            {"kind": "random_note", "content": "Use SQLite"})
        action, fb = ActionParser.parse(raw)
        assert action.schema_status == SchemaStatus.INVALID.value
        assert fb is not None
        assert "record_memory.kind" in fb.summary
        assert "random_note" in fb.summary


# -- Boundary cases -------------------------------------------------

class TestBoundary:
    def test_very_long_raw_excerpt_is_truncated(self):
        long_str = "x" * 2000
        action, fb = ActionParser.parse(long_str)
        assert fb is not None
        assert len(fb.raw_excerpt) <= 500

    def test_unicode_in_args(self):
        raw = _make_payload("read_file", {"path": "src/中文/模块.py"})
        action, fb = ActionParser.parse(raw)
        assert fb is None
        parsed = json.loads(action.args_json)
        assert "中文" in parsed["path"]
