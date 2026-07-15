import sqlite3
import json

from harness.domain import Feedback, FeedbackCategory, FeedbackSource, Task, TaskStatus
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


def test_runner_model_input_includes_profile_context_and_prior_actions(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "calculator.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    storage = HarnessStorage(repo)
    storage.init()
    task = storage.create_task(
        Task(
            title="Update calculator",
            description="Update calculator.py with tests",
            repo_path=str(repo),
        )
    )
    llm = MockLLM(["not json"])

    AgentRunner(storage=storage, llm=llm, repo_root=repo).run(task.id, max_rounds=1)

    prompt = llm.requests[0][1]["content"]
    assert "profile" in prompt
    assert "context" in prompt
    assert "calculator.py" in prompt
    assert "prior_actions" in prompt


def test_runner_creates_approval_request_for_approval_actions(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    storage = HarnessStorage(repo)
    storage.init()
    task = storage.create_task(
        Task(
            title="Unknown command",
            description="Run a command that needs approval",
            repo_path=str(repo),
        )
    )

    run = AgentRunner(
        storage=storage,
        llm=MockLLM([
            '{"thought_summary":"needs approval","action":"run_command",'
            '"args":{"command":"python script.py"}}'
        ]),
        repo_root=repo,
    ).run(task.id, max_rounds=1)

    assert run.status == TaskStatus.WAITING_APPROVAL.value
    conn = sqlite3.connect(storage.db_path)
    try:
        approvals = conn.execute(
            "SELECT action_id, status, reason FROM approval_request"
        ).fetchall()
    finally:
        conn.close()
    assert len(approvals) == 1
    assert approvals[0][1] == "pending"
    assert "approval" in approvals[0][2].lower()


def test_runner_runs_validation_after_tool_execution_and_records_feedback(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("hello", encoding="utf-8")
    storage = HarnessStorage(repo)
    storage.init()
    task = storage.create_task(
        Task(
            title="Read then validate",
            description="Read README and run validation",
            repo_path=str(repo),
        )
    )

    run = AgentRunner(
        storage=storage,
        llm=MockLLM([
            '{"thought_summary":"read file","action":"read_file",'
            '"args":{"path":"README.md"}}'
        ]),
        repo_root=repo,
        validation_commands=["definitely-not-a-real-command"],
    ).run(task.id, max_rounds=1)

    feedback = storage.list_feedback_for_run(run.id)
    assert len(feedback) == 1
    assert "could not start" in feedback[0]["summary"]


def test_runner_stops_early_on_repeated_guardrail_failures(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    storage = HarnessStorage(repo)
    storage.init()
    task = storage.create_task(
        Task(
            title="Repeat unsafe action",
            description="Repeated unsafe actions should stop early",
            repo_path=str(repo),
        )
    )
    unsafe_action = (
        '{"thought_summary":"unsafe","action":"read_file",'
        '"args":{"path":"../secret.txt"}}'
    )

    run = AgentRunner(
        storage=storage,
        llm=MockLLM([unsafe_action, unsafe_action]),
        repo_root=repo,
    ).run(task.id, max_rounds=6)

    feedback = storage.list_feedback_for_run(run.id)
    assert len(feedback) == 2
    assert run.status == TaskStatus.STOPPED.value
    assert run.stop_reason == "repeated_failure"


def test_runner_finish_action_runs_final_validation_before_success(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    storage = HarnessStorage(repo)
    storage.init()
    task = storage.create_task(
        Task(
            title="Finish only after validation",
            description="Finish should still validate",
            repo_path=str(repo),
        )
    )

    run = AgentRunner(
        storage=storage,
        llm=MockLLM([
            '{"thought_summary":"done","action":"finish","args":{"summary":"done"}}'
        ]),
        repo_root=repo,
        validation_commands=["definitely-not-a-real-command"],
    ).run(task.id, max_rounds=1)

    feedback = storage.list_feedback_for_run(run.id)
    assert len(feedback) == 1
    assert "could not start" in feedback[0]["summary"]
    assert run.status == TaskStatus.STOPPED.value
    assert run.stop_reason == "max_repair_rounds"


def test_runner_successful_validation_records_passed_feedback(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("hello", encoding="utf-8")
    storage = HarnessStorage(repo)
    storage.init()
    task = storage.create_task(
        Task(
            title="Read and pass validation",
            description="Read README and pass validation",
            repo_path=str(repo),
        )
    )

    run = AgentRunner(
        storage=storage,
        llm=MockLLM([
            '{"thought_summary":"read file","action":"read_file",'
            '"args":{"path":"README.md"}}',
            '{"thought_summary":"done","action":"finish","args":{"summary":"done"}}',
        ]),
        repo_root=repo,
        validation_commands=[
            [__import__("sys").executable, "-c", "print('ok')"]
        ],
    ).run(task.id, max_rounds=2)

    feedback = storage.list_feedback_for_run(run.id)
    assert len(feedback) == 2
    assert {item["passed"] for item in feedback} == {1}
    assert all("exit 0" in item["summary"] for item in feedback)
    assert run.status == TaskStatus.SUCCEEDED.value


def test_runner_records_guardrail_blocked_audit_event(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    storage = HarnessStorage(repo)
    storage.init()
    task = storage.create_task(
        Task(
            title="Block unsafe read",
            description="Unsafe read should be audited",
            repo_path=str(repo),
        )
    )

    AgentRunner(
        storage=storage,
        llm=MockLLM([
            '{"thought_summary":"unsafe","action":"read_file",'
            '"args":{"path":"../secret.txt"}}'
        ]),
        repo_root=repo,
    ).run(task.id, max_rounds=1)

    audit_events = [
        json.loads(line)
        for line in storage.audit_path.read_text(encoding="utf-8").splitlines()
    ]
    assert any(event["type"] == "guardrail.blocked" for event in audit_events)


def test_runner_prompt_context_metadata_is_structured_and_whitelisted(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "calculator.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    storage = HarnessStorage(repo)
    storage.init()
    task = storage.create_task(
        Task(
            title="Update calculator",
            description="Update calculator.py",
            repo_path=str(repo),
        )
    )
    llm = MockLLM(["not json"])

    AgentRunner(storage=storage, llm=llm, repo_root=repo).run(task.id, max_rounds=1)

    prompt = json.loads(llm.requests[0][1]["content"])
    metadata_values = [
        item["metadata"]
        for item in prompt["context"]
        if item["source_path"] == "calculator.py"
    ]
    assert metadata_values
    assert isinstance(metadata_values[0], dict)
    assert set(metadata_values[0]) <= {"source", "score", "selection_reason"}


def test_runner_prior_actions_include_completed_guardrail_status_in_next_prompt(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("hello", encoding="utf-8")
    storage = HarnessStorage(repo)
    storage.init()
    task = storage.create_task(
        Task(
            title="Read twice",
            description="Read README twice",
            repo_path=str(repo),
        )
    )
    llm = MockLLM([
        '{"thought_summary":"read file","action":"read_file",'
        '"args":{"path":"README.md"}}',
        "not json",
    ])

    AgentRunner(storage=storage, llm=llm, repo_root=repo).run(task.id, max_rounds=2)

    prompt = json.loads(llm.requests[1][1]["content"])
    assert prompt["prior_actions"][0]["guardrail_status"] == "allow"
    assert prompt["prior_actions"][0]["round_index"] == 0
    assert prompt["prior_actions"][0]["action_id"]
    assert prompt["prior_actions"][0]["args"] == {"path": "README.md"}


def test_runner_validation_success_uses_structured_result_not_summary_text(tmp_path):
    class PassingFeedbackEngine:
        def discover_validation_commands(self, repo_root, configured=None):
            return ["pass"]

        def run_validation(self, command, cwd):
            feedback = Feedback(
                source=FeedbackSource.TEST.value,
                category=FeedbackCategory.UNKNOWN.value,
                summary="validation succeeded",
            )
            feedback.passed = True
            return feedback

        def should_stop_early(self, feedback):
            return False

    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("hello", encoding="utf-8")
    storage = HarnessStorage(repo)
    storage.init()
    task = storage.create_task(
        Task(
            title="Read and finish",
            description="Read README then finish",
            repo_path=str(repo),
        )
    )
    llm = MockLLM([
        '{"thought_summary":"read file","action":"read_file",'
        '"args":{"path":"README.md"}}',
        '{"thought_summary":"done","action":"finish","args":{"summary":"done"}}',
    ])
    runner = AgentRunner(storage=storage, llm=llm, repo_root=repo)
    runner.feedback_engine = PassingFeedbackEngine()

    run = runner.run(task.id, max_rounds=2)

    assert run.status == TaskStatus.SUCCEEDED.value
    feedback = storage.list_feedback_for_run(run.id)
    assert len(feedback) == 2
    assert {item["passed"] for item in feedback} == {1}


def test_runner_finish_without_validation_commands_does_not_succeed(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    storage = HarnessStorage(repo)
    storage.init()
    task = storage.create_task(
        Task(
            title="Finish without validation",
            description="Finish should require validation evidence",
            repo_path=str(repo),
        )
    )

    run = AgentRunner(
        storage=storage,
        llm=MockLLM([
            '{"thought_summary":"done","action":"finish","args":{"summary":"done"}}'
        ]),
        repo_root=repo,
    ).run(task.id, max_rounds=1)

    feedback = storage.list_feedback_for_run(run.id)
    assert run.status == TaskStatus.STOPPED.value
    assert run.stop_reason == "max_repair_rounds"
    assert feedback
    assert feedback[0]["source"] == FeedbackSource.BUILD.value
    assert "No validation commands" in feedback[0]["summary"]


def test_runner_waiting_approval_is_not_marked_finished(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    storage = HarnessStorage(repo)
    storage.init()
    task = storage.create_task(
        Task(
            title="Unknown command",
            description="Run a command that needs approval",
            repo_path=str(repo),
        )
    )

    run = AgentRunner(
        storage=storage,
        llm=MockLLM([
            '{"thought_summary":"needs approval","action":"run_command",'
            '"args":{"command":"python script.py"}}'
        ]),
        repo_root=repo,
    ).run(task.id, max_rounds=1)

    stored_run = storage.get_task_run(run.id)
    audit_events = [
        json.loads(line)
        for line in storage.audit_path.read_text(encoding="utf-8").splitlines()
    ]
    assert run.status == TaskStatus.WAITING_APPROVAL.value
    assert stored_run["finished_at"] is None
    assert not any(event["type"] == "run.finished" for event in audit_events)


def test_runner_sends_structured_feedback_to_next_repair_round(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("hello", encoding="utf-8")
    storage = HarnessStorage(repo)
    storage.init()
    task = storage.create_task(
        Task(
            title="Read then repair",
            description="Read README and repair validation failure",
            repo_path=str(repo),
        )
    )
    llm = MockLLM([
        '{"thought_summary":"read file","action":"read_file",'
        '"args":{"path":"README.md"}}',
        "not json",
    ])

    AgentRunner(
        storage=storage,
        llm=llm,
        repo_root=repo,
        validation_commands=["definitely-not-a-real-command"],
    ).run(task.id, max_rounds=2)

    prompt = json.loads(llm.requests[1][1]["content"])
    assert prompt["feedback"][0]["source"] == FeedbackSource.BUILD.value
    assert prompt["feedback"][0]["category"] == FeedbackCategory.UNKNOWN.value
    assert "summary" in prompt["feedback"][0]


def test_runner_sends_tool_result_observation_to_next_repair_round(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("observed tool output", encoding="utf-8")
    storage = HarnessStorage(repo)
    storage.init()
    task = storage.create_task(
        Task(
            title="Read then use result",
            description="Read README and use observed result",
            repo_path=str(repo),
        )
    )
    llm = MockLLM([
        '{"thought_summary":"read file","action":"read_file",'
        '"args":{"path":"README.md"}}',
        "not json",
    ])

    AgentRunner(
        storage=storage,
        llm=llm,
        repo_root=repo,
        validation_commands=["definitely-not-a-real-command"],
    ).run(task.id, max_rounds=2)

    prompt = json.loads(llm.requests[1][1]["content"])
    assert prompt["prior_actions"][0]["tool_result"]["status"] == "success"
    assert "observed tool output" in prompt["prior_actions"][0]["tool_result"]["stdout_excerpt"]


def test_runner_redacts_sensitive_prior_action_args_in_next_prompt(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    storage = HarnessStorage(repo)
    storage.init()
    task = storage.create_task(
        Task(
            title="Write then repair",
            description="Write a config and repair validation failure",
            repo_path=str(repo),
        )
    )
    secret = "sk-test-secret"
    llm = MockLLM([
        (
            '{"thought_summary":"write config","action":"write_file",'
            f'"args":{{"path":"config.txt","content":"OPENAI_API_KEY={secret}"}}}}'
        ),
        "not json",
    ])

    AgentRunner(
        storage=storage,
        llm=llm,
        repo_root=repo,
        validation_commands=["definitely-not-a-real-command"],
    ).run(task.id, max_rounds=2)

    prompt_text = llm.requests[1][1]["content"]
    prompt = json.loads(prompt_text)
    assert secret not in prompt_text
    assert prompt["prior_actions"][0]["args"]["content"] == "OPENAI_API_KEY=[REDACTED]"


def test_runner_redacts_sensitive_task_and_profile_fields_in_prompt(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    storage = HarnessStorage(repo)
    storage.init()
    secret = "sk-test-secret"
    task = storage.create_task(
        Task(
            title="Update config",
            description=f"Update config with OPENAI_API_KEY={secret}",
            repo_path=str(repo),
        )
    )
    llm = MockLLM(["not json"])

    AgentRunner(storage=storage, llm=llm, repo_root=repo).run(task.id, max_rounds=1)

    prompt_text = llm.requests[0][1]["content"]
    prompt = json.loads(prompt_text)
    assert secret not in prompt_text
    assert prompt["task"] == "Update config with OPENAI_API_KEY=[REDACTED]"
    assert secret not in json.dumps(prompt["profile"], ensure_ascii=False)


def test_feedback_passed_is_part_of_domain_contract():
    feedback = Feedback(
        source=FeedbackSource.TEST.value,
        category=FeedbackCategory.UNKNOWN.value,
        summary="validation succeeded",
        passed=True,
    )

    assert feedback.passed is True
