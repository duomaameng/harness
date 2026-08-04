# 仓库卡片操作交互实施计划

> **供代理执行：** 必须使用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 逐任务实施。步骤以复选框（`- [ ]`）记录进度。

**目标：** 将始终显示的仓库重命名/删除控件替换为无障碍的更多菜单，以及重命名和移除弹窗流程。

**架构：** 保持既有 FastAPI 路由和仓库注册表不变。仅修改 `harness/webui.py` 中服务端渲染的侧栏标记、内嵌 CSS 与浏览器端表单提交逻辑；沿用现有 WebUI 集成测试模块保护渲染契约。

**技术栈：** Python、FastAPI 服务端渲染 HTML/CSS/JavaScript、pytest。

## 全局约束

- 不修改 `/ui/repositories/{repository_id}/rename` 或 `/ui/repositories/{repository_id}/delete` 的路由行为。
- 移除确认必须明确说明：操作仅从工作台移除仓库，绝不删除本地文件。
- 仓库卡片仍可被选择，且管理控件不会触发卡片选择。
- 重命名在弹窗中输入，预填当前名称并自动聚焦；Esc 取消，Enter 提交。
- 更多菜单触发器和菜单操作必须具备无障碍标签。

---

### 任务 1：仓库卡片更多菜单与管理弹窗

**文件：**

- 修改：`tests/test_service_cli_api.py:186-207`
- 修改：`harness/webui.py:212-240, 582-600, 703-713`
- 修改：`PLAN.md`
- 修改：`AGENT_LOG.md`

**接口：**

- 使用：既有 POST 路由 `/ui/repositories/{repository_id}/rename` 和 `/ui/repositories/{repository_id}/delete`。
- 产出：渲染后的仓库卡片包含 `repo-management-menu`（其触发器的标签为 `Repository management`）、`rename-repository-dialog` 与 `delete-repository-dialog`；继续使用原有 JSON 表单提交契约。

- [ ] **步骤 1：编写失败测试**

```python
def test_webui_repository_card_uses_overflow_menu_and_management_dialogs(tmp_path):
    # 创建两个仓库并渲染工作台
    assert 'class="repo-management-menu"' in html
    assert 'aria-label="Repository management"' in html
    assert 'id="rename-repository-dialog"' in html
    assert 'id="delete-repository-dialog"' in html
    assert 'Remove from workbench only. Local files are never deleted.' in html
    assert 'class="repository-json-form"' not in sidebar_markup
```

- [ ] **步骤 2：运行测试并确认失败**

运行：`python -m pytest tests/test_service_cli_api.py::test_webui_repository_card_uses_overflow_menu_and_management_dialogs -q -p no:cacheprovider`

预期：失败。现有侧栏会渲染可见的重命名输入框和 Rename/Delete 按钮，但没有菜单或弹窗标记。

- [ ] **步骤 3：编写最小实现**

```python
# 每张仓库卡片渲染带标签的 details/summary 更多菜单。
# 页面级只渲染两份 <dialog>，由被点击操作的数据填充。
# 弹窗表单继续使用现有 JSON fetch 提交；菜单点击不得触发卡片选择。
# 使用 dialog.showModal()、close() 和 focus()。
```

- [ ] **步骤 4：运行测试并确认通过**

运行：`python -m pytest tests/test_service_cli_api.py::test_webui_repository_card_uses_overflow_menu_and_management_dialogs -q -p no:cacheprovider`

预期：通过。

- [ ] **步骤 5：重构并重新运行聚焦测试**

保持管理标记和事件绑定小而职责清晰；保留既有仓库添加表单行为。

运行：`python -m pytest tests/test_service_cli_api.py::test_webui_repository_card_uses_overflow_menu_and_management_dialogs -q -p no:cacheprovider`

预期：通过。

- [ ] **步骤 6：更新项目账本并提交**

将 UI 行为与测试证据追加至 `PLAN.md` 和 `AGENT_LOG.md`，然后提交功能、测试、计划和账本文件。
