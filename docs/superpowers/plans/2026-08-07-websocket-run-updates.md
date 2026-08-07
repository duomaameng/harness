# WebSocket 运行更新 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让运行详情页通过 WebSocket 自动刷新，并为工作台实时列表准备同一套仓库频道。

**Architecture:** 新增进程内事件中心，向运行和仓库订阅者发送不含业务内容的刷新提示。写入运行可见状态的服务与路由发布事件；详情页收到提示后刷新 HTML，工作台频道仅完成后端和测试准备。

**Tech Stack:** FastAPI WebSocket、asyncio、Python、服务端 HTML/JavaScript、pytest。

## Global Constraints

- 仅单进程进程内广播；不引入 Redis 或新依赖。
- 事件不包含任务描述、动作参数、上下文或密钥。
- 运行详情 WebSocket 必须验证运行存在且属于当前仓库。
- 断线自动重连，浏览器无法连接时保留手动刷新能力。

---

### Task 1: 事件中心与运行事件发布

**Files:**
- Create: `harness/webui_events.py`
- Modify: `harness/service.py`
- Modify: `harness/runner.py`
- Test: `tests/test_service_cli_api.py`

- [ ] **Step 1: Write failing event-hub tests**

```python
async def test_webui_event_hub_delivers_run_and_repository_refresh_events():
    hub = WebUIEventHub()
    queue = hub.subscribe_run("repo", "run-1")
    hub.publish_run_update("repo", "run-1")
    assert (await queue.get())["type"] == "run_updated"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_service_cli_api.py -k webui_event_hub -q`

Expected: FAIL because `WebUIEventHub` does not exist.

- [ ] **Step 3: Implement the minimal event hub and publication hooks**

Create `WebUIEventHub` with thread-safe loop-bound queues, `subscribe_run`, `subscribe_repository`, unsubscribe methods, and `publish_run_update`. Payload contains only type, run ID, repository key, and timestamp. Pass an optional publisher callback from `CoreService` into `AgentRunner`; publish after status/action/feedback/approval-visible changes. Keep the callback optional so CLI/API behavior is unchanged.

- [ ] **Step 4: Run focused tests to verify they pass**

Run: `python -m pytest --basetemp .pytest-websocket tests/test_service_cli_api.py -k webui_event_hub -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add harness/webui_events.py harness/service.py harness/runner.py tests/test_service_cli_api.py
git commit -m "feat: publish webui run updates"
```

### Task 2: WebSocket routes and detail-page client

**Files:**
- Modify: `harness/webui_routes.py`
- Modify: `harness/webui.py`
- Test: `tests/test_service_cli_api.py`

- [ ] **Step 1: Write failing WebSocket and HTML tests**

```python
def test_webui_run_detail_includes_reconnecting_websocket_client(tmp_path):
    html = _endpoint(create_app(CoreService(tmp_path, llm=MockLLM([]))), "/", "GET")().body.decode()
    assert "/ui/ws/runs/" in _render_run_detail(...)
    assert "WebSocket" in _render_run_detail(...)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_service_cli_api.py -k reconnecting_websocket -q`

Expected: FAIL because routes and script are absent.

- [ ] **Step 3: Implement guarded routes and refresh client**

Add `/ui/ws/runs/{run_id}` and `/ui/ws/workbench` routes. Accept only valid same-repository connections, subscribe, await messages, and unsubscribe on disconnect. In detail HTML emit a script that derives `ws`/`wss`, connects to its run URL, reloads once on a `run_updated` message, and schedules bounded reconnect delay on close. Do not send sensitive data in JavaScript or events.

- [ ] **Step 4: Run focused tests to verify they pass**

Run: `python -m pytest --basetemp .pytest-websocket tests/test_service_cli_api.py -k "websocket or reconnecting" -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add harness/webui_routes.py harness/webui.py tests/test_service_cli_api.py
git commit -m "feat: refresh run details over websocket"
```

### Task 3: Repository-channel readiness and regression verification

**Files:**
- Modify: `harness/webui_events.py`
- Modify: `harness/webui_routes.py`
- Test: `tests/test_service_cli_api.py`

- [ ] **Step 1: Write failing repository-channel isolation test**

```python
async def test_webui_event_hub_isolates_repository_subscribers():
    hub = WebUIEventHub()
    first = hub.subscribe_repository("repo-a")
    second = hub.subscribe_repository("repo-b")
    hub.publish_run_update("repo-a", "run-1")
    assert (await first.get())["run_id"] == "run-1"
    assert second.empty()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_service_cli_api.py -k isolates_repository_subscribers -q`

Expected: FAIL because repository subscribers are not yet notified.

- [ ] **Step 3: Publish repository refresh events and validate workbench connection**

Make `publish_run_update` also notify repository subscribers with an opaque `workbench_updated` event. Verify `/ui/ws/workbench` subscribes to only the selected repository. Do not add a workbench browser script in this phase.

- [ ] **Step 4: Run full regression suite**

Run: `python -m pytest --basetemp .pytest-websocket tests/test_service_cli_api.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add harness/webui_events.py harness/webui_routes.py tests/test_service_cli_api.py
git commit -m "feat: prepare workbench websocket channel"
```

## Self-Review

- The three tasks cover delivery, secure WebSocket routing/client refresh, and repository-scoped workbench readiness.
- No task introduces external infrastructure or event payload data beyond opaque identifiers.
- Route names and event types match the approved design.
