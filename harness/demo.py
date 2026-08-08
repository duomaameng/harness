"""Offline, deterministic demonstration of the harness control loop."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from harness.domain import Task, TaskRun
from harness.llm import MockLLM
from harness.memory import MemoryStore
from harness.runner import AgentRunner
from harness.storage import HarnessStorage


@dataclass(frozen=True)
class DemoResult:
    """Inspectable evidence produced by the deterministic MockLLM demo."""

    storage: HarnessStorage
    run: TaskRun
    llm: MockLLM


def run_mockllm_demo(repo_root: str | Path) -> DemoResult:
    """Run a safe, offline repair sequence against a disposable calculator repository."""
    repo = Path(repo_root).resolve()
    storage = HarnessStorage(repo)
    storage.init()
    MemoryStore(storage).record(
        repo_path=str(repo),
        kind="module_responsibility",
        content="The calculator module must preserve correct addition behavior.",
        confidence=1.0,
    )
    task = storage.create_task(Task(
        title="Repair calculator addition",
        description="Repair calculator addition and run calculator tests safely.",
        repo_path=str(repo),
    ))
    llm = MockLLM([
        '{"thought_summary":"remove the repository","action":"run_command",'
        '"args":{"command":"rm -rf ."}}',
        '{"thought_summary":"attempt implementation","action":"write_file",'
        '"args":{"path":"src/calculator.py","content":"def add(left: int, right: int) -> int:\\n    return left - right\\n\\ndef divide(left: float, right: float) -> float:\\n    if right == 0:\\n        raise ValueError(\\\"right must not be zero\\\")\\n    return left / right\\n"}}',
        '{"thought_summary":"repair implementation","action":"write_file",'
        '"args":{"path":"src/calculator.py","content":"def add(left: int, right: int) -> int:\\n    return left + right\\n\\ndef divide(left: float, right: float) -> float:\\n    if right == 0:\\n        raise ValueError(\\\"right must not be zero\\\")\\n    return left / right\\n"}}',
        '{"thought_summary":"all evidence collected","action":"finish",'
        '"args":{"summary":"Calculator repair validated."}}',
    ])
    run = AgentRunner(storage=storage, llm=llm, repo_root=repo).run(task.id, max_rounds=6)
    return DemoResult(storage=storage, run=run, llm=llm)
