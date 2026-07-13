# 上下文感知 Coding Agent Harness 实现计划

> **给 agentic workers：** 必须使用子技能：用 `superpowers:subagent-driven-development`（推荐）或 `superpowers:executing-plans` 按 task 逐项执行本计划。步骤使用 checkbox（`- [ ]`）语法，方便追踪。

**目标：** 构建一个可确定性测试的单仓库 coding agent harness，支持显式上下文检索、结构化动作、 guardrail、工具调度、基于反馈的自修复、长期记忆、CLI/API/WebUI 可观测性、报告导出、Docker 分发和 CI。

**架构：** 该 harness 是一个 Python 包，核心边界是 `CoreService` 和 `AgentRunner`。交互层只调用 service；runner 控制生命周期；动作解析、guardrail、工具调度、反馈、上下文、记忆、持久化和报告分别放在独立模块中，并用 MockLLM 做确定性测试覆盖。

**技术栈：** Python、Typer、FastAPI、SQLite、JSONL、pytest、keyring、OpenAI-compatible Chat Completions、Docker、GitHub Actions。

## 全局约束

- 范围只支持单仓库 feature development。
- 核心机制必须能在没有网络和 API key 的情况下通过 `MockLLM` 运行。
- LLM 输出必须是结构化 JSON action，不能直接执行工具。
- 每个可执行 action 都必须先通过 schema validation 和 guardrail 检查。
- 上下文检索必须 code-driven first；LLM 只能用于排序或解释，不能作为唯一发现机制。
- 凭证不能硬编码、提交到 Git、写入日志、存入 SQLite、写入 JSONL、在 WebUI 明文显示，或放入 prompt。
- 默认 repair 上限是 6 轮。
- 如果连续两轮出现相同 failure category 和 key location，必须提前停止。
- `.harness/` 和 `.env` 是本地数据或开发 fallback，必须被 Git 忽略。
- CI 必须包含名为 `unit-test` 的 job，该 job 运行 pytest 且不使用真实 API key。
- CI 必须构建 Docker image。

---

## 文件结构

- `pyproject.toml`：包元数据、依赖、pytest 配置、console script。
- `.gitignore`：忽略 `.harness/`、`.env`、Python cache、构建产物。
- `README.md`：安装、运行、凭证、Docker、WebUI、已知限制、demo 流程。
- `Dockerfile`：CLI/API/WebUI 的本地容器分发，不内置任何 secret。
- `.github/workflows/ci.yml`：`unit-test` job 和 Docker image build。
- `harness/domain.py`：task、run、action、context、feedback、approval、memory、report 的 dataclass、enum 和 typed record。
- `harness/storage.py`：SQLite schema、domain record repository、JSONL audit writer。
- `harness/profiler.py`：task profiling 和 out-of-scope detection。
- `harness/repo_index.py`：仓库扫描、文件摘要、dependency/test mapping 信号。
- `harness/context_engine.py`：候选生成、评分、selection reason、budget trimming。
- `harness/memory.py`：memory CRUD、冲突处理、supersession、供上下文检索的查询。
- `harness/llm.py`：`LLMClient`、`MockLLM`、OpenAI-compatible client、credential config type。
- `harness/actions.py`：结构化 action schema parser 和 validation feedback 转换。
- `harness/guardrails.py`：路径、敏感文件、覆盖、命令、网络、安装、发布、Git history 风险检查。
- `harness/tools.py`：受控 read、write、search、list、command、diff、memory action 执行。
- `harness/feedback.py`：validation discovery、命令结果转结构化 feedback、重复失败检测。
- `harness/runner.py`：主 agent loop、approval wait state、repair rounds、finish condition。
- `harness/service.py`：CLI/API/WebUI 使用的 task/run orchestration boundary。
- `harness/reports.py`：redacted Markdown 和 JSON report export。
- `harness/auth.py`：keyring-first credential 操作和 `.env` fallback warning。
- `harness/cli.py`：Typer 命令 `init`、`run`、`status`、`auth`、`memory`、`export`。
- `harness/api.py`：tasks、runs、context、actions、feedback、approvals、reports 的 FastAPI endpoints。
- `harness/webui.py`：用于 observability 和 approval 的最小 HTML views。
- `tests/fixtures/sample_repo/`：确定性 context 和 runner 测试使用的小型 fixture repository。
- `tests/test_*.py`：下面每个 task 对应的 focused unit/integration tests。

