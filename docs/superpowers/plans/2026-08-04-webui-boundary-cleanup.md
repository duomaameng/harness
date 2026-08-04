# WebUI 职责边界清理实施计划

> **供代理执行者使用：** 必须使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务执行；步骤以复选框追踪。

**目标：** 将 WebUI 的服务生命周期和路由职责移出展示模块，修复切换仓库后的依赖丢失，补齐 HTTP 层测试，并清理无关过程文件。

**架构：** WebUIServiceProvider 负责当前仓库的 CoreService 解析、工厂创建与缓存；webui_routes.py 负责 HTTP 路由及输入校验；webui.py 仅提供页面渲染。harness.webui.include_webui 保持为兼容再导出。

**技术栈：** Python 3.11+、FastAPI、pytest、现有 RepositoryRegistry、CoreService、MockLLM。

## 全局约束

- 必须完整保留当前多仓库功能：仓库注册、选择、重命名、删除注册及任务隔离的已有行为、路由和持久化格式均不得移除或改变；本计划仅修复其服务配置传递、职责边界和测试覆盖。
- 不新增运行时依赖；HTTP 回归测试使用 FastAPI/Starlette 已提供的测试客户端。
- CoreService 的公开构造参数保持 repo_path、llm 和 validation_commands。
- harness.webui 的 include_webui 导入路径必须继续有效。
- 每次产品行为变更遵循先写失败测试、确认失败、最小实现、确认通过的 TDD 循环。

---

## 文件职责映射

- harness/webui_services.py（新建）：仓库路径到 CoreService 的解析、懒创建和缓存。
- harness/webui_routes.py（新建）：WebUI 路由、请求校验、注册表操作及渲染委托。
- harness/webui.py（修改）：仅页面渲染、样式、浏览器脚本，以及 include_webui 兼容再导出。
- tests/test_webui_services.py（新建）：服务提供器的配置继承和缓存行为。
- tests/test_service_cli_api.py（修改）：真实 HTTP 请求的仓库管理回归测试。
- .superpowers/sdd/2026-07-27-webui-repository-registry/、task-2-report.md（删除）：非产品过程报告。
- .gitignore、harness/service.py（修改）：撤销当前无关未提交变更。

### Task 1：WebUI 服务提供器

**文件：**

- 新建：harness/webui_services.py
- 新建：tests/test_webui_services.py

**接口：**

- 产出：WebUIServiceProvider(initial_service: CoreService, service_factory: Callable[[Path], CoreService] | None = None)。
- 产出：for_repository(repo_path: str | Path) -> CoreService。

- [ ] **步骤 1：写失败测试，锁定工厂创建、缓存和配置继承。**

~~~python
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
~~~

- [ ] **步骤 2：运行测试并确认模块缺失导致失败。**

运行：python -m pytest tests/test_webui_services.py::test_provider_creates_selected_repository_once_with_injected_factory -q

预期：失败信息包含 No module named 'harness.webui_services'。

- [ ] **步骤 3：写第二个失败测试，锁定默认工厂继承依赖。**

~~~python
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
~~~

- [ ] **步骤 4：运行第二个测试并确认因缺少提供器而失败。**

运行：python -m pytest tests/test_webui_services.py::test_provider_default_factory_preserves_initial_dependencies -q

预期：失败信息包含 No module named 'harness.webui_services'。

- [ ] **步骤 5：最小实现服务提供器。**

~~~python
class WebUIServiceProvider:
    def __init__(self, initial_service, service_factory=None):
        self._services = {str(initial_service.repo_path.resolve()): initial_service}
        self._factory = service_factory or self._default_factory(initial_service)

    def for_repository(self, repo_path):
        key = str(Path(repo_path).resolve())
        if key not in self._services:
            self._services[key] = self._factory(Path(key))
        return self._services[key]
~~~

默认工厂必须调用 CoreService(path, llm=initial.llm, validation_commands=initial.validation_commands)。

- [ ] **步骤 6：确认测试通过并提交。**

运行：python -m pytest tests/test_webui_services.py -q

预期：两个测试通过。

~~~bash
git add harness/webui_services.py tests/test_webui_services.py
git commit -m "fix: preserve webui service configuration"
~~~

### Task 2：HTTP 契约和路由/展示拆分

**文件：**

- 新建：harness/webui_routes.py
- 修改：harness/webui.py（移除路由、服务生命周期和注册表协调；再导出接口）
- 修改：harness/api.py（接受并转发 service_factory）
- 修改：tests/test_service_cli_api.py

**接口：**

- 产出：include_webui(app, service=None, *, repo_path=".", registry=None, service_factory=None) -> FastAPI。
- 产出：harness.webui.include_webui 对 harness.webui_routes.include_webui 的兼容再导出。

- [ ] **步骤 1：写 HTTP 契约测试，注册、选择、重命名和删除仓库。**

~~~python
def test_webui_repository_management_routes_accept_http_json(tmp_path):
    registry = RepositoryRegistry(tmp_path / "config")
    first_path, second_path = tmp_path / "first", tmp_path / "second"
    first_path.mkdir()
    second_path.mkdir()
    first = registry.register(first_path)
    app = create_app(CoreService(first_path, llm=MockLLM([])), registry=registry)

    with TestClient(app) as client:
        added = client.post("/ui/repositories", json={"path": str(second_path)})
        second = added.json()
        selected = client.post(
            f"/ui/repositories/{first['id']}/select", follow_redirects=False
        )
        renamed = client.post(
            f"/ui/repositories/{first['id']}/rename", json={"name": "Primary"}
        )
        deleted = client.post(
            f"/ui/repositories/{second['id']}/delete", follow_redirects=False
        )

    assert added.status_code == 200
    assert selected.status_code == 303
    assert renamed.json()["name"] == "Primary"
    assert deleted.headers["location"] == "/"
