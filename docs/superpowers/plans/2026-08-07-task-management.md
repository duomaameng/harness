# 任务管理 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为非活动任务提供安全的重命名与删除功能，并让新任务标题从描述自动生成。

**Architecture:** 存储层在单一 SQLite 事务中删除任务的所有依赖记录；服务层统一判定活动运行。WebUI 复用仓库更多菜单和对话框模式，服务端从描述生成标题。

**Tech Stack:** Python 3、FastAPI、SQLite、服务端 HTML/CSS/JavaScript、pytest。

## Global Constraints

- 只有不存在 `running` 或 `waiting_approval` 运行记录的任务可重命名或删除。
- 删除只删除 Harness 数据；不得修改仓库工作区文件。
- 默认标题取描述规范化文本的前 32 个字符；空描述使用“未命名任务”。
- 重命名仅更新标题，描述和既有运行数据保持不变。

---

### Task 1: 存储与服务层任务管理

**Files:**
- Modify: `harness/storage.py:357-370`
- Modify: `harness/service.py:41-55`
- Test: `tests/test_service_cli_api.py`

**Interfaces:**
- Produces: `HarnessStorage.rename_task(task_id: str, title: str) -> dict | None`
- Produces: `HarnessStorage.delete_task(task_id: str) -> bool`
- Produces: `CoreService.rename_task(task_id: str, title: str) -> dict`
- Produces: `CoreService.delete_task(task_id: str) -> None`

- [ ] **Step 1: Write the failing service tests**

```python
def test_service_renames_inactive_task_and_rejects_active_task(tmp_path):
    service = CoreService(tmp_path, llm=MockLLM([]))
    task = service.create_task("Old", "description")
    assert service.rename_task(task.id, "New")["title"] == "New"
    active = service.create_task("Active", "description")
    service.storage.create_task_run(TaskRun(task_id=active.id, status="running"))
    with pytest.raises(ValueError, match="active"):
        service.rename_task(active.id, "Blocked")

def test_service_deletes_inactive_task_and_all_run_data(tmp_path):
    service = CoreService(tmp_path, llm=MockLLM([]))
    task = service.create_task("Delete", "description")
    run = service.storage.create_task_run(TaskRun(task_id=task.id, status="stopped"))
    action = service.storage.create_action(Action(task_run_id=run.id, action_type="finish"))
    service.storage.create_tool_result(ToolResult(action_id=action.id))
    service.delete_task(task.id)
    assert service.storage.get_task(task.id) is None
    assert service.storage.get_task_run(run.id) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_service_cli_api.py -k "renames_inactive_task or deletes_inactive_task" -q`

Expected: FAIL because `CoreService.rename_task` and `CoreService.delete_task` do not exist.

- [ ] **Step 3: Write minimal implementation**

Add `CoreService._task_has_active_run`, `rename_task`, and `delete_task`. Verify existence and reject a task that has a `running` or `waiting_approval` run. Add storage methods that update title and delete dependency rows in one connection transaction: approvals, tool results, actions, feedback, context-package items, context packages, runs, then task.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_service_cli_api.py -k "renames_inactive_task or deletes_inactive_task" -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add harness/storage.py harness/service.py tests/test_service_cli_api.py
git commit -m "feat: manage inactive tasks safely"
```

### Task 2: WebUI routes and automatic titles

**Files:**
- Modify: `harness/webui_routes.py:112-130,170-184`
- Test: `tests/test_service_cli_api.py`

**Interfaces:**
- Consumes: `CoreService.rename_task(task_id, title)` and `CoreService.delete_task(task_id)`.
- Produces: `POST /ui/tasks/{task_id}/rename`, `POST /ui/tasks/{task_id}/delete`, and `_title_from_description(payload) -> str`.

- [ ] **Step 1: Write the failing route tests**

```python
def test_webui_creates_title_from_description_prefix(tmp_path):
    service = CoreService(tmp_path, llm=MockLLM([]))
    api = create_app(service)
    result = _endpoint(api, "/ui/tasks", "POST")({"description": "x" * 40})
    assert service.storage.get_task(result["task_id"])["title"] == "x" * 32

def test_webui_task_management_routes_rename_and_delete_inactive_task(tmp_path):
    service = CoreService(tmp_path, llm=MockLLM([]))
    api = create_app(service)
    task = service.create_task("Before", "description")
    assert _endpoint(api, "/ui/tasks/{task_id}/rename", "POST")(task.id, {"title": "After"})["title"] == "After"
    assert _endpoint(api, "/ui/tasks/{task_id}/delete", "POST")(task.id).status_code == 303
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_service_cli_api.py -k "title_from_description_prefix or task_management_routes" -q`

Expected: FAIL because routes do not exist and a title is still required.

- [ ] **Step 3: Write minimal implementation**

Implement `_title_from_description`: normalize whitespace with `" ".join(description.split())`, return its first 32 characters or “未命名任务”. Both creation routes use it. Add rename and delete routes; translate service `ValueError` to `400`, and return `303 /` after a delete.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_service_cli_api.py -k "title_from_description_prefix or task_management_routes" -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add harness/webui_routes.py tests/test_service_cli_api.py
git commit -m "feat: add task management web routes"
```

### Task 3: 工作台任务菜单与表单

**Files:**
- Modify: `harness/webui.py:96-104,267-281,629-659,723-780`
- Test: `tests/test_service_cli_api.py`

**Interfaces:**
- Consumes: task action routes `rename` and `delete`.
- Produces: right-aligned `task-management-menu`, one rename dialog, and one delete dialog.

- [ ] **Step 1: Write the failing presentation test**

```python
def test_webui_task_items_show_right_aligned_menu_only_when_inactive(tmp_path):
    service = CoreService(tmp_path, llm=MockLLM([]))
    inactive = service.create_task("Inactive", "description")
    active = service.create_task("Active", "description")
    service.storage.create_task_run(TaskRun(task_id=active.id, status="waiting_approval"))
    html = _endpoint(create_app(service), "/", "GET")().body.decode("utf-8")
    assert f'data-task-id="{inactive.id}"' in html
    assert f'data-task-id="{active.id}"' not in html
    assert '<input class="input" name="title" required>' not in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_service_cli_api.py -k "task_items_show_right_aligned_menu" -q`

Expected: FAIL because task menu markup is absent and the create form still has a title input.

- [ ] **Step 3: Write minimal implementation**

Remove the title field. Render a task row with title/status on the left and a `task-management-menu` on the right only for tasks with no active run. Reuse the repository menu style, with the task menu margin reset and popup aligned right. Add one rename dialog and one delete confirmation dialog. Extend the existing JSON-form and dialog event code with `data-task-action` and `/ui/tasks/{id}/{action}`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_service_cli_api.py -k "task_items_show_right_aligned_menu" -q`

Expected: PASS.

- [ ] **Step 5: Run the relevant regression suite**

Run: `python -m pytest tests/test_service_cli_api.py -q`

Expected: PASS, including repository management and updated task creation tests.

- [ ] **Step 6: Commit**

```bash
git add harness/webui.py tests/test_service_cli_api.py
git commit -m "feat: add task menus to workbench"
```

## Self-Review

- Spec coverage: Task 1 enforces activity checks and cascade deletion; Task 2 makes titles server-authoritative; Task 3 supplies the right-side menu, dialogs, and title-less form.
- Placeholder scan: no TODO/TBD or implicit test steps remain.
- Type consistency: the route names and service method signatures are identical across all tasks.
