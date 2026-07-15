import sqlite3

from harness.domain import FeedbackCategory, FeedbackSource, Task
from harness.llm import MockLLM
from harness.runner import AgentRunner
from harness.storage import HarnessStorage


def test_invalid_action_from_mock_llm_becomes_feedback_without_tool_execution(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    storage = HarnessStorage(repo)
    storage.init()
    task = storage.create_task(
        Task(
            title="Handle invalid action",
            description="Run one invalid model action",
            repo_path=str(repo),
        )
    )
    runner = AgentRunner(
        storage=storage,
        llm=MockLLM(["not json"]),
        repo_root=repo,
    )

    run = runner.run(task.id, max_rounds=1)

    feedback = storage.list_feedback_for_run(run.id)
    assert len(feedback) == 1
    assert feedback[0]["source"] == FeedbackSource.SCHEMA_VALIDATION.value
    assert feedback[0]["category"] == FeedbackCategory.INVALID_ACTION.value
    conn = sqlite3.connect(storage.db_path)
    try:
        tool_result_count = conn.execute("SELECT COUNT(*) FROM tool_result").fetchone()[0]
    finally:
        conn.close()
    assert tool_result_count == 0


def test_denied_action_from_mock_llm_becomes_guardrail_feedback_without_tool_execution(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    storage = HarnessStorage(repo)
    storage.init()
    task = storage.create_task(
        Task(
            title="Block dangerous command",
            description="Do not run destructive shell commands",
            repo_path=str(repo),
        )
    )
    runner = AgentRunner(
        storage=storage,
        llm=MockLLM([
            '{"thought_summary":"try dangerous command","action":"run_command",'
            '"args":{"command":"rm -rf ."}}'
        ]),
        repo_root=repo,
    )

    run = runner.run(task.id, max_rounds=1)

    feedback = storage.list_feedback_for_run(run.id)
    assert len(feedback) == 1
    assert feedback[0]["source"] == "guardrail"
    assert feedback[0]["category"] == "unsafe_action"
    conn = sqlite3.connect(storage.db_path)
    try:
        tool_result_count = conn.execute("SELECT COUNT(*) FROM tool_result").fetchone()[0]
    finally:
        conn.close()
    assert tool_result_count == 0
