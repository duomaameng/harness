# Task 2: WebUI 仓库工作台集成

## 文件
- 修改：`harness/webui.py`、`harness/api.py`、`tests/test_service_cli_api.py`

## 要求

使用 Task 1 的 `RepositoryRegistry`。让 `create_app` 和 `include_webui` 接受可选 registry；首次启动注册传入的默认服务仓库。WebUI 每个请求均取得当前注册仓库对应的 `CoreService`，服务可缓存但不同路径必须隔离。

新增：
- `POST /ui/repositories`：注册路径并设为当前。
- `POST /ui/repositories/{repository_id}/select`：选择并 303 返回工作台。
- `POST /ui/repositories/{repository_id}/rename`：更新非空显示名。
- `POST /ui/repositories/{repository_id}/delete`：仅取消注册并 303 返回工作台。

工作台侧栏必须显示全部仓库、显示名、路径、当前状态、选择、重命名、删除控件。无当前仓库时呈现添加仓库提示；任务创建/执行在此时 400。现有 API 调用方不传 registry 时仍可工作。运行详情与审批必须使用当前服务，不能跨仓库访问。

## TDD

先在 `tests/test_service_cli_api.py` 写失败的真实集成测试：用临时 registry 创建 first/second 仓库；注册 second、在 second 创建任务；断言工作台显示 second 与该任务，且 first 的 `CoreService.list_tasks()` 为空。再补充重命名和删除路由测试。以 `C:\Users\duoma\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m pytest tests/test_service_cli_api.py -q -k webui_repository -p no:cacheprovider` 运行 RED，失败须源自缺少 routes/registry 参数；写最小实现后运行 GREEN，必要重构后再运行。提交：`feat: switch repositories in webui`。只改指定文件。完整输出写 `task-2-report.md`，最终只回复状态、commit、测试结果、疑虑。
