from pathlib import Path

from harness.context_engine import ContextEngine
from harness.domain import ContextItemKind, MemoryEntry, MemoryKind, Task, TaskRun
from harness.storage import HarnessStorage


def test_context_package_includes_code_test_convention_and_memory_reasons(tmp_path):
    repo_root = Path(__file__).parent / "fixtures" / "sample_repo"
    storage = HarnessStorage(tmp_path)
    storage.init()
    task = storage.create_task(
        Task(
            title="Add calculator feature",
            description="Add a calculator feature and update pytest coverage.",
            repo_path=str(repo_root.resolve()),
        )
    )
    run = storage.create_task_run(TaskRun(task_id=task.id))
    storage.create_memory_entry(
        MemoryEntry(
            repo_path=str(repo_root.resolve()),
            kind=MemoryKind.HISTORICAL_DECISION.value,
            content="Calculator features should keep arithmetic behavior in src/calculator.py.",
            source_task_id=task.id,
            confidence=0.9,
        )
    )

    package = ContextEngine(
        repo_path=repo_root,
        storage=storage,
        token_budget=800,
    ).build_package(
        task_run_id=run.id,
        round_index=1,
        task_request="Add calculator feature and update tests.",
    )

    stored_item_ids = storage.get_package_items(package.id)
    assert stored_item_ids == package.items
    assert package.selection_reason
    assert package.token_estimate <= 800

    stored_items = [storage.get_context_item(item_id) for item_id in package.items]
    assert all(item is not None for item in stored_items)
    kinds = {item["kind"] for item in stored_items if item is not None}
    assert ContextItemKind.CODE_STRUCTURE.value in kinds
    assert ContextItemKind.TEST_MAPPING.value in kinds
    assert ContextItemKind.PROJECT_CONVENTION.value in kinds
    assert ContextItemKind.DECISION_MEMORY.value in kinds

    by_kind = {item["kind"]: item for item in stored_items if item is not None}
    for kind in (
        ContextItemKind.CODE_STRUCTURE.value,
        ContextItemKind.TEST_MAPPING.value,
        ContextItemKind.PROJECT_CONVENTION.value,
        ContextItemKind.DECISION_MEMORY.value,
    ):
        assert by_kind[kind]["metadata"] is not None
        assert "selection_reason" in by_kind[kind]["metadata"]
