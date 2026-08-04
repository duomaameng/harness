"""Service provider for the WebUI's selected repository."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from harness.service import CoreService


class WebUIServiceProvider:
    """Create and cache a service for each selected repository."""

    def __init__(
        self,
        initial_service: CoreService,
        service_factory: Callable[[Path], CoreService] | None = None,
    ) -> None:
        self._services = {initial_service.repo_path: initial_service}
        self._service_factory = service_factory or self._default_factory(initial_service)

    def for_repository(self, repo_path: str | Path) -> CoreService:
        path = Path(repo_path).resolve()
        if path not in self._services:
            self._services[path] = self._service_factory(path)
        return self._services[path]

    @staticmethod
    def _default_factory(initial_service: CoreService) -> Callable[[Path], CoreService]:
        return lambda path: CoreService(
            path,
            llm=initial_service.llm,
            validation_commands=initial_service.validation_commands,
        )
