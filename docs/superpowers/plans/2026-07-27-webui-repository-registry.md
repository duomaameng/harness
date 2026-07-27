# WebUI 仓库注册与切换 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 WebUI 在应用级配置中注册、切换、重命名和取消注册本地仓库，并保持每个仓库的 Harness 数据隔离。

**Architecture:** `RepositoryRegistry` 负责应用级 JSON 注册表、绝对路径规范化和当前仓库选择。WebUI 按请求从注册表取得当前仓库的 `CoreService`，并通过仓库 ID 路由执行选择、重命名和取消注册操作。

**Tech Stack:** Python 3.11、FastAPI、pytest、标准库 JSON 与 pathlib。

## Global Constraints

- 删除仓库仅取消应用级注册，绝不删除本地目录、`.git` 或 `.harness`。
- 重命名仅修改 WebUI 显示名称，绝不重命名本地目录或 Git 仓库。
- 仓库路径必须是存在的本地目录，并按规范化绝对路径去重。
- 每个仓库继续使用其自身的 `.harness` 存储，数据不得跨仓库混合。
- 所有新行为先有失败测试，再写最小实现。

---

### Task 1: 应用级仓库注册表

**Files:**
- Create: `harness/repository_registry.py`
- Modify: `tests/test_service_cli_api.py`

**Interfaces:**
- Produces `RepositoryRegistry(config_dir: Path)`。
- Produces `register(path: str | Path) -> dict[str, str]`、`list() -> list[dict[str, str]]`、`current() -> dict[str, str] | None`、`select(repository_id: str) -> dict[str, str]`、`rename(repository_id: str, name: str) -> dict[str, str]`、`remove(repository_id: str) -> dict[str, str] | None`。
- 注册记录的字段固定为 `id`、`path`、`name`；删除当前记录后 `current()` 返回剩余首项或 `None`。

- [ ] **Step 1: Write the failing test**

```python
def test_repository_registry_persists_switch_rename_and_safe_removal(tmp_path):
    config_dir = tmp_path / "app-config"
    first = tmp_path / "first-repo"
    second = tmp_path / "second-repo"
    first.mkdir()
    second.mkdir()

    registry = RepositoryRegistry(config_dir)
    first_item = registry.register(first)
    second_item = registry.register(second)
    registry.select(first_item["id"])
    registry.rename(first_item["id"], "First project")
    registry.remove(first_item["id"])

    restored = RepositoryRegistry(config_dir)
    assert restored.current() == second_item
    assert restored.list() == [second_item]
    assert first.exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_service_cli_api.py::test_repository_registry_persists_switch_rename_and_safe_removal -q -p no:cacheprovider`

Expected: FAIL because `harness.repository_registry.RepositoryRegistry` does not exist.

- [ ] **Step 3: Write minimal implementation**

```python
class RepositoryRegistry:
    def __init__(self, config_dir: Path) -> None:
        self.config_path = config_dir / "repositories.json"

    def register(self, path: str | Path) -> dict[str, str]:
        # Resolve and validate a directory, persist it, and make it current.
        ...
```

Implement JSON read/write, UUID repository IDs, validation, unique paths, selection, non-empty display-name updates, and safe removal with fallback current selection. Write JSON through a sibling temporary file then replace the target.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_service_cli_api.py::test_repository_registry_persists_switch_rename_and_safe_removal -q -p no:cacheprovider`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add harness/repository_registry.py tests/test_service_cli_api.py
git commit -m "feat: add application repository registry"
```

### Task 2: WebUI 仓库工作台集成

**Files:**
- Modify: `harness/webui.py`
- Modify: `harness/api.py`
- Modify: `tests/test_service_cli_api.py`

**Interfaces:**
- Consumes `RepositoryRegistry` from Task 1 and its `current`, `register`, `select`, `rename`, `remove` methods.
- `include_webui(..., registry: RepositoryRegistry | None = None)` registers the supplied default service repository on first startup.
- Produces POST routes `/ui/repositories`、`/ui/repositories/{repository_id}/select`、`/ui/repositories/{repository_id}/rename`、`/ui/repositories/{repository_id}/delete`。
- All existing WebUI task, run and approval routes resolve the active service for the request.

- [ ] **Step 1: Write the failing test**

```python
def test_webui_switches_registered_repositories_without_mixing_tasks(tmp_path):
    first = tmp_path / "first-repo"
    second = tmp_path / "second-repo"
    first.mkdir()
    second.mkdir()
    registry = RepositoryRegistry(tmp_path / "app-config")
    app = create_app(CoreService(first, llm=MockLLM([])), registry=registry)

    _endpoint(app, "/ui/repositories", "POST")({"path": str(second)})
    _endpoint(app, "/ui/tasks", "POST")({"title": "Only second"})
    html = _endpoint(app, "/", "GET")().body.decode("utf-8")

    assert str(second.resolve()) in html
    assert "Only second" in html
    assert CoreService(first, llm=MockLLM([])).list_tasks() == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_service_cli_api.py::test_webui_switches_registered_repositories_without_mixing_tasks -q -p no:cacheprovider`

Expected: FAIL because `create_app` does not accept `registry` and no repository routes exist.

- [ ] **Step 3: Write minimal implementation**

```python
def include_webui(app, service=None, *, repo_path=".", registry=None):
    registry = registry or RepositoryRegistry.default()
    registry.register(core.repo_path)

    def current_core() -> CoreService:
        current = registry.current()
        if current is None:
            raise HTTPException(status_code=400, detail="No repository selected")
        return services.setdefault(current["path"], CoreService(current["path"]))
```

Add the repository routes and sidebar forms/links. Render every registered repository with active state, its display name and path, and controls for select, rename and delete. When none is selected, render an add-repository panel; task creation returns 400 until a repository is selected. Pass the optional registry through `create_app` without changing existing callers.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_service_cli_api.py::test_webui_switches_registered_repositories_without_mixing_tasks -q -p no:cacheprovider`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add harness/api.py harness/webui.py tests/test_service_cli_api.py
git commit -m "feat: switch repositories in webui"
```

### Task 3: 项目台账

**Files:**
- Modify: `PLAN.md`
- Modify: `AGENT_LOG.md`

**Interfaces:**
- Consumes the completed registry and WebUI behavior from Tasks 1–2.
- Produces project-plan and implementation-log entries stating the application-level registry, safe deletion, display-name rename, and repository data isolation.

- [ ] **Step 1: Write the failing test**

No automated test: this task updates human-facing project records after the tested behavior from Tasks 1–2 is complete.

- [ ] **Step 2: Run test to verify it fails**

No test command: documentation task with no executable consumer.

- [ ] **Step 3: Write minimal implementation**

Add one concise `PLAN.md` scope/progress entry and one `AGENT_LOG.md` dated completion entry. State that deletion only unregisters a repository and that renaming changes a display alias only.

- [ ] **Step 4: Run test to verify it passes**

No test command: preserve the behavior verification evidence from Tasks 1–2.

- [ ] **Step 5: Commit**

```bash
git add PLAN.md AGENT_LOG.md
git commit -m "docs: record webui repository registry"
```
