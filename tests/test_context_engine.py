from pathlib import Path
import json

import pytest

from harness.context_engine import ContextEngine
from harness.domain import ContextItemKind, MemoryEntry, MemoryKind, Task, TaskRun
from harness.storage import HarnessStorage


def _storage_with_run(tmp_path, repo_root):
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
    return storage, task, run


def test_context_package_includes_code_test_convention_and_memory_reasons(tmp_path):
    repo_root = Path(__file__).parent / "fixtures" / "sample_repo"
    storage, task, run = _storage_with_run(tmp_path, repo_root)
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


def test_context_items_preserve_score_source_and_dependency_reason(tmp_path):
    repo_root = Path(__file__).parent / "fixtures" / "sample_repo"
    storage, task, run = _storage_with_run(tmp_path, repo_root)
    storage.create_memory_entry(
        MemoryEntry(
            repo_path=str(repo_root.resolve()),
            kind=MemoryKind.HISTORICAL_DECISION.value,
            content="Calculator features should keep arithmetic behavior in src/calculator.py.",
            source_task_id=task.id,
            confidence=0.9,
        )
    )

    package = ContextEngine(repo_root, storage, token_budget=800).build_package(
        task_run_id=run.id,
        round_index=1,
        task_request="Use pathlib dependency in calculator tests.",
    )

    stored_items = [storage.get_context_item(item_id) for item_id in package.items]
    test_item = next(
        item for item in stored_items
        if item["kind"] == ContextItemKind.CODE_STRUCTURE.value
        and item["source_path"] == "tests/test_calculator.py"
    )

    metadata = json.loads(test_item["metadata"])
    assert metadata["score"] > 0
    assert metadata["source"] == ContextItemKind.CODE_STRUCTURE.value
    assert "pathlib" in metadata["selection_reason"]


def test_context_engine_does_not_select_unmatched_memory(tmp_path):
    repo_root = Path(__file__).parent / "fixtures" / "sample_repo"
    storage, task, run = _storage_with_run(tmp_path, repo_root)
    storage.create_memory_entry(
        MemoryEntry(
            repo_path=str(repo_root.resolve()),
            kind=MemoryKind.HISTORICAL_DECISION.value,
            content="Release notes are drafted from the changelog.",
            source_task_id=task.id,
            confidence=0.8,
        )
    )

    package = ContextEngine(repo_root, storage, token_budget=800).build_package(
        task_run_id=run.id,
        round_index=1,
        task_request="Add calculator feature and update tests.",
    )

    kinds = [
        storage.get_context_item(item_id)["kind"]
        for item_id in package.items
    ]
    assert ContextItemKind.DECISION_MEMORY.value not in kinds


@pytest.mark.parametrize(
    "memory_kind",
    [
        MemoryKind.MODULE_RESPONSIBILITY,
        MemoryKind.PROJECT_CONVENTION,
        MemoryKind.HISTORICAL_DECISION,
        MemoryKind.REJECTED_ALTERNATIVE,
        MemoryKind.FAILURE_PATTERN,
        MemoryKind.TASK_SUMMARY,
    ],
)
def test_context_engine_includes_matching_stored_memory_kinds(tmp_path, memory_kind):
    repo_root = Path(__file__).parent / "fixtures" / "sample_repo"
    storage, task, run = _storage_with_run(tmp_path, repo_root)
    storage.create_memory_entry(
        MemoryEntry(
            repo_path=str(repo_root.resolve()),
            kind=memory_kind.value,
            content="Calculator tests fail when divide by zero is not handled.",
            source_task_id=task.id,
            confidence=0.8,
        )
    )

    package = ContextEngine(repo_root, storage, token_budget=800).build_package(
        task_run_id=run.id,
        round_index=1,
        task_request="Fix calculator divide by zero tests.",
    )

    memory_items = [
        storage.get_context_item(item_id)
        for item_id in package.items
        if storage.get_context_item(item_id)["kind"] == ContextItemKind.DECISION_MEMORY.value
    ]
    assert memory_items
    metadata = json.loads(memory_items[0]["metadata"])
    assert metadata["memory_kind"] == memory_kind.value


def test_budget_trimming_prefers_task_critical_code_over_memory(tmp_path):
    repo_root = Path(__file__).parent / "fixtures" / "sample_repo"
    storage, task, run = _storage_with_run(tmp_path, repo_root)
    storage.create_memory_entry(
        MemoryEntry(
            repo_path=str(repo_root.resolve()),
            kind=MemoryKind.HISTORICAL_DECISION.value,
            content="calculator memory note",
            source_task_id=task.id,
            confidence=0.9,
        )
    )

    package = ContextEngine(repo_root, storage, token_budget=220).build_package(
        task_run_id=run.id,
        round_index=1,
        task_request="Add calculator feature and update tests.",
    )

    items = [storage.get_context_item(item_id) for item_id in package.items]
    assert any(item["source_path"] == "src/calculator.py" for item in items)
    assert all(item["kind"] != ContextItemKind.DECISION_MEMORY.value for item in items)


def test_budget_trimming_exhausts_code_and_tests_before_memory(tmp_path):
    repo_root = Path(__file__).parent / "fixtures" / "sample_repo"
    storage, task, run = _storage_with_run(tmp_path, repo_root)
    storage.create_memory_entry(
        MemoryEntry(
            repo_path=str(repo_root.resolve()),
            kind=MemoryKind.HISTORICAL_DECISION.value,
            content="calculator memory note",
            source_task_id=task.id,
            confidence=0.9,
        )
    )

    package = ContextEngine(repo_root, storage, token_budget=190).build_package(
        task_run_id=run.id,
        round_index=1,
        task_request="Add calculator feature and update tests.",
    )

    items = [storage.get_context_item(item_id) for item_id in package.items]
    assert any(item["source_path"] == "src/calculator.py" for item in items)
    assert all(item["kind"] != ContextItemKind.DECISION_MEMORY.value for item in items)
