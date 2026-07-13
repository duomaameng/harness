"""Deterministic repository indexing for context retrieval."""

from __future__ import annotations

import ast
from pathlib import Path

from .domain import ContextItem, ContextItemKind


_IGNORED_DIRECTORIES = {
    ".git", ".harness", ".venv", "venv", "env", "__pycache__", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", ".cache", ".tox", ".nox", "build", "dist",
    "node_modules", "target", "out",
}
_SENSITIVE_FILE_NAMES = {
    ".npmrc", ".pypirc",
}
_SENSITIVE_SUFFIXES = {".key", ".pem", ".p12", ".pfx", ".crt", ".cer"}
_BINARY_SUFFIXES = {
    ".class", ".jar", ".war", ".zip", ".tar", ".gz", ".bin", ".exe", ".dll", ".so",
    ".dylib", ".pyc", ".pyo", ".png", ".jpg", ".jpeg", ".gif", ".pdf",
}
_CONVENTION_NAMES = {"README.md", "pyproject.toml", "package.json", "Cargo.toml", "Makefile", "tox.ini"}


class RepositoryIndex:
    """Build ContextItem records from a local repository without executing it."""

    def __init__(self, repo_path: str | Path, max_file_bytes: int = 1_000_000):
        self.repo_path = Path(repo_path).resolve()
        self.max_file_bytes = max_file_bytes

    def index(self) -> list[ContextItem]:
        files = self._files()
        items: list[ContextItem] = []
        source_symbols: dict[str, list[str]] = {}
        file_text: dict[str, str] = {}

        for path in files:
            relative = self._relative(path)
            text = self._read_text(path)
            if text is None:
                continue
            file_text[relative] = text
            if path.name in _CONVENTION_NAMES or path.name.startswith("."):
                items.append(self._convention_item(relative, text))

            if path.suffix.lower() == ".py":
                symbols, dependencies = self._python_signals(text)
                source_symbols[relative] = symbols
                items.append(self._file_item(
                    relative,
                    text,
                    f"Python module {relative}.",
                    {"language": "python", "dependencies": dependencies},
                ))
                if symbols:
                    for symbol in symbols:
                        items.append(ContextItem(
                            repo_path=str(self.repo_path),
                            kind=ContextItemKind.CODE_STRUCTURE.value,
                            source_path=relative,
                            symbol=symbol,
                            summary=f"Python symbol {symbol} in {relative}.",
                            metadata={"language": "python", "dependencies": dependencies},
                        ))
            else:
                items.append(self._file_item(relative, text, f"File {relative}."))

        tests = [(path, file_text[path]) for path in file_text if self._is_test(path)]
        test_references = {
            path: self._python_references(text) if Path(path).suffix.lower() == ".py" else set()
            for path, text in tests
        }
        sources = [path for path in file_text if not self._is_test(path)]
        for source in sources:
            source_stem = Path(source).stem.lower().removeprefix("test_")
            for test, text in tests:
                test_stem = Path(test).stem.lower().removeprefix("test_")
                symbols = source_symbols.get(source, [])
                references = test_references.get(test, set())
                symbol_hits = [symbol for symbol in symbols if symbol in references]
                if source_stem == test_stem or symbol_hits:
                    reasons = []
                    if source_stem == test_stem:
                        reasons.append("matching path stem")
                    if symbol_hits:
                        reasons.append("source symbol keyword: " + ", ".join(symbol_hits))
                    reason = " and ".join(reasons)
                    items.append(ContextItem(
                        repo_path=str(self.repo_path),
                        kind=ContextItemKind.TEST_MAPPING.value,
                        source_path=source,
                        summary=f"Related test {test} selected because of {reason}.",
                        metadata={"test_path": test, "selection_reason": reason},
                    ))
        return items

    scan = index

    def _files(self) -> list[Path]:
        result = []
        for path in self.repo_path.rglob("*"):
            try:
                relative_parts = path.relative_to(self.repo_path).parts
                resolved = path.resolve()
            except OSError:
                continue
            if (
                not path.is_file()
                or path.is_symlink()
                or not resolved.is_relative_to(self.repo_path)
                or any(part in _IGNORED_DIRECTORIES for part in relative_parts)
                or self._is_sensitive_file(path)
                or path.suffix.lower() in _BINARY_SUFFIXES
            ):
                continue
            result.append(path)
        return sorted(result, key=lambda path: self._relative(path))

    def _relative(self, path: Path) -> str:
        return path.relative_to(self.repo_path).as_posix()

    def _read_text(self, path: Path) -> str | None:
        try:
            if path.stat().st_size > self.max_file_bytes:
                return None
            data = path.read_bytes()
            if b"\x00" in data:
                return None
            return data.decode("utf-8")
        except (OSError, UnicodeDecodeError):
            return None

    def _file_item(
        self,
        relative: str,
        text: str,
        summary: str,
        metadata: dict | None = None,
    ) -> ContextItem:
        item_metadata = {"line_count": len(text.splitlines())}
        if metadata:
            item_metadata.update(metadata)
        return ContextItem(
            repo_path=str(self.repo_path),
            kind=ContextItemKind.CODE_STRUCTURE.value,
            source_path=relative,
            summary=summary,
            metadata=item_metadata,
        )

    def _convention_item(self, relative: str, text: str) -> ContextItem:
        return ContextItem(
            repo_path=str(self.repo_path),
            kind=ContextItemKind.PROJECT_CONVENTION.value,
            source_path=relative,
            summary=f"Project convention and repository guidance from {relative}.",
            content_ref=text,
            metadata={"selection_reason": f"recognized project convention file: {relative}"},
        )

    @staticmethod
    def _python_signals(text: str) -> tuple[list[str], list[str]]:
        try:
            tree = ast.parse(text)
        except SyntaxError:
            return [], []
        symbols = [
            node.name for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        ]
        dependencies: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                dependencies.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                dependencies.add(node.module.split(".", 1)[0])
        return symbols, sorted(dependencies)

    @staticmethod
    def _python_references(text: str) -> set[str]:
        try:
            tree = ast.parse(text)
        except SyntaxError:
            return set()
        references: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                references.add(node.id)
            elif isinstance(node, ast.Attribute):
                references.add(node.attr)
        return references

    @staticmethod
    def _is_sensitive_file(path: Path) -> bool:
        name = path.name.lower()
        return (
            name in _SENSITIVE_FILE_NAMES
            or name == ".env"
            or name.startswith(".env.")
            or path.suffix.lower() in _SENSITIVE_SUFFIXES
        )

    @staticmethod
    def _is_test(relative: str) -> bool:
        path = Path(relative)
        return path.name.startswith("test_") or path.name.endswith("_test.py") or "tests" in path.parts