~~~

- [ ] **步骤 2：在重构前运行 HTTP 契约测试，记录基线。**

运行：python -m pytest tests/test_service_cli_api.py::test_webui_repository_management_routes_accept_http_json -q

预期：通过；这是迁移前的行为契约。

- [ ] **步骤 3：写失败测试，证明 WebUI 切换使用注入工厂。**

~~~python
def test_webui_switch_uses_injected_service_factory(tmp_path):
    first_path, second_path = tmp_path / "first", tmp_path / "second"
    first_path.mkdir()
    second_path.mkdir()
    registry = RepositoryRegistry(tmp_path / "config")
    registry.register(first_path)
    second = registry.register(second_path)
    created = []

    def factory(path: Path) -> CoreService:
        service = CoreService(path, llm=MockLLM([]), validation_commands=["pytest -q"])
        created.append(service)
        return service

    app = create_app(
        CoreService(first_path, llm=MockLLM([])),
        registry=registry,
        service_factory=factory,
    )
    with TestClient(app) as client:
        client.post(f"/ui/repositories/{second['id']}/select", follow_redirects=False)
        response = client.post("/ui/tasks", json={"title": "Task in second"})

    assert response.status_code == 200
    assert len(created) == 1
    assert created[0].repo_path == second_path.resolve()
~~~

- [ ] **步骤 4：运行测试并确认当前 create_app 不接受 service_factory。**

运行：python -m pytest tests/test_service_cli_api.py::test_webui_switch_uses_injected_service_factory -q

预期：失败信息包含 unexpected keyword argument 'service_factory'。

- [ ] **步骤 5：实现路由模块。**

将 include_webui、_required_title 和 _max_rounds 从 webui.py 移至 webui_routes.py。路由模块从 webui.py 导入 _render_workbench、_render_run_detail，并通过提供器获取服务：

~~~python
provider = WebUIServiceProvider(core, service_factory=service_factory)

def current_core() -> CoreService:
    if registry is None:
        return core
    repository = registry.current()
    if repository is None:
        raise HTTPException(status_code=400, detail="Select or add a repository first")
    return provider.for_repository(repository["path"])
~~~

禁止在该函数或 webui.py 中直接构造 CoreService。

- [ ] **步骤 6：将 webui.py 限定为展示层并保留兼容导出。**

删除 FastAPI、RepositoryRegistry、CoreService 路由依赖和 include_webui 实现，文件末尾增加：

~~~python
from harness.webui_routes import include_webui

__all__ = ["include_webui"]
~~~

- [ ] **步骤 7：将工厂参数传入 API 工厂。**

~~~python
def create_app(..., registry=None, service_factory=None) -> FastAPI:
    ...
    include_webui(app, core, registry=active_registry, service_factory=service_factory)
~~~

- [ ] **步骤 8：验证 HTTP、工厂注入、公开导入和既有 WebUI 测试。**

运行：python -m pytest tests/test_service_cli_api.py -q

预期：测试通过，harness.webui 的 include_webui 仍可导入。

- [ ] **步骤 9：提交路由拆分。**

~~~bash
git add harness/webui_routes.py harness/webui.py harness/api.py tests/test_service_cli_api.py
git commit -m "refactor: separate webui routes from rendering"
~~~

### Task 3：清理与完整验证

**文件：**

- 删除：.superpowers/sdd/2026-07-27-webui-repository-registry/
- 删除：task-2-report.md
- 修改：.gitignore、harness/service.py

**接口：** 不修改产品接口。

- [ ] **步骤 1：确认无关未提交变更范围。**

运行：git diff -- .gitignore harness/service.py

预期：只显示 TASK_FLOW.md 忽略规则和 service.py 的解释性注释；如范围扩大则停止并报告。

- [ ] **步骤 2：删除授权的过程文件并撤销无关工作区修改。**

目标必须逐一限定为：

~~~text
.superpowers/sdd/2026-07-27-webui-repository-registry/
task-2-report.md
.gitignore 的 TASK_FLOW.md 单行
harness/service.py 的三行解释性注释
~~~

- [ ] **步骤 3：检查清理结果。**

运行：

~~~bash
git diff --name-status
git diff --check
~~~

预期：指定报告显示删除；.gitignore 和 harness/service.py 不再存在无关差异；无空白错误。

- [ ] **步骤 4：提交清理。**

~~~bash
git add -u -- .superpowers/sdd/2026-07-27-webui-repository-registry task-2-report.md .gitignore harness/service.py
git commit -m "chore: remove webui registry process artifacts"
~~~

- [ ] **步骤 5：运行聚焦和完整测试。**

运行：

~~~bash
python -m pytest tests/test_webui_services.py tests/test_service_cli_api.py -q
python -m pytest -q
rg -n "CoreService\\(" harness/webui.py
rg -n "RepositoryRegistry" harness/webui.py
git diff --check HEAD~3..HEAD
~~~

预期：测试全部通过；两条 rg 命令无输出；差异检查无输出。

- [ ] **步骤 6：请求独立代码审查。**

审查范围为本计划生成的提交；核对 SPEC.md/PLAN.md、配置继承、SRP/DIP 边界、HTTP 覆盖和清理范围。

## 计划自检

- 规格覆盖：Task 1 覆盖配置继承和缓存；Task 2 覆盖 HTTP 契约、SRP/DIP 拆分和兼容性；Task 3 覆盖授权清理和完整验证。
- 占位符检查：每个任务均提供准确文件、接口、测试名、命令和预期结果。
- 类型一致性：for_repository 始终接收 str | Path 并返回 CoreService；service_factory 始终接收 Path 并返回 CoreService；include_webui 与 create_app 均以可选关键字参数 service_factory 传递它。
