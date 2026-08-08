"""Bounded agent runner lifecycle."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Callable

from harness.actions import ActionParser
from harness.context_engine import ContextEngine
from harness.domain import (
    Action,
    ActionType,
    ApprovalRequest,
    ApprovalStatus,
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
from harness.llm import LLMClient, LLMClientError, LLMTimeoutError
from harness.profiler import TaskProfiler
from harness.storage import HarnessStorage, _redact
from harness.tools import ToolDispatcher


_ACTION_SYSTEM_PROMPT = """Return exactly one JSON object for the next harness action.
The JSON object must have exactly these top-level fields:
{
  "thought_summary": "short reason for the next action",
  "action": "one allowed action name",
  "args": {}
}

Allowed action names and args:
- read_file: {"path": "relative/path"}
- write_file: {"path": "relative/path", "content": "complete file content"}
- search: {"query": "text or regex", "path": "optional relative directory"}
- list_files: {"path": "optional relative directory"}
- run_command: {"command": "single command without shell chaining"}
- show_diff: {"path": "optional relative path"}
- record_memory: {"kind": "task_summary", "content": "memory content"}
- finish: {"summary": "final human-readable result"}

Do not invent action names. For example, use read_file then finish; never use
read_and_summarize, summarize_file, inspect, answer, or edit. Put all action
parameters inside args. The response must be valid JSON only, with no markdown
or explanatory text outside the JSON object."""


class AgentRunner:
    """Run model actions through parser, guardrails, tools, and feedback."""

    def __init__(
        self,
        *,
        storage: HarnessStorage,
        llm: LLMClient,
        repo_root: str | Path,
        validation_commands: list[str | Sequence[str]] | None = None,
        event_publisher: Callable[[str], None] | None = None,
    ) -> None:
        self.storage = storage
        self.llm = llm
        self.repo_root = Path(repo_root).resolve()
        self.validation_commands = validation_commands
        self.parser = ActionParser()
        self.guardrail = Guardrail(self.repo_root)
        self.dispatcher = ToolDispatcher(storage)
        self.feedback_engine = FeedbackEngine()
        self._event_publisher = event_publisher

    def run(self, task_id: str, max_rounds: int = 6) -> TaskRun:
        task = self.storage.get_task(task_id)
        if task is None:
            raise ValueError(f"Unknown task: {task_id}")

        run = self.storage.create_task_run(TaskRun(
            task_id=task_id,
            status=TaskStatus.RUNNING.value,
            max_repair_rounds=max_rounds,
        ))
        self._publish_run_update(run.id)
        return self._continue(task=task, run=run, start_round=0)

    def resume_approved_action(self, approval_id: str) -> TaskRun:
        approval = self.storage.get_approval_request(approval_id)
        if approval is None or approval["status"] != ApprovalStatus.APPROVED.value:
            raise ValueError(f"Approval is not approved: {approval_id}")
        stored_run = self.storage.get_task_run(approval["task_run_id"])
        if stored_run is None or stored_run["status"] != TaskStatus.WAITING_APPROVAL.value:
            raise ValueError("Approval does not belong to a waiting task run")
        task = self.storage.get_task(stored_run["task_id"])
        action_data = self.storage.get_action(approval["action_id"])
        if task is None or action_data is None:
            raise ValueError("Approval is missing its task or action")

        run = TaskRun(**stored_run)
        action = Action(**action_data)
        self.storage.update_task_run(
            run.id,
            status=TaskStatus.RUNNING.value,
            stop_reason=None,
        )
        run.status = TaskStatus.RUNNING.value
        run.stop_reason = None
        self._publish_run_update(run.id)

        result = self.dispatcher.dispatch_approved(
            action,
            approval_id=approval_id,
            repo_root=self.repo_root,
        )
        prior_actions = [
            self._action_trace(Action(**item))
            for item in self.storage.list_actions_for_run(run.id)
        ]
        prior_feedback = [
            self._feedback_from_row(item)
            for item in self.storage.list_feedback_for_run(run.id)
        ]
        changed_files = self._changed_files_for_run(run.id)
        changed_files.update(result.changed_files or [])
        if self._should_validate_after(action):
            validation_feedback = self._run_validation(run.id, action.round_index)
            prior_feedback.extend(validation_feedback)
            if self.feedback_engine.should_stop_early(prior_feedback):
                return self._finish(run, TaskStatus.STOPPED.value, "repeated_failure")
        return self._continue(
            task=task,
            run=run,
            start_round=action.round_index + 1,
            prior_actions=prior_actions,
            prior_feedback=prior_feedback,
            changed_files=changed_files,
        )

    def resume_rejected_action(self, approval_id: str) -> TaskRun:
        approval = self.storage.get_approval_request(approval_id)
        if approval is None or approval["status"] != ApprovalStatus.REJECTED.value:
            raise ValueError(f"Approval is not rejected: {approval_id}")
        stored_run = self.storage.get_task_run(approval["task_run_id"])
        if stored_run is None or stored_run["status"] != TaskStatus.WAITING_APPROVAL.value:
            raise ValueError("Approval does not belong to a waiting task run")
        task = self.storage.get_task(stored_run["task_id"])
        action_data = self.storage.get_action(approval["action_id"])
        if task is None or action_data is None:
            raise ValueError("Approval is missing its task or action")

        run = TaskRun(**stored_run)
        action = Action(**action_data)
        self.storage.update_task_run(run.id, status=TaskStatus.RUNNING.value, stop_reason=None)
        run.status = TaskStatus.RUNNING.value
        run.stop_reason = None
        self._publish_run_update(run.id)
        prior_actions = [
            self._action_trace(Action(**item))
            for item in self.storage.list_actions_for_run(run.id)
        ]
        prior_feedback = [
            self._feedback_from_row(item)
            for item in self.storage.list_feedback_for_run(run.id)
        ]
        return self._continue(
            task=task,
            run=run,
            start_round=action.round_index + 1,
            prior_actions=prior_actions,
            prior_feedback=prior_feedback,
            changed_files=self._changed_files_for_run(run.id),
        )

    def _continue(
        self,
        *,
        task: dict,
        run: TaskRun,
        start_round: int,
        prior_actions: list[dict] | None = None,
        prior_feedback: list[Feedback] | None = None,
        changed_files: set[str] | None = None,
    ) -> TaskRun:
        prior_actions = prior_actions or []
        prior_feedback = prior_feedback or []
        changed_files = changed_files or set()
        profile = TaskProfiler().profile(task["description"] or task["title"])
        if profile.out_of_scope:
            return self._finish(
                run,
                TaskStatus.STOPPED.value,
                f"out_of_scope: {profile.decomposition_reason}",
            )

        for round_index in range(start_round, run.max_repair_rounds):
            self.storage.update_task_run(run.id, current_round=round_index)
            self._publish_run_update(run.id)
            package = ContextEngine(self.repo_root, self.storage).build_package(
                task_run_id=run.id,
                round_index=round_index,
                task_request=task["description"] or task["title"],
            )
            context = self._context_for_package(package.items)
            try:
                action_text = self.llm.complete(
                    self._messages(task, profile, context, prior_actions, prior_feedback)
                )
            except LLMTimeoutError:
                return self._finish(run, TaskStatus.STOPPED.value, "model_timeout")
            except LLMClientError:
                return self._finish(run, TaskStatus.FAILED.value, "model_request_failed")
            action, schema_feedback = self.parser.parse(action_text)
            action.task_run_id = run.id
            action.round_index = round_index
            self.storage.create_action(action)
            self._publish_run_update(run.id)

            if action.schema_status == SchemaStatus.INVALID.value:
                prior_actions.append(self._action_trace(action))
                if schema_feedback is not None:
                    schema_feedback.task_run_id = run.id
                    schema_feedback.round_index = round_index
                    schema_feedback.locations = schema_feedback.locations or ["schema_validation"]
                    self.storage.create_feedback(schema_feedback)
                    self._publish_run_update(run.id)
                    prior_feedback.append(schema_feedback)
                if self.feedback_engine.should_stop_early(prior_feedback):
                    return self._finish(run, TaskStatus.STOPPED.value, "repeated_failure")
                continue

            if action.action_type == ActionType.FINISH.value:
                prior_actions.append(self._action_trace(action))
                if changed_files:
                    validation_feedback = self._run_validation(run.id, round_index)
                    prior_feedback.extend(validation_feedback)
                    if validation_feedback:
                        if self.feedback_engine.should_stop_early(prior_feedback):
                            return self._finish(run, TaskStatus.STOPPED.value, "repeated_failure")
                        continue
                return self._finish(run, TaskStatus.SUCCEEDED.value, "model_finished")

            guardrail = self.guardrail.evaluate(action)
            action.guardrail_status = guardrail.status
            self.storage.update_action_guardrail(action.id, guardrail.status)
            self._publish_run_update(run.id)
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
                self._publish_run_update(run.id)
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
                self._publish_run_update(run.id)
                prior_actions.append(self._action_trace(action))
                return self._wait_for_approval(run, "approval_required")

            result = self.dispatcher.dispatch(action, repo_root=self.repo_root)
            self._publish_run_update(run.id)
            changed_files.update(result.changed_files or [])
            prior_actions.append(self._action_trace(action))
            if self._should_validate_after(action):
                validation_feedback = self._run_validation(run.id, round_index)
                prior_feedback.extend(validation_feedback)
                if self.feedback_engine.should_stop_early(prior_feedback):
                    return self._finish(run, TaskStatus.STOPPED.value, "repeated_failure")

        return self._finish(run, TaskStatus.STOPPED.value, "max_repair_rounds")

    def _feedback_from_row(self, feedback: dict) -> Feedback:
        locations = feedback.get("locations")
        if isinstance(locations, str):
            try:
                locations = json.loads(locations)
            except json.JSONDecodeError:
                locations = []
        return Feedback(
            id=feedback["id"],
            task_run_id=feedback["task_run_id"],
            round_index=feedback["round_index"],
            source=feedback["source"],
            category=feedback["category"],
            summary=feedback["summary"],
            locations=locations if isinstance(locations, list) else [],
            raw_excerpt=feedback["raw_excerpt"],
            passed=bool(feedback["passed"]),
            created_at=feedback["created_at"],
        )

    def _changed_files_for_run(self, task_run_id: str) -> set[str]:
        changed_files: set[str] = set()
        for result in self.storage.list_tool_results_for_run(task_run_id):
            if not result["changed_files"]:
                continue
            try:
                paths = json.loads(result["changed_files"])
            except json.JSONDecodeError:
                continue
            if isinstance(paths, list):
                changed_files.update(path for path in paths if isinstance(path, str))
        return changed_files

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
            {"role": "system", "content": _ACTION_SYSTEM_PROMPT},
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
            self._publish_run_update(task_run_id)
            return [item]
        feedback: list[Feedback] = []
        for command in commands:
            item = self.feedback_engine.run_validation(command, self.repo_root)
            item.task_run_id = task_run_id
            item.round_index = round_index
            self.storage.create_feedback(item)
            self._publish_run_update(task_run_id)
            if self._validation_passed(item):
                continue
            feedback.append(item)
        return feedback

    def _validation_passed(self, feedback: Feedback) -> bool:
        return bool(getattr(feedback, "passed", False))

    def _should_validate_after(self, action) -> bool:
        return action.action_type in {
            ActionType.WRITE_FILE.value,
            ActionType.RUN_COMMAND.value,
        }

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
        self._publish_run_update(run.id)
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
        self._publish_run_update(run.id)
        return run

    def _publish_run_update(self, run_id: str) -> None:
        if self._event_publisher is not None:
            try:
                self._event_publisher(run_id)
            except Exception:
                pass
