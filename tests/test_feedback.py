import sys

from harness.domain import Feedback, FeedbackCategory, FeedbackSource
from harness.feedback import FeedbackEngine


def test_feedback_engine_discovers_configured_commands_before_project_defaults(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[tool.pytest.ini_options]\n", encoding="utf-8")
    (tmp_path / "package.json").write_text('{"scripts":{"test":"vitest"}}', encoding="utf-8")

    engine = FeedbackEngine()

    assert engine.discover_validation_commands(
        tmp_path,
        configured=["ruff check ."],
    ) == ["ruff check ."]


def test_feedback_engine_discovers_pyproject_lint_typecheck_and_build(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        "[tool.pytest.ini_options]\n[tool.ruff]\n[tool.mypy]\n[build-system]\nrequires=[]\n",
        encoding="utf-8",
    )

    commands = FeedbackEngine().discover_validation_commands(tmp_path)

    assert "python -m pytest" in commands
    assert "ruff check ." in commands
    assert "mypy ." in commands
    assert "python -m build" in commands


def test_feedback_engine_parses_pytest_failure_with_location_and_excerpt():
    output = """
    tests/test_math.py::test_addition FAILED
    E   assert 1 == 2
    """

    feedback = FeedbackEngine().parse_validation_result(
        command="python -m pytest",
        exit_code=1,
        stdout="",
        stderr=output,
    )

    assert feedback.source == FeedbackSource.TEST.value
    assert feedback.category == FeedbackCategory.ASSERTION_FAILURE.value
    assert feedback.locations == ["tests/test_math.py::test_addition"]
    assert "assert 1 == 2" in feedback.raw_excerpt


def test_feedback_engine_redacts_secret_values_from_raw_excerpt():
    feedback = FeedbackEngine().parse_validation_result(
        command="python -m pytest",
        exit_code=1,
        stdout="OPENAI_API_KEY=sk-test-secret",
        stderr="",
    )

    assert "sk-test-secret" not in feedback.raw_excerpt
    assert "[REDACTED]" in feedback.raw_excerpt


def test_feedback_engine_structures_timeout_feedback():
    feedback = FeedbackEngine().timeout_feedback(
        command="python -m pytest",
        stdout="",
        stderr="",
    )

    assert feedback.source == FeedbackSource.TEST.value
    assert feedback.category == FeedbackCategory.UNKNOWN.value
    assert "timeout" in feedback.summary.lower()


def test_feedback_engine_run_validation_times_out_argv_command(tmp_path):
    feedback = FeedbackEngine().run_validation(
        [sys.executable, "-c", "import time; time.sleep(2)"],
        tmp_path,
        timeout_seconds=1,
    )

    assert feedback.category == FeedbackCategory.UNKNOWN.value
    assert "timeout" in feedback.summary.lower()
    assert "could not start" not in feedback.summary


def test_feedback_engine_returns_feedback_when_command_cannot_start(tmp_path):
    feedback = FeedbackEngine().run_validation(
        "definitely-not-a-real-command",
        tmp_path,
    )

    assert feedback.source == FeedbackSource.BUILD.value
    assert feedback.category == FeedbackCategory.UNKNOWN.value
    assert "could not start" in feedback.summary


def test_feedback_engine_parses_guardrail_approval_and_build_failures():
    engine = FeedbackEngine()

    guardrail = engine.parse_validation_result(
        command="guardrail",
        exit_code=1,
        stdout="guardrail blocked path",
        stderr="",
    )
    approval = engine.parse_validation_result(
        command="approval",
        exit_code=1,
        stdout="approval rejected by user",
        stderr="",
    )
    build = engine.parse_validation_result(
        command="python -m build",
        exit_code=1,
        stdout="build failed",
        stderr="",
    )

    assert guardrail.source == FeedbackSource.GUARDRAIL.value
    assert guardrail.category == FeedbackCategory.UNSAFE_ACTION.value
    assert approval.source == FeedbackSource.GUARDRAIL.value
    assert approval.category == FeedbackCategory.UNSAFE_ACTION.value
    assert build.source == FeedbackSource.BUILD.value
    assert build.category == FeedbackCategory.UNKNOWN.value


def test_feedback_engine_accepts_known_mechanism_sources():
    feedback = FeedbackEngine().parse_validation_result(
        command="schema_validation",
        exit_code=1,
        stdout="invalid action payload",
        stderr="",
        source=FeedbackSource.SCHEMA_VALIDATION.value,
    )

    assert feedback.source == FeedbackSource.SCHEMA_VALIDATION.value
    assert feedback.category == FeedbackCategory.INVALID_ACTION.value


def test_feedback_engine_keeps_generic_exit_code_unknown():
    feedback = FeedbackEngine().parse_validation_result(
        command="custom-validator",
        exit_code=2,
        stdout="command exited 2",
        stderr="",
    )

    assert feedback.source == FeedbackSource.BUILD.value
    assert feedback.category == FeedbackCategory.UNKNOWN.value


def test_repeated_same_pytest_failure_stops_after_second_occurrence():
    first_failure = Feedback(
        source=FeedbackSource.TEST.value,
        category=FeedbackCategory.ASSERTION_FAILURE.value,
        summary="test_math.py::test_addition failed",
        locations=["tests/test_math.py::test_addition"],
    )
    repeated_failure = Feedback(
        source=FeedbackSource.TEST.value,
        category=FeedbackCategory.ASSERTION_FAILURE.value,
        summary="test_math.py::test_addition failed again",
        locations=["tests/test_math.py::test_addition"],
    )

    engine = FeedbackEngine()

    assert engine.should_stop_early([first_failure, repeated_failure])
