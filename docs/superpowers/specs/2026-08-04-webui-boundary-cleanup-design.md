# WebUI 职责边界清理设计

## 目标

修复 WebUI 切换仓库时丢失配置依赖的问题；将展示以外的职责从 `harness/webui.py` 移出；补充 HTTP 层回归测试；移除审查发现的、非产品交付物的过程文件。

## 范围

本次修改处理审查问题 1、4、5，以及由此产生的 WebUI SRP/DIP 问题。不移除仓库注册功能，也不实现独立缺失的 Docker、CI、README 和端到端演示交付物。

## 架构

### 服务提供器

新增 `harness/webui_services.py`，定义 `WebUIServiceProvider`，专门维护“已注册仓库路径到 `CoreService`”的映射。

- 以初始服务和可选 `service_factory: Callable[[Path], CoreService]` 初始化。
- 初始仓库路径始终返回原服务。
- 访问其他已选仓库时，先查询缓存；仅在未命中时调用工厂，再缓存结果。
- 默认工厂以原服务的 LLM 与验证命令配置创建 `CoreService`。调用方如需每个仓库使用独立依赖，可传入自己的工厂。

这样依赖创建变为显式行为，WebUI 不再自行选择提供器或丢弃调用方提供的 MockLLM 配置。

### 路由模块

新增 `harness/webui_routes.py`，承载 `include_webui`：注册 HTTP 路由、校验请求载荷、调用 `RepositoryRegistry` 和 `WebUIServiceProvider`，并将 HTML 生成委托给渲染函数。

`harness/webui.py` 退回为展示模块：工作台/详情页、侧边栏和证据渲染、CSS 与浏览器 JavaScript。它不再构造 `CoreService`，也不协调仓库注册表。

### 兼容性

`harness.webui` 仍以再导出的方式提供 `include_webui`，因此现有调用方和测试无需更改导入路径。`create_app` 继续调用这一公开接口。

## 行为与错误处理

- 未选择仓库时，任务和审批操作在执行前返回 HTTP 400。
- 选择未知仓库时返回 HTTP 404。
- 仓库注册路径或重命名输入无效时返回 HTTP 400。
- 选择仓库本身不会创建服务；仅在路由确实需要服务时才懒创建。
- 后续请求复用未改变的缓存服务。

## 测试

使用 `TestClient` 对仓库 JSON 端点发送真实 FastAPI HTTP 请求，验证注册、选择、重命名和删除。

服务提供器测试验证：第二个仓库由注入工厂创建服务；切换后其 MockLLM/验证配置仍被保留；重复访问不会构造重复服务。现有直接调用端点的测试可保留用于细粒度输入校验，但不能作为浏览器接口的唯一覆盖。

## 清理

移除已提交的 `.superpowers/sdd/2026-07-27-webui-repository-registry/` 过程报告与 `task-2-report.md`。撤销未提交的 `TASK_FLOW.md` 忽略规则和 `harness/service.py` 中无功能作用的注释。保留产品代码与产品测试。

## 验收标准

1. `harness/webui.py` 不包含 `CoreService` 构造或 `RepositoryRegistry` 协调逻辑。
2. 切换仓库后仍保留调用方指定的依赖配置，且不会提前或重复创建服务。
3. 仓库管理路由通过 HTTP 层 JSON 请求测试。
4. 指定的过程文件和无关未提交变更均已移除。
5. 在可用 Python 环境中，聚焦测试与完整测试套件均通过。