## 依赖与并行关系

- Task 1 是所有任务的基础。
- Tasks 2、3、4、5 依赖 Task 1，可以并行执行。
- Task 6 依赖 Tasks 1、4、5。
- Task 7 依赖 Tasks 1、3、4、5。
- Task 8 依赖 Tasks 1、2、3、4、5、6、7。
- Tasks 9、10 依赖 Task 8，可以并行执行。
- Task 11 依赖 Tasks 1、2，可以与 Tasks 3 到 7 并行执行。
- Task 12 依赖 Tasks 8、9、10、11。
- Task 13 依赖所有实现任务。

## Tasks

### Task 1：项目骨架、领域模型与存储

**可并行：** 否。这是基础任务。

**依赖：** 无。

**目标：** 创建 package、typed domain records、SQLite 持久化和 append-only JSONL audit store，供后续所有任务使用。

**涉及文件：**
- 创建：`pyproject.toml`
- 创建：`.gitignore`
- 创建：`harness/__init__.py`
- 创建：`harness/domain.py`
- 创建：`harness/storage.py`
- 创建：`tests/test_storage.py`

**实现要点：**
- 定义 task/run/action/guardrail/approval/report status enum，取值必须与 `SPEC.md` 一致。
- 用 dataclass 定义 `Task`、`TaskRun`、`ContextItem`、`ContextPackage`、`Action`、`ToolResult`、`Feedback`、`ApprovalRequest`、`MemoryEntry`。
- 初始化 section 8 中每个 data model 对应的 SQLite table。
- audit event 以一行一个 JSON object 的形式写入，包含 event type 和 timestamp。
- invalid action 必须能以 `schema_status="invalid"` 存储，且没有 tool result。

**先写的失败测试：**
- 写 `tests/test_storage.py::test_storage_creates_task_run_and_audit_event`。
- 测试应创建一个临时 `.harness` 目录，初始化 storage，创建 task 和 run，追加 `task.created`，并断言 SQLite row 和 JSONL event 都存在。
- 初始预期失败：无法 import `harness.storage`，或缺少 `HarnessStorage`。

**验证命令：**
- `python -m pytest tests/test_storage.py::test_storage_creates_task_run_and_audit_event -q`
- `python -m pytest tests/test_storage.py -q`

### Task 2：Task Profiler 与验证策略提示

**可并行：** 是，在 Task 1 之后。

**依赖：** Task 1。

**目标：** 将用户请求分类成 task profile，包含 likely modules、symbols、validation requirements 和 out-of-scope flags。

**涉及文件：**
- 创建：`harness/profiler.py`
- 创建：`tests/test_profiler.py`
- 修改：`harness/domain.py`

**实现要点：**
- 添加 `TaskProfile`，字段包括 task type、keywords、symbols、likely modules、validation requirements、`out_of_scope`、`decomposition_reason`。
- 检测 cross-repository、external deployment、大型 architecture rewrite 请求，并标记为 out of scope。
- 根据请求中的 tests、lint、typecheck、build、Docker、CLI、API、WebUI、guardrail、memory、report 等词推断 validation requirements。
- 使用关键词和 path-like signal 做确定性提取。

**先写的失败测试：**
- 写 `tests/test_profiler.py::test_profiler_marks_cross_repo_deployment_out_of_scope`。
- 测试传入一个提到两个 repositories 和 production deployment 的请求，断言 `out_of_scope is True`，且 decomposition reason 同时说明 cross-repository work 和 deployment。
- 初始预期失败：`TaskProfiler` 不存在。

**验证命令：**
- `python -m pytest tests/test_profiler.py::test_profiler_marks_cross_repo_deployment_out_of_scope -q`
- `python -m pytest tests/test_profiler.py -q`

### Task 3：Repository Index、项目约定与 Fixture Repo

**可并行：** 是，在 Task 1 之后。

**依赖：** Task 1。

**目标：** 将仓库扫描成结构化 context items，覆盖文件、模块、测试、dependency signals 和 project conventions。

