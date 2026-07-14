import json
import sys
import tempfile
from pathlib import Path
import subprocess

from harness.domain import Action, Task, TaskRun
from harness.storage import HarnessStorage
from harness.tools import ToolDispatcher, ToolLimits


def _storage_and_run(repo: Path):
    storage = HarnessStorage(repo)
    storage.init()
    task = Task(title="Tool dispatch", repo_path=str(repo))
    storage.create_task(task)
    run = TaskRun(task_id=task.id)
    storage.create_task_run(run)
    return storage, run


def test_run_command_result_redacts_secret_like_output():
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        repo.mkdir()
        storage, run = _storage_and_run(repo)
        action = Action(
            task_run_id=run.id,
            action_type="run_command",
            guardrail_status="allow",
            args_json=json.dumps({
                "command": (
                    f'"{sys.executable}" -c '
                    "\"print('OPENAI_API_KEY=sk-test-secret')\""
                ),
            }),
        )
        storage.create_action(action)

        result = ToolDispatcher(storage).dispatch(action, repo_root=repo)

        stored = storage.get_tool_result(result.id)
        assert stored is not None
        assert "sk-test-secret" not in stored["stdout_excerpt"]
        assert stored["stdout_excerpt"] == "OPENAI_API_KEY=[REDACTED]\n"


def test_run_command_result_redacts_bearer_and_env_style_secret_output():
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        repo.mkdir()
        storage, run = _storage_and_run(repo)
        action = Action(
            task_run_id=run.id,
            action_type="run_command",
            guardrail_status="allow",
            args_json=json.dumps({
                "command": (
                    f'"{sys.executable}" -c '
                    "\"print('Authorization: Bearer abc123'); print('PASSWORD=hunter2')\""
                ),
            }),
        )
        storage.create_action(action)

        result = ToolDispatcher(storage).dispatch(action, repo_root=repo)

        stored = storage.get_tool_result(result.id)
        assert stored is not None
        assert "abc123" not in stored["stdout_excerpt"]
        assert "hunter2" not in stored["stdout_excerpt"]
        assert "Bearer [REDACTED]" in stored["stdout_excerpt"]
        assert "PASSWORD=[REDACTED]" in stored["stdout_excerpt"]


def test_tool_result_records_redaction_and_truncation_metadata():
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        repo.mkdir()
        storage, run = _storage_and_run(repo)
        action = Action(
            task_run_id=run.id,
            action_type="run_command",
            guardrail_status="allow",
            args_json=json.dumps({
                "command": f'"{sys.executable}" -c "print(\'OPENAI_API_KEY=sk-test-secret-and-long\')"',
            }),
        )
        storage.create_action(action)

        result = ToolDispatcher(storage, limits=ToolLimits(stdout_chars=24)).dispatch(
            action, repo_root=repo
        )

        stored = storage.get_tool_result(result.id)
        assert stored is not None
        metadata = json.loads(stored["metadata"])
        assert metadata["stdout_redacted"] is True
        assert metadata["stdout_truncated"] is True
        assert metadata["stdout_limit"] == 24


def test_tool_error_is_recorded_as_tool_result():
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        repo.mkdir()
        storage, run = _storage_and_run(repo)
        action = Action(
            task_run_id=run.id,
            action_type="read_file",
            guardrail_status="allow",
            args_json=json.dumps({"path": "missing.txt"}),
        )
        storage.create_action(action)

        result = ToolDispatcher(storage).dispatch(action, repo_root=repo)

        stored = storage.get_tool_result(result.id)
        assert stored is not None
        assert stored["status"] == "error"
        assert stored["stderr_excerpt"]


def test_run_command_changed_files_excludes_preexisting_dirty_files():
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, capture_output=True, text=True)
        (repo / "preexisting.txt").write_text("dirty", encoding="utf-8")
        storage, run = _storage_and_run(repo)
        action = Action(
            task_run_id=run.id,
            action_type="run_command",
            guardrail_status="allow",
            args_json=json.dumps({"command": f'"{sys.executable}" -c "print(123)"'}),
        )
        storage.create_action(action)

        result = ToolDispatcher(storage).dispatch(action, repo_root=repo)

        stored = storage.get_tool_result(result.id)
        assert stored is not None
        assert stored["changed_files"] is None


def test_run_command_tracks_modified_preexisting_dirty_file():
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, capture_output=True, text=True)
        (repo / "preexisting.txt").write_text("dirty", encoding="utf-8")
        storage, run = _storage_and_run(repo)
        action = Action(
            task_run_id=run.id,
            action_type="run_command",
            guardrail_status="allow",
            args_json=json.dumps({
                "command": (
                    f'"{sys.executable}" -c '
                    "\"from pathlib import Path; Path('preexisting.txt').write_text('changed')\""
                ),
            }),
        )
        storage.create_action(action)

        result = ToolDispatcher(storage).dispatch(action, repo_root=repo)

        stored = storage.get_tool_result(result.id)
        assert stored is not None
        assert stored["changed_files"] == '["preexisting.txt"]'


