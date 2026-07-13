import os
from pathlib import Path

import pytest

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


def test_repository_index_ignores_sensitive_dotenv_files(tmp_path):
    (tmp_path / ".env").write_text("OPENAI_API_KEY=sk-test-secret\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Sample\n", encoding="utf-8")

    items = RepositoryIndex(tmp_path).index()

    assert all(item.source_path != ".env" for item in items)
    assert all("sk-test-secret" not in (item.content_ref or "") for item in items)


def test_repository_index_records_python_import_dependency_signals(tmp_path):
    (tmp_path / "app.py").write_text("import json\nfrom pathlib import Path\n", encoding="utf-8")

    items = RepositoryIndex(tmp_path).index()

    app_items = [item for item in items if item.source_path == "app.py"]
    dependencies = {
        dependency
        for item in app_items
        for dependency in (item.metadata or {}).get("dependencies", [])
    }
    assert {"json", "pathlib"}.issubset(dependencies)


def test_repository_index_emits_module_summary_for_symbol_bearing_python(tmp_path):
    (tmp_path / "app.py").write_text("import json\n\ndef add(a, b):\n    return a + b\n", encoding="utf-8")

    items = RepositoryIndex(tmp_path).index()

    assert any(
        item.source_path == "app.py"
        and item.kind == ContextItemKind.CODE_STRUCTURE.value
        and item.symbol is None
        and (item.metadata or {}).get("dependencies") == ["json"]
        for item in items
    )


def test_repository_index_skips_sensitive_dotfile_variants(tmp_path):
    for name in [".env.test", ".npmrc", ".pypirc"]:
        (tmp_path / name).write_text("token=secret\n", encoding="utf-8")

    items = RepositoryIndex(tmp_path).index()

    paths = {item.source_path for item in items}
    assert ".env.test" not in paths
    assert ".npmrc" not in paths
    assert ".pypirc" not in paths
    assert all("secret" not in (item.content_ref or "") for item in items)


def test_repository_index_skips_symlinked_files(tmp_path):
    outside = tmp_path.parent / "outside-secret.txt"
    outside.write_text("outside secret", encoding="utf-8")
    link = tmp_path / "linked.py"
    try:
        os.symlink(outside, link)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")

    items = RepositoryIndex(tmp_path).index()

    assert all(item.source_path != "linked.py" for item in items)
    assert all("outside secret" not in (item.content_ref or item.summary) for item in items)


def test_repository_index_skips_oversized_files(tmp_path):
    (tmp_path / "large.py").write_text("x" * 20, encoding="utf-8")

    items = RepositoryIndex(tmp_path, max_file_bytes=10).index()

    assert all(item.source_path != "large.py" for item in items)


def test_repository_index_avoids_substring_false_positive_test_mapping(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "src" / "math_ops.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    (tmp_path / "tests" / "test_strings.py").write_text(
        "def test_text():\n    assert 'address' == 'address'\n",
        encoding="utf-8",
    )

    items = RepositoryIndex(tmp_path).index()

    assert not any(
        item.kind == ContextItemKind.TEST_MAPPING.value
        and item.source_path == "src/math_ops.py"
        and (item.metadata or {}).get("test_path") == "tests/test_strings.py"
        for item in items
    )