**涉及文件：**
- 创建：`harness/repo_index.py`
- 创建：`tests/fixtures/sample_repo/README.md`
- 创建：`tests/fixtures/sample_repo/pyproject.toml`
- 创建：`tests/fixtures/sample_repo/src/calculator.py`
- 创建：`tests/fixtures/sample_repo/tests/test_calculator.py`
- 创建：`tests/test_repo_index.py`

**实现要点：**
- 忽略 `.git`、`.harness`、virtualenv、cache、build output 和 binary file。
- 为 code structure、project conventions、test mappings 生成 `ContextItem` records。
- Python 文件优先用 `ast` 提取 functions/classes；解析失败时降级为 file-level summary。
- 根据路径命名和 symbol keywords 将 tests 映射到 source files。

**先写的失败测试：**
- 写 `tests/test_repo_index.py::test_repository_index_maps_source_file_to_related_test`。
- 测试应 index `tests/fixtures/sample_repo`，定位 `src/calculator.py`，并断言存在一个 `test_mapping` item 指向 `tests/test_calculator.py`，且 selection reason 非空。
- 初始预期失败：`RepositoryIndex` 不存在。

**验证命令：**
- `python -m pytest tests/test_repo_index.py::test_repository_index_maps_source_file_to_related_test -q`
- `python -m pytest tests/test_repo_index.py -q`

### Task 4：Decision Memory Store

**可并行：** 是，在 Task 1 之后。

**依赖：** Task 1。

**目标：** 实现长期 repository memory，包含 confidence、source task、timestamps、conflict-safe supersession 和供 context retrieval 使用的 query。

**涉及文件：**
- 创建：`harness/memory.py`
- 创建：`tests/test_memory.py`
- 修改：`harness/storage.py`

**实现要点：**
- 在 SQLite 中存储 `MemoryEntry` rows，用 `superseded_by` 表达替代关系，不做破坏性更新。
- 支持按 repository path、kind、content keyword 查询。
- 当调用方显式提供 old entry id 时，新 memory 可 supersede 匹配的 active entry。
- 保留旧 entries，保证 auditability。

**先写的失败测试：**
- 写 `tests/test_memory.py::test_memory_supersession_preserves_old_entry`。
- 测试创建一个原始 decision，再用新 decision supersede 它，并断言旧 row 仍存在且 `superseded_by` 已设置。
- 初始预期失败：`MemoryStore` 不存在。

**验证命令：**
- `python -m pytest tests/test_memory.py::test_memory_supersession_preserves_old_entry -q`
- `python -m pytest tests/test_memory.py -q`

### Task 5：Action Parser 与 Schema Feedback

**可并行：** 是，在 Task 1 之后。

**依赖：** Task 1。

**目标：** 解析 LLM JSON actions，验证支持的 action types 和 args shapes，并把 invalid output 转成结构化 feedback，且不执行。

**涉及文件：**
- 创建：`harness/actions.py`
- 创建：`tests/test_actions.py`
- 修改：`harness/domain.py`

**实现要点：**
- 支持 `read_file`、`write_file`、`search`、`list_files`、`run_command`、`show_diff`、`record_memory`、`finish`。
- 必须包含 `thought_summary`、`action`、`args`。
- 按 action 类型验证 required fields 和 primitive types。
- invalid JSON、unknown action、missing fields、wrong types 都返回 invalid `Action` 和 `Feedback(source="schema_validation", category="invalid_action")`。

**先写的失败测试：**
- 写 `tests/test_actions.py::test_unknown_action_becomes_schema_feedback_and_is_not_executable`。
- 测试解析一个 action 为 `delete_file` 的 JSON payload，断言 schema status 为 invalid，并断言 feedback category 是 `invalid_action`。
- 初始预期失败：`ActionParser` 不存在。

**验证命令：**
- `python -m pytest tests/test_actions.py::test_unknown_action_becomes_schema_feedback_and_is_not_executable -q`
- `python -m pytest tests/test_actions.py -q`

### Task 6：Guardrails 与 Approval Classification

**可并行：** 否。

**依赖：** Tasks 1、4、5。

**目标：** 在每个 parsed action 执行前评估 repository boundary safety、sensitive file access、risky writes、dangerous commands 和 approval requirements。

**涉及文件：**
- 创建：`harness/guardrails.py`
- 创建：`tests/test_guardrails.py`
- 修改：`harness/domain.py`

