"""Deterministic proof that the core harness mechanisms work together."""

import json
import shutil
from pathlib import Path

from harness.demo import run_mockllm_demo
from harness.domain import ContextItemKind, GuardrailDecision, TaskStatus


def test_mockllm_demo_context_guardrail_feedback_repair_and_memory(tmp_path: Path):
    """A broken repair sequence must be blocked, diagnosed, repaired, and remembered."""
    fixture_repo = Path(__file__).parent / "fixtures" / "sample_repo"
    demo_repo = tmp_path / "demo-repo"
    shutil.copytree(fixture_repo, demo_repo)

    result = run_mockllm_demo(demo_repo)

    assert result.run.status == TaskStatus.SUCCEEDED.value
    assert len(result.llm.requests) == 4
    packages = result.storage._fetchall(
        "SELECT * FROM context_package WHERE task_run_id=? ORDER BY round_index",
        (result.run.id,),
    )
    assert packages
    first_package_items = [
        result.storage.get_context_item(item_id)
        for item_id in result.storage.get_package_items(packages[0]["id"])
    ]
    selected_memory = next(
        item for item in first_package_items
        if item is not None and item["kind"] == ContextItemKind.DECISION_MEMORY.value
    )
    first_model_context = json.loads(result.llm.requests[0][1]["content"])["context"]
    prompted_memory = next(
        item for item in first_model_context
        if item["kind"] == ContextItemKind.DECISION_MEMORY.value
    )
    assert prompted_memory["summary"] == selected_memory["summary"]
    assert any(
        action["guardrail_status"] == GuardrailDecision.DENY.value
        for action in result.storage.list_actions_for_run(result.run.id)
    )
    feedback = result.storage.list_feedback_for_run(result.run.id)
    assert any(item["category"] == "unsafe_action" for item in feedback)
    actions = result.storage.list_actions_for_run(result.run.id)
    failed_write = next(
        item for item in actions
        if item["action_type"] == "write_file" and item["round_index"] == 1
    )
    repair_write = next(
        item for item in actions
        if item["action_type"] == "write_file" and item["round_index"] == 2
    )
    failed_validation = next(
        item for item in feedback
        if item["round_index"] == failed_write["round_index"]
    )
    repaired_validation = next(
        item for item in feedback
        if item["round_index"] == repair_write["round_index"]
    )
    assert failed_validation["source"] == "test"
    assert not failed_validation["passed"]
    assert repaired_validation["source"] == "test"
    assert repaired_validation["passed"]
    repair_content = json.loads(repair_write["args_json"])["content"]
    assert (demo_repo / "src" / "calculator.py").read_text(encoding="utf-8") == repair_content

    audit_events = [
        json.loads(line)
        for line in result.storage.audit_path.read_text(encoding="utf-8").splitlines()
    ]
    assert any(event["type"] == "guardrail.blocked" for event in audit_events)
