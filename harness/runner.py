"""Bounded agent runner lifecycle."""

from __future__ import annotations

import json
from pathlib import Path

from harness.actions import ActionParser
from harness.context_engine import ContextEngine
from harness.domain import (
    ActionType,
    Feedback,
    GuardrailDecision,
    SchemaStatus,
    TaskRun,
    TaskStatus,
)
from harness.feedback import FeedbackEngine
from harness.guardrails import Guardrail
from harness.llm import LLMClient
from harness.storage import HarnessStorage
from harness.tools import ToolDispatcher


class AgentRunner:
    """Run model actions through parser, guardrails, tools, and feedback."""

    def __init__(
        self,
        *,
        storage: HarnessStorage,
        llm: LLMClient,
        repo_root: str | Path,
    ) -> None:
        self.storage = storage
        self.llm = llm
        self.repo_root = Path(repo_root).resolve()
        self.parser = ActionParser()
        self.guardrail = Guardrail(self.repo_root)
        self.dispatcher = ToolDispatcher(storage)
        self.feedback_engine = FeedbackEngine()

    def run(self, task_id: str, max_rounds: int = 6) -> TaskRun:
        task = self.storage.get_task(task_id)
        if task is None:
            raise ValueError(f"Unknown task: {task_id}")

        run = self.storage.create_task_run(TaskRun(
            task_id=task_id,
            status=TaskStatus.RUNNING.value,
            max_repair_rounds=max_rounds,
        ))
        prior_feedback: list[Feedback] = []

        for round_index in range(max_rounds):
            self.storage.update_task_run(run.id, current_round=round_index)
            ContextEngine(self.repo_root, self.storage).build_package(
                task_run_id=run.id,
                round_index=round_index,
                task_request=task["description"] or task["title"],
            )
            action_text = self.llm.complete(self._messages(task, prior_feedback))
            action, schema_feedback = self.parser.parse(action_text)
            action.task_run_id = run.id
            action.round_index = round_index
            self.storage.create_action(action)

            if action.schema_status == SchemaStatus.INVALID.value:
                if schema_feedback is not None:
                    schema_feedback.task_run_id = run.id
                    schema_feedback.round_index = round_index
                    self.storage.create_feedback(schema_feedback)
                    prior_feedback.append(schema_feedback)
                if self.feedback_engine.should_stop_early(prior_feedback):
                    return self._finish(run, TaskStatus.STOPPED.value, "repeated_failure")
                continue

            if action.action_type == ActionType.FINISH.value:
                return self._finish(run, TaskStatus.SUCCEEDED.value, "model_finished")

            guardrail = self.guardrail.evaluate(action)
            action.guardrail_status = guardrail.status
            self.storage.update_action_guardrail(action.id, guardrail.status)
            if guardrail.status == GuardrailDecision.DENY.value:
                feedback = Feedback(
                    task_run_id=run.id,
                    round_index=round_index,
                    source="guardrail",
                    category="unsafe_action",
                    summary=guardrail.reason,
                )
                self.storage.create_feedback(feedback)
                prior_feedback.append(feedback)
                continue
            if guardrail.status == GuardrailDecision.REQUIRE_APPROVAL.value:
                return self._finish(run, TaskStatus.WAITING_APPROVAL.value, "approval_required")

            self.dispatcher.dispatch(action, repo_root=self.repo_root)

        return self._finish(run, TaskStatus.STOPPED.value, "max_repair_rounds")

    def _messages(
        self,
        task: dict,
        feedback: list[Feedback],
    ) -> list[dict[str, str]]:
        content = {
            "task": task["description"] or task["title"],
            "feedback": [item.summary for item in feedback],
        }
        return [
            {"role": "system", "content": "Return one structured JSON harness action."},
            {"role": "user", "content": json.dumps(content, ensure_ascii=False)},
        ]

    def _finish(self, run: TaskRun, status: str, stop_reason: str) -> TaskRun:
        self.storage.update_task_run(run.id, status=status, stop_reason=stop_reason)
        run.status = status
        run.stop_reason = stop_reason
        return run
