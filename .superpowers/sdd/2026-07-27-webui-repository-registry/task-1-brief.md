# Task 1: 应用级仓库注册表

## 文件

- 创建：`harness/repository_registry.py`
- 修改：`tests/test_service_cli_api.py`

## 要求

实现 `RepositoryRegistry(config_dir: Path)`，并提供：

- `register(path: str | Path) -> dict[str, str]`
- `list() -> list[dict[str, str]]`
- `current() -> dict[str, str] | None`
- `select(repository_id: str) -> dict[str, str]`
- `rename(repository_id: str, name: str) -> dict[str, str]`
- `remove(repository_id: str) -> dict[str, str] | None`

每条记录必须包含 `id`、`path`、`name`。注册表保存在传入应用配置目录的 JSON 文件中；路径规范化为绝对路径、必须存在且是目录、不得重复。首个注册仓库为当前仓库。`register` 注册后将该仓库设为当前仓库。重命名只更新显示名称，名称不得为空。删除只从 JSON 注册表移除条目，不得删除本地目录、`.git` 或 `.harness`；删除当前仓库后选择剩余首项，若没有条目则没有当前仓库。写入必须通过同目录临时文件后替换目标文件。损坏 JSON 不得静默覆盖，应抛出可诊断异常。

## TDD 要求

1. 在 `tests/test_service_cli_api.py` 先新增一个只使用真实目录和真实注册表的失败测试，覆盖注册、选择、重命名、删除、重新实例化后的持久化，以及原目录仍存在。
2. 运行该单测并在报告中记录预期的失败输出；失败必须源自缺失实现。
3. 编写最小 `harness/repository_registry.py` 实现。
4. 重跑该单测并记录通过输出；仅在通过后做必要重构并重跑同一单测。
5. 提交该任务的代码与测试，提交信息为 `feat: add application repository registry`。

不要修改 WebUI、API、PLAN.md 或 AGENT_LOG.md；这些属于后续任务。