**实现要点：**
- 对所有路径做 canonicalize，并拒绝 repository root 之外的访问。
- 对 `.env`、key files、credential-like paths、deletion、critical config overwrites、network、publish、install、git history commands 进行 deny 或 require approval。
- 对已配置或已发现的已知 validation commands 放行，例如 `python -m pytest`、`pytest`、`ruff check`、`mypy`、`python -m build`。
- 返回 `allow`、`deny` 或 `require_approval`，并携带 risk level 和 reason。

**先写的失败测试：**
- 写 `tests/test_guardrails.py::test_path_traversal_read_is_denied_before_dispatch`。
- 测试构造一个读取 `../secret.txt` 的 `read_file` action，用临时 repo root 评估，断言 status 是 `deny`，reason 提到 repository root。
- 初始预期失败：`Guardrail` 不存在。

**验证命令：**
- `python -m pytest tests/test_guardrails.py::test_path_traversal_read_is_denied_before_dispatch -q`
- `python -m pytest tests/test_guardrails.py -q`

### Task 7：带 Redaction 和 Limits 的 Tool Dispatcher

**可并行：** 否。

**依赖：** Tasks 1、3、4、5。

**目标：** 只执行已批准的 actions，并通过受控 file、search、command、diff 和 memory tools 记录 redacted、truncated tool results。

**涉及文件：**
- 创建：`harness/tools.py`
- 创建：`tests/test_tools.py`
- 修改：`harness/storage.py`

**实现要点：**
- 实现 `read_file`、`write_file`、`search`、`list_files`、`run_command`、`show_diff`、`record_memory`。
- 要求调用方传入已经 allow 的 action 和 repository root。
- 对 stdout/stderr/file excerpts 做配置化截断。
- 对 API keys、bearer tokens、明显 secrets 和 `.env` 风格 credential values 做 redaction 后再存储。
- 记录 changed files 和 command duration。

**先写的失败测试：**
- 写 `tests/test_tools.py::test_run_command_result_redacts_secret_like_output`。
- 测试运行一个打印 `OPENAI_API_KEY=sk-test-secret` 的命令，并断言存储的 stdout excerpt 不包含 `sk-test-secret`。
- 初始预期失败：`ToolDispatcher` 不存在。

**验证命令：**
- `python -m pytest tests/test_tools.py::test_run_command_result_redacts_secret_like_output -q`
- `python -m pytest tests/test_tools.py -q`

### Task 8：带 Scoring、Reasons 与 Budget Trimming 的 Context Engine

**可并行：** 否。

**依赖：** Tasks 1、2、3、4、5、6、7。

**目标：** 从 repository index、project conventions、test mappings 和 decision memory 构建可审计 context packages。

**涉及文件：**
- 创建：`harness/context_engine.py`
- 创建：`tests/test_context_engine.py`
- 修改：`harness/domain.py`
- 修改：`harness/storage.py`

**实现要点：**
- 使用 static structure、dependency signals、test mappings、keyword matching、stored memory 生成 candidates。
- 确定性评分，并保留 score、source、selection reason。
- 超出 budget 时按优先级裁剪：task-critical code 和 tests 优先，其次 conventions，再次 historical decisions。
- 按 task run 和 round 存储 `ContextPackage` records。

**先写的失败测试：**
- 写 `tests/test_context_engine.py::test_context_package_includes_code_test_convention_and_memory_reasons`。
- 测试 index sample repo，添加一个 decision memory entry，提交 calculator feature 请求，并断言 package 至少包含每种 required source 的一个 item，且都有 selection reason。
- 初始预期失败：`ContextEngine` 不存在。

**验证命令：**
- `python -m pytest tests/test_context_engine.py::test_context_package_includes_code_test_convention_and_memory_reasons -q`
- `python -m pytest tests/test_context_engine.py -q`

### Task 9：Feedback Engine 与 Validation Loop Signals

**可并行：** 是，在 Task 8 之后。

**依赖：** Task 8。

**目标：** 发现 validation commands，运行 configured validations，将 failures 解析为结构化 feedback，并检测重复不变失败。

**涉及文件：**
- 创建：`harness/feedback.py`
- 创建：`tests/test_feedback.py`
- 修改：`harness/domain.py`

