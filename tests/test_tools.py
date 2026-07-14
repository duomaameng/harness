import json
import sys
import tempfile
from pathlib import Path

from harness.domain import Action, Task, TaskRun
from harness.storage import HarnessStorage
from harness.tools import ToolDispatcher


def test_run_command_result_redacts_secret_like_output():
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        repo.mkdir()
        storage = HarnessStorage(repo)
        storage.init()
        task = Task(title="Tool dispatch", repo_path=str(repo))
        storage.create_task(task)
        run = TaskRun(task_id=task.id)
        storage.create_task_run(run)
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
