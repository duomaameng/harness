from pathlib import Path

from harness.domain import ContextItemKind
from harness.repo_index import RepositoryIndex


def test_repository_index_maps_source_file_to_related_test():
    repo_root = Path(__file__).parent / "fixtures" / "sample_repo"

    items = RepositoryIndex(repo_root).index()

    source_items = [
        item
        for item in items
        if item.kind == ContextItemKind.CODE_STRUCTURE.value
        and item.source_path == "src/calculator.py"
    ]
    mappings = [
        item
        for item in items
        if item.kind == ContextItemKind.TEST_MAPPING.value
        and item.source_path == "src/calculator.py"
    ]

    assert source_items
    assert any(
        item.metadata and item.metadata.get("test_path") == "tests/test_calculator.py"
        and item.metadata.get("selection_reason")
        for item in mappings
    )


def test_repository_index_extracts_python_symbols_and_conventions():
    repo_root = Path(__file__).parent / "fixtures" / "sample_repo"

    items = RepositoryIndex(repo_root).index()

    assert any(item.symbol == "add" for item in items)
    assert any(
        item.kind == ContextItemKind.PROJECT_CONVENTION.value
        and item.source_path == "pyproject.toml"
        for item in items
    )


def test_repository_index_ignores_artifacts_and_summarizes_invalid_python(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "ignored.py").write_text("def ignored(): pass", encoding="utf-8")
    (tmp_path / "broken.py").write_text("def broken(:\n", encoding="utf-8")
    (tmp_path / "secret.bin").write_bytes(b"header\x00binary")

    items = RepositoryIndex(tmp_path).index()

    paths = {item.source_path for item in items}
    assert "broken.py" in paths
    assert ".git/ignored.py" not in paths
    assert "secret.bin" not in paths
    assert any(item.source_path == "broken.py" and item.symbol is None for item in items)