**实现要点：**
- 优先使用 configured validation commands；没有配置时从 `pyproject.toml`、`package.json`、`Cargo.toml`、`pom.xml` 和常见约定推断 fallback commands。
- 解析 pytest、lint、typecheck、build、schema validation、guardrail denial、approval rejection、timeout 和 generic exit-code failures。
- 存储 category、summary、locations、redacted raw excerpt。
- 按 category 和 key location 比较连续失败，决定是否 early stop。

**先写的失败测试：**
- 写 `tests/test_feedback.py::test_repeated_same_pytest_failure_stops_after_second_occurrence`。
- 测试传入两个 category 为 `assertion_failure` 且 file/test location 相同的 feedback objects，断言 engine 建议 early stop。
- 初始预期失败：`FeedbackEngine` 不存在。

**验证命令：**
- `python -m pytest tests/test_feedback.py::test_repeated_same_pytest_failure_stops_after_second_occurrence -q`
- `python -m pytest tests/test_feedback.py -q`

### Task 10：LLM Clients 与 Agent Runner 主循环

**可并行：** 是，在 Task 8 之后。

**依赖：** Task 8。

**目标：** 实现模型抽象、MockLLM、OpenAI-compatible client shell 和有界 Agent Runner 生命周期。

**涉及文件：**
- 创建：`harness/llm.py`
- 创建：`harness/runner.py`
- 创建：`tests/test_runner.py`
- 修改：`harness/storage.py`

**实现要点：**
- `LLMClient` 只发送 messages 并返回 model output。
- `MockLLM` 返回预定义 structured action strings。
- OpenAI-compatible client 接受 `base_url`、`model`、API key，但 offline tests 不使用它。
- `AgentRunner` 从 task、profile、context、prior actions、feedback 构造 model inputs。
- Runner 解析 actions、应用 guardrails、调度 tools、运行 validation、记录 audit events、遵守 approval wait state，并在 success、repeated failure 或六轮 repair 后停止。

**先写的失败测试：**
- 写 `tests/test_runner.py::test_invalid_action_from_mock_llm_becomes_feedback_without_tool_execution`。
- 测试配置 MockLLM 返回 invalid JSON，运行一轮 loop，断言存在 schema feedback，且没有 tool result。
- 初始预期失败：`AgentRunner` 或 `MockLLM` 不存在。

**验证命令：**
- `python -m pytest tests/test_runner.py::test_invalid_action_from_mock_llm_becomes_feedback_without_tool_execution -q`
- `python -m pytest tests/test_runner.py -q`

### Task 11：Credentials、Reports 与 Export Redaction

**可并行：** 是，在 Tasks 1 和 2 之后。

**依赖：** Tasks 1、2。

**目标：** 添加 keyring-first credential management，以及 redacted Markdown/JSON success/failure report export。

**涉及文件：**
- 创建：`harness/auth.py`
- 创建：`harness/reports.py`
- 创建：`tests/test_auth_reports.py`
- 修改：`.gitignore`

**实现要点：**
- 在 service class 后实现 `auth set/status/clear`，测试中可使用 fake keyring。
- 报告 `.env` fallback 是 plaintext development risk，但不打印 secret values。
- 导出 task request、selected context、action trace、changed files、validation commands/results、repair rounds、approval decisions、final status 和 stop reason。
- Markdown 和 JSON exports 都必须 redact credentials 和 secret-like strings。

**先写的失败测试：**
- 写 `tests/test_auth_reports.py::test_report_export_redacts_api_key_from_action_trace`。
- 测试构造一个在 tool excerpt 中含有 `sk-test-secret` 的 run report，并断言导出的 Markdown 和 JSON 都不包含 secret。
- 初始预期失败：`ReportExporter` 不存在。

**验证命令：**
- `python -m pytest tests/test_auth_reports.py::test_report_export_redacts_api_key_from_action_trace -q`
- `python -m pytest tests/test_auth_reports.py -q`

### Task 12：Core Service、CLI、API 与 WebUI Observability

**可并行：** 否。

**依赖：** Tasks 8、9、10、11。

**目标：** 通过统一 service boundary、Typer CLI、FastAPI endpoints 和最小 WebUI 暴露 harness 的 status、context、actions、feedback、approvals 和 reports。

