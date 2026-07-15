"""Bounded agent runner lifecycle."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
import json
from pathlib import Path

from harness.actions import ActionParser
from harness.context_engine import ContextEngine
from harness.domain import (
    ActionType,
    ApprovalRequest,
    Feedback,
    FeedbackCategory,
    FeedbackSource,
    GuardrailDecision,
    SchemaStatus,
    TaskRun,
    TaskStatus,
    make_audit_event,
)
from harness.feedback import FeedbackEngine
from harness.guardrails import Guardrail
from harness.llm import LLMClient
from harness.profiler import TaskProfiler
from harness.storage import HarnessStorage, _redact
from harness.tools import ToolDispatcher


class AgentRunner:
    """Run model actions through parser, guardrails, tools, and feedback."""

    def __init__(
        self,
        *,
        storage: HarnessStorage,
        llm: LLMClient,
        repo_root: str | Path,
        validation_commands: list[str | Sequence[str]] | None = None,
    ) -> None:
        self.storage = storage
        self.llm = llm
        self.repo_root = Path(repo_root).resolve()
        self.validation_commands = validation_commands
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
        prior_actions: list[dict] = []
        profile = TaskProfiler().profile(task["description"] or task["title"])

        for round_index in range(max_rounds):
            self.storage.update_task_run(run.id, current_round=round_index)
            package = ContextEngine(self.repo_root, self.storage).build_package(
                task_run_id=run.id,
                round_index=round_index,
                task_request=task["description"] or task["title"],
            )
            context = self._context_for_package(package.items)
            action_text = self.llm.complete(
                self._messages(task, profile, context, prior_actions, prior_feedback)
            )
            action, schema_feedback = self.parser.parse(action_text)
            action.task_run_id = run.id
            action.round_index = round_index
            self.storage.create_action(action)

            if action.schema_status == SchemaStatus.INVALID.value:
                prior_actions.append(self._action_trace(action))
                if schema_feedback is not None:
                    schema_feedback.task_run_id = run.id
                    schema_feedback.round_index = round_index
                    schema_feedback.locations = schema_feedback.locations or ["schema_validation"]
                    self.storage.create_feedback(schema_feedback)
                    prior_feedback.append(schema_feedback)
                if self.feedback_engine.should_stop_early(prior_feedback):
                    return self._finish(run, TaskStatus.STOPPED.value, "repeated_failure")
                continue

            if action.action_type == ActionType.FINISH.value:
                validation_feedback = self._run_validation(run.id, round_index)
                prior_actions.append(self._action_trace(action))
                prior_feedback.extend(validation_feedback)
                if validation_feedback:
                    if self.feedback_engine.should_stop_early(prior_feedback):
                        return self._finish(run, TaskStatus.STOPPED.value, "repeated_failure")
                    continue
                return self._finish(run, TaskStatus.SUCCEEDED.value, "model_finished")

            guardrail = self.guardrail.evaluate(action)
            action.guardrail_status = guardrail.status
            self.storage.update_action_guardrail(action.id, guardrail.status)
            if guardrail.status == GuardrailDecision.DENY.value:
                self.storage.write_audit(make_audit_event(
                    "guardrail.blocked",
                    action_id=action.id,
                    task_run_id=run.id,
                    reason=guardrail.reason,
                ))
                feedback = Feedback(
                    task_run_id=run.id,
                    round_index=round_index,
                    source="guardrail",
                    category="unsafe_action",
                    summary=guardrail.reason,
                    locations=[action.action_type or "guardrail"],
                )
                self.storage.create_feedback(feedback)
                prior_feedback.append(feedback)
                prior_actions.append(self._action_trace(action))
                if self.feedback_engine.should_stop_early(prior_feedback):
                    return self._finish(run, TaskStatus.STOPPED.value, "repeated_failure")
                continue
            if guardrail.status == GuardrailDecision.REQUIRE_APPROVAL.value:
                self.storage.create_approval_request(ApprovalRequest(
                    task_run_id=run.id,
                    action_id=action.id,
                    risk_level=guardrail.risk_level,
                    reason=guardrail.reason,
                ))
                prior_actions.append(self._action_trace(action))
                return self._wait_for_approval(run, "approval_required")

            self.dispatcher.dispatch(action, repo_root=self.repo_root)
            validation_feedback = self._run_validation(run.id, round_index)
            prior_actions.append(self._action_trace(action))
            prior_feedback.extend(validation_feedback)
            if self.feedback_engine.should_stop_early(prior_feedback):
                return self._finish(run, TaskStatus.STOPPED.value, "repeated_failure")

        return self._finish(run, TaskStatus.STOPPED.value, "max_repair_rounds")

    def _messages(
        self,
        task: dict,
        profile: object,
        context: list[dict[str, object]],
        prior_actions: list[dict],
        feedback: list[Feedback],
    ) -> list[dict[str, str]]:
        content = {
            "task": task["description"] or task["title"],
            "profile": getattr(profile, "__dict__", {}),
            "context": context,
            "prior_actions": prior_actions,
            "feedback": [self._feedback_trace(item) for item in feedback],
        }
        return [
            {"role": "system", "content": "Return one structured JSON harness action."},
            {"role": "user", "content": json.dumps(content, ensure_ascii=False)},
        ]

    def _context_for_package(self, item_ids: list[str]) -> list[dict[str, object]]:
        context: list[dict[str, object]] = []
        for item_id in item_ids:
            item = self.storage.get_context_item(item_id)
            if item is not None:
                context.append({
                    "kind": item["kind"],
                    "source_path": item["source_path"],
                    "symbol": item["symbol"],
                    "summary": item["summary"],
                    "metadata": self._prompt_metadata(item["metadata"]),
                })
        return context

    def _prompt_metadata(self, metadata_json: str | None) -> dict[str, object]:
        if not metadata_json:
            return {}
        try:
            metadata = json.loads(metadata_json)
        except json.JSONDecodeError:
            return {}
        return {
            key: metadata[key]
            for key in ("source", "score", "selection_reason")
            if key in metadata
        }

    def _run_validation(self, task_run_id: str, round_index: int) -> list[Feedback]:
        commands = self.feedback_engine.discover_validation_commands(
            self.repo_root,
            configured=self.validation_commands,
        )
        if not commands:
            item = Feedback(
                task_run_id=task_run_id,
                round_index=round_index,
                source=FeedbackSource.BUILD.value,
                category=FeedbackCategory.UNKNOWN.value,
                summary="No validation commands configured or discovered.",
                locations=["validation_commands"],
            )
            self.storage.create_feedback(item)
            return [item]
        feedback: list[Feedback] = []
        for command in commands:
            item = self.feedback_engine.run_validation(command, self.repo_root)
            item.task_run_id = task_run_id
            item.round_index = round_index
            self.storage.create_feedback(item)
            if self._validation_passed(item):
                continue
            feedback.append(item)
        return feedback

    def _validation_passed(self, feedback: Feedback) -> bool:
        return bool(getattr(feedback, "passed", False))

    def _action_trace(self, action) -> dict[str, object]:
        try:
            args = json.loads(action.args_json or "{}")
        except json.JSONDecodeError:
            args = {}
        return {
            "action_id": action.id,
            "round_index": action.round_index,
            "action_type": action.action_type,
            "args": _redact(args) if isinstance(args, dict) else {},
            "schema_status": action.schema_status,
            "guardrail_status": action.guardrail_status,
            "tool_result": self._tool_result_trace(action),
        }

    def _tool_result_trace(self, action) -> dict[str, object] | None:
        if not action.task_run_id:
            return None
        for result in self.storage.list_tool_results_for_run(action.task_run_id):
            if result["action_id"] == action.id:
                return {
                    "status": result["status"],
                    "stdout_excerpt": result["stdout_excerpt"],
                    "stderr_excerpt": result["stderr_excerpt"],
                    "exit_code": result["exit_code"],
                    "changed_files": json.loads(result["changed_files"])
                    if result["changed_files"] else [],
                }
        return None

    def _feedback_trace(self, feedback: Feedback) -> dict[str, object]:
        return {
            "source": feedback.source,
            "category": feedback.category,
            "summary": feedback.summary,
            "locations": feedback.locations or [],
            "raw_excerpt": feedback.raw_excerpt,
        }

    def _wait_for_approval(self, run: TaskRun, stop_reason: str) -> TaskRun:
        self.storage.update_task_run(
            run.id,
            status=TaskStatus.WAITING_APPROVAL.value,
            stop_reason=stop_reason,
        )
        run.status = TaskStatus.WAITING_APPROVAL.value
        run.stop_reason = stop_reason
        return run

    def _finish(self, run: TaskRun, status: str, stop_reason: str) -> TaskRun:
        finished_at = datetime.now(timezone.utc).isoformat()
        self.storage.update_task_run(
            run.id,
            status=status,
            stop_reason=stop_reason,
            finished_at=finished_at,
        )
        self.storage.write_audit(make_audit_event(
            "run.finished",
            task_run_id=run.id,
            status=status,
            stop_reason=stop_reason,
        ))
        run.status = status
        run.stop_reason = stop_reason
        run.finished_at = finished_at
        return run