def test_timed_out_command_excludes_preexisting_dirty_files():
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, capture_output=True, text=True)
        (repo / "preexisting.txt").write_text("dirty", encoding="utf-8")
        storage, run = _storage_and_run(repo)
        action = Action(
            task_run_id=run.id,
            action_type="run_command",
            guardrail_status="allow",
            args_json=json.dumps({
                "command": f'"{sys.executable}" -c "import time; time.sleep(2)"',
            }),
        )
        storage.create_action(action)

        result = ToolDispatcher(
            storage, limits=ToolLimits(command_timeout_seconds=1)
        ).dispatch(action, repo_root=repo)

        stored = storage.get_tool_result(result.id)
        assert stored is not None
        assert stored["status"] == "timeout"
        assert stored["changed_files"] is None


def test_read_file_uses_file_limit_without_stdout_limit():
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        repo.mkdir()
        (repo / "long.txt").write_text("abcdefghijklmnop", encoding="utf-8")
        storage, run = _storage_and_run(repo)
        action = Action(
            task_run_id=run.id,
            action_type="read_file",
            guardrail_status="allow",
            args_json=json.dumps({"path": "long.txt"}),
        )
        storage.create_action(action)

        result = ToolDispatcher(
            storage, limits=ToolLimits(file_chars=15, stdout_chars=8)
        ).dispatch(action, repo_root=repo)

        stored = storage.get_tool_result(result.id)
        assert stored is not None
        assert stored["stdout_excerpt"] == "abcdefghijkl..."


def test_run_command_requires_string_command_argument():
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        repo.mkdir()
        storage, run = _storage_and_run(repo)
        action = Action(
            task_run_id=run.id,
            action_type="run_command",
            guardrail_status="allow",
            args_json=json.dumps({"command": [sys.executable, "-c", "print(123)"]}),
        )
        storage.create_action(action)

        result = ToolDispatcher(storage).dispatch(action, repo_root=repo)

        stored = storage.get_tool_result(result.id)
        assert stored is not None
        assert stored["status"] == "error"
        assert "command" in stored["stderr_excerpt"]


def test_file_search_diff_memory_tools_record_results_and_limits():
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, capture_output=True, text=True)
        storage, run = _storage_and_run(repo)
        dispatcher = ToolDispatcher(storage, limits=ToolLimits(file_chars=12))

        write_action = Action(
            task_run_id=run.id,
            action_type="write_file",
            guardrail_status="allow",
            args_json=json.dumps({"path": "src/example.txt", "content": "alpha beta gamma"}),
        )
        storage.create_action(write_action)
        write_result = dispatcher.dispatch(write_action, repo_root=repo)
        assert storage.get_tool_result(write_result.id)["changed_files"] == '["src/example.txt"]'

        read_action = Action(
            task_run_id=run.id,
            action_type="read_file",
            guardrail_status="allow",
            args_json=json.dumps({"path": "src/example.txt"}),
        )
        storage.create_action(read_action)
        read_result = dispatcher.dispatch(read_action, repo_root=repo)
        assert storage.get_tool_result(read_result.id)["stdout_excerpt"] == "alpha bet..."

        search_action = Action(
            task_run_id=run.id,
            action_type="search",
            guardrail_status="allow",
            args_json=json.dumps({"query": "beta", "path": "src"}),
        )
        storage.create_action(search_action)
        search_result = dispatcher.dispatch(search_action, repo_root=repo)
        assert "src/example.txt:1" in storage.get_tool_result(search_result.id)["stdout_excerpt"]

        diff_action = Action(
            task_run_id=run.id,
            action_type="show_diff",
            guardrail_status="allow",
            args_json=json.dumps({"path": "src/example.txt"}),
        )
        storage.create_action(diff_action)
        diff_result = dispatcher.dispatch(diff_action, repo_root=repo)
        assert storage.get_tool_result(diff_result.id)["status"] == "success"

        memory_action = Action(
            task_run_id=run.id,
            action_type="record_memory",
            guardrail_status="allow",
            args_json=json.dumps({"kind": "task_summary", "content": "remember this"}),
        )
        storage.create_action(memory_action)
        memory_result = dispatcher.dispatch(memory_action, repo_root=repo)
        assert storage.get_tool_result(memory_result.id)["status"] == "success"
        assert storage.list_memory_entries(repo_path=str(repo))[0]["content"] == "remember this"


def test_search_uses_search_limit_before_stdout_limit():
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        repo.mkdir()
        (repo / "matches.txt").write_text(
            "\n".join(f"beta {index}" for index in range(30)),
            encoding="utf-8",
        )
        storage, run = _storage_and_run(repo)
        action = Action(
            task_run_id=run.id,
            action_type="search",
            guardrail_status="allow",
            args_json=json.dumps({"query": "beta"}),
        )
        storage.create_action(action)

        result = ToolDispatcher(
            storage, limits=ToolLimits(search_chars=20, stdout_chars=4000)
        ).dispatch(action, repo_root=repo)

        stored = storage.get_tool_result(result.id)
        assert stored is not None
        assert len(stored["stdout_excerpt"]) <= 20
        metadata = json.loads(stored["metadata"])
        assert metadata["stdout_truncated"] is True
        assert metadata["stdout_limit"] == 20
