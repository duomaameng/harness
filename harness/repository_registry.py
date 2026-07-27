"""Persistent application-level registry for local repositories."""

from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import uuid4


class RepositoryRegistry:
    """Store repository registrations outside the repositories themselves."""

    _FILENAME = "repositories.json"

    def __init__(self, config_dir: Path):
        self.config_dir = Path(config_dir)
        self.path = self.config_dir / self._FILENAME

    def register(self, path: str | Path) -> dict[str, str]:
        repository_path = Path(path).expanduser().resolve()
        if not repository_path.is_dir():
            raise ValueError(f"Repository path must be an existing directory: {repository_path}")

        state = self._read()
        normalized_path = str(repository_path)
        if any(item["path"] == normalized_path for item in state["repositories"]):
            raise ValueError(f"Repository path is already registered: {normalized_path}")

        repository = {
            "id": str(uuid4()),
            "path": normalized_path,
            "name": repository_path.name,
        }
        state["repositories"].append(repository)
        state["current_repository_id"] = repository["id"]
        self._write(state)
        return repository

    def list(self) -> list[dict[str, str]]:
        return self._read()["repositories"]

    def current(self) -> dict[str, str] | None:
        state = self._read()
        return self._find(state, state["current_repository_id"])

    def select(self, repository_id: str) -> dict[str, str]:
        state = self._read()
        repository = self._required(state, repository_id)
        state["current_repository_id"] = repository_id
        self._write(state)
        return repository

    def rename(self, repository_id: str, name: str) -> dict[str, str]:
        if not name.strip():
            raise ValueError("Repository name must not be empty")

        state = self._read()
        repository = self._required(state, repository_id)
        repository["name"] = name.strip()
        self._write(state)
        return repository

    def remove(self, repository_id: str) -> dict[str, str] | None:
        state = self._read()
        repository = self._find(state, repository_id)
        if repository is None:
            return None

        state["repositories"].remove(repository)
        if state["current_repository_id"] == repository_id:
            state["current_repository_id"] = (
                state["repositories"][0]["id"] if state["repositories"] else None
            )
        self._write(state)
        return repository

    def _read(self) -> dict[str, list[dict[str, str]] | str | None]:
        if not self.path.exists():
            return {"repositories": [], "current_repository_id": None}
        try:
            with self.path.open(encoding="utf-8") as file:
                state = json.load(file)
        except json.JSONDecodeError as error:
            raise ValueError(f"Repository registry contains invalid JSON: {self.path}") from error

        if not isinstance(state, dict) or not isinstance(state.get("repositories"), list):
            raise ValueError(f"Repository registry has invalid structure: {self.path}")
        return state

    def _write(self, state: dict[str, list[dict[str, str]] | str | None]) -> None:
        self.config_dir.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=self.config_dir, delete=False
        ) as temporary_file:
            json.dump(state, temporary_file, ensure_ascii=False, indent=2)
            temporary_file.write("\n")
            temporary_path = Path(temporary_file.name)
        os.replace(temporary_path, self.path)

    @staticmethod
    def _find(
        state: dict[str, list[dict[str, str]] | str | None], repository_id: str | None
    ) -> dict[str, str] | None:
        return next(
            (
                item
                for item in state["repositories"]
                if item["id"] == repository_id
            ),
            None,
        )

    def _required(
        self, state: dict[str, list[dict[str, str]] | str | None], repository_id: str
    ) -> dict[str, str]:
        repository = self._find(state, repository_id)
        if repository is None:
            raise ValueError(f"Unknown repository id: {repository_id}")
        return repository
