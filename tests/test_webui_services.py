from pathlib import Path

from harness.llm import MockLLM
from harness.service import CoreService


def test_provider_creates_selected_repository_once_with_injected_factory(tmp_path):
    from harness.webui_services import WebUIServiceProvider

    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir()
    second.mkdir()
    created = []
    initial = CoreService(first, llm=MockLLM([]), validation_commands=[["pytest", "-q"]])

    def factory(path: Path) -> CoreService:
        service = CoreService(path, llm=MockLLM([]), validation_commands=[["pytest", "-q"]])
        created.append(service)
        return service

    provider = WebUIServiceProvider(initial, service_factory=factory)

    assert provider.for_repository(second) is provider.for_repository(second)
    assert len(created) == 1
    assert created[0].repo_path == second.resolve()
    assert created[0].validation_commands == [["pytest", "-q"]]


def test_provider_default_factory_preserves_initial_dependencies(tmp_path):
    from harness.webui_services import WebUIServiceProvider

    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir()
    second.mkdir()
    llm = MockLLM([])
    selected = WebUIServiceProvider(
        CoreService(first, llm=llm, validation_commands=["pytest -q"])
    ).for_repository(second)

    assert selected.llm is llm
    assert selected.validation_commands == ["pytest -q"]