**涉及文件：**
- 创建：`harness/service.py`
- 创建：`harness/cli.py`
- 创建：`harness/api.py`
- 创建：`harness/webui.py`
- 创建：`tests/test_service_cli_api.py`
- 修改：`pyproject.toml`

**实现要点：**
- `CoreService` 创建 tasks/runs、启动 runs、读取 status、记录 approvals、管理 memory、导出 reports。
- CLI 命令包括 `init`、`run`、`status`、`auth set/status/clear`、`memory`、`export`。
- API endpoints 支持提交 tasks、查询 runs、读取 context/action/feedback traces、approve/reject pending approvals、导出 reports。
- WebUI 渲染 read-only observability pages 和 approval decision forms；WebUI 不实现 agent logic。

**先写的失败测试：**
- 写 `tests/test_service_cli_api.py::test_cli_run_with_mock_llm_creates_task_run_and_context_trace`。
- 测试用 MockLLM 对临时 sample repo 调用 Typer CLI，断言命令成功退出，且 storage 中存在 task run 和 context package。
- 初始预期失败：CLI entry point 不存在。

**验证命令：**
- `python -m pytest tests/test_service_cli_api.py::test_cli_run_with_mock_llm_creates_task_run_and_context_trace -q`
- `python -m pytest tests/test_service_cli_api.py -q`

### Task 13：Docker、CI、README 与端到端机制 Demo

**可并行：** 否。

**依赖：** 所有前置任务。

**目标：** 提供 distribution、automated verification、documentation 和确定性 MockLLM demo，覆盖课程要求的 mechanism evidence。

**涉及文件：**
- 创建：`Dockerfile`
- 创建：`.github/workflows/ci.yml`
- 创建：`README.md`
- 创建：`tests/test_e2e_demo.py`
- 修改：`pyproject.toml`

**实现要点：**
- Docker image 安装 package 并运行 CLI/API/WebUI，不嵌入 secrets。
- CI job 名为 `unit-test`，使用 MockLLM 运行 pytest，且不需要真实 API key。
- CI 在 tests 后构建 Docker image。
- README 记录 install、`harness init`、`harness run`、credential configuration、`.env` fallback risk、WebUI access、Docker build/run、report export、known limits 和 demo flow。
- E2E test 展示 context package construction、guardrail interception of dangerous action、failed implementation feedback、successful repair 和 memory inclusion。

**先写的失败测试：**
- 写 `tests/test_e2e_demo.py::test_mockllm_demo_context_guardrail_feedback_repair_and_memory`。
- 测试针对 sample repo 运行确定性 MockLLM sequence，并断言四个 required demonstration events 都出现在 storage 或 audit logs 中。
- 初始预期失败：demo workflow 无法 import 或执行。

**验证命令：**
- `python -m pytest tests/test_e2e_demo.py::test_mockllm_demo_context_guardrail_feedback_repair_and_memory -q`
- `python -m pytest -q`
- `docker build -t context-aware-harness:test .`

## 最终验证清单

- `python -m pytest -q`
- `docker build -t context-aware-harness:test .`
- 确认 `.github/workflows/ci.yml` 包含名为 `unit-test` 的 job。
- 确认 `README.md` 记录 install、run、key configuration、Docker distribution、WebUI/API、report export、MockLLM demo 和 known limits。
- 确认没有测试需要真实 LLM、API key 或 network access。
- 确认 `.gitignore` 忽略 `.harness/` 和 `.env`。

## 对 SPEC.md 的自检

- CLI、API、WebUI 和 Core Service 由 Task 12 覆盖。
- Task Profiler 由 Task 2 覆盖。
- Repository Index、Context Engine、project conventions 和 decision memory 由 Tasks 3、4、8 覆盖。
- LLMClient 和 MockLLM 由 Task 10 覆盖。
- Agent Runner 和 structured action protocol 由 Tasks 5、10 覆盖。
- Guardrail 和 approval 由 Tasks 6、10、12 覆盖。
- Tool Dispatcher 由 Task 7 覆盖。
- Feedback Engine 和 self-repair 由 Tasks 9、10 覆盖。
- Reports 和 export 由 Task 11 覆盖。
- Credential 和 security design 由 Tasks 6、7、11、13 覆盖。
- Data model 和 audit events 由 Task 1 覆盖。
- Testing strategy、MockLLM demonstration、Docker、CI 和 README 由 Task 13 覆盖。
