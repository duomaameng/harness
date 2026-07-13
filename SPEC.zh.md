# SPEC.md

# 上下文感知 Coding Agent Harness

## 1. 问题陈述

通用 LLM 已经能够生成有用的代码，但当它进入一个真实代码仓库执行开发任务时，仍然缺少稳定的工程化承载层。它可能选错文件、忽略项目约定、忘记历史决策，或者在测试失败后没有依据地反复修改。许多现有 coding agent 把这些决策隐藏在黑箱里，用户和评审者很难判断：它为什么选择这些上下文，为什么执行某个动作，失败后又为什么改变策略。

本项目要构建一个中量级、上下文感知的 Coding Agent Harness，用于单仓库内的功能开发任务。Harness 接收用户的功能需求后，先分析任务，再从代码结构、项目约定、历史决策中检索相关上下文，然后通过严格的结构化 action 协议驱动 LLM 工作。任务生命周期、action 校验、护栏判断、工具执行、验证命令运行和反馈回灌都由 harness 控制，而不是交给 LLM 自由发挥。

本项目的主要贡献是上下文机制：把仓库上下文变成显式、可检查、可持久化、可测试的工程对象。自修复能力是建立在客观验证反馈上的辅助能力。

## 2. 目标用户

- 独立开发者或学生：希望让 LLM 辅助完成可验证的功能开发，同时能看清它使用了哪些上下文和动作。
- 维护已有代码仓库的工程师：希望 agent 在遵守项目约定和安全边界的前提下完成中小规模变更。
- AI4SE 课程评审者：需要看到 harness 核心机制是由代码实现、可测试的，而不是只依赖 prompt 约束。

## 3. 项目范围

Harness 支持单仓库内的功能开发任务。一个任务可以跨相关模块，也可以包含中小规模的局部重构，例如提取函数、调整模块边界、拆分过大的文件、迁移局部接口等。每个任务必须能通过测试、lint、类型检查、构建命令或这些信号的组合来验证。

Harness 不支持跨仓库开发、不负责外部服务上线、不承诺完成大型架构重写，也不做大型多 agent 编排平台。首版系统运行一个核心 agent 主循环，但模块边界保留未来扩展空间。

## 4. 用户故事

1. 作为开发者，我希望提交一个单仓库内的功能需求后，harness 能识别任务类型、可能相关的模块和验证方式，以便 agent 不从空白上下文开始工作。

2. 作为开发者，我希望在执行前和执行中查看上下文包，以便知道哪些文件、项目约定和历史决策被选中，以及它们为什么被选中。

3. 作为开发者，我希望 LLM 只能通过结构化 action 操作工具，以便文件修改、命令执行、记忆写入和最终报告都能被校验、审计和测试。

4. 作为开发者，我希望测试、lint、类型检查、构建、schema 校验和护栏失败都能被转换成结构化反馈，以便 agent 进行有边界的自修复，而不是盲目重试。

5. 作为重视安全的用户，我希望危险动作在执行前被拦截，以便删除文件、越界访问、可疑 shell 命令和敏感文件访问必须经过拒绝或审批。

6. 作为课程评审者，我希望核心机制能在 MockLLM 下运行，以便不依赖真实 LLM 或网络，也能验证上下文检索、action 解析、工具分发、护栏、反馈和修复循环。

## 5. 功能规格

### 5.1 CLI、WebUI 与 API

交互入口层包括 CLI、WebUI 和 API。它们负责提交任务、查询状态、查看上下文包、检查 action 轨迹、处理审批请求和导出报告。它们不直接实现 agent 逻辑。

预期 CLI 命令包括：

- `init`：初始化仓库的 harness 元数据。
- `run`：提交并运行功能任务。
- `status`：查看任务和运行状态。
- `auth set/status/clear`：管理 LLM provider 凭据。
- `memory`：查看或管理长期记忆。
- `export`：导出脱敏运行报告。

WebUI 重点承担观察和审批职责。它展示当前任务状态、选中的上下文、action 历史、验证反馈、待审批请求和最终报告。

### 5.2 Core Service

Core Service 是交互入口层和 harness 内部逻辑之间的统一边界。它负责创建任务、启动运行、查询状态、记录审批结果，并向 WebUI 提供只读的运行信息。

CLI 和 WebUI 调用 Core Service，而不是直接调用 Agent Runner。

### 5.3 Task Profiler

Task Profiler 分析用户需求并提取：

- 任务类型；
- 关键词和符号；
- 可能相关的模块；
- 可能需要的验证方式；
- 任务是否过大、是否需要拆分。

如果需求看起来需要跨仓库、外部部署或大型架构重写，Task Profiler 会把任务标记为超出范围，并要求用户拆分。

### 5.4 Repository Index 与 Context Engine

Repository Index 扫描仓库并记录代码结构、文件路径、模块摘要、依赖信号、测试映射、README/配置中的项目约定，以及相关历史记忆。

Context Engine 从三类来源构建上下文包，优先级如下：

1. 代码结构上下文：文件树、模块职责、入口点、依赖关系和相关测试。
2. 项目约定上下文：编码风格、测试命令、安全边界、配置规则和仓库规范。
3. 历史决策上下文：已采纳的设计决策、被否决的方案、历史任务总结和已知坑点。

上下文检索先由代码驱动。Harness 根据静态结构、依赖信号、测试映射、关键词匹配和已存记忆生成候选集。LLM 可以辅助排序或解释候选项，但不能成为发现上下文的唯一机制。

每个 ContextPackage 都记录选中的条目、来源、评分、选择理由和估算上下文大小。如果超出上下文预算，系统按优先级裁剪：任务关键代码和测试优先，其次是项目约定，最后是历史决策。

### 5.5 LLM Provider 与 MockLLM

Harness 定义统一的 `LLMClient` 抽象。首个真实 provider 支持 OpenAI-compatible Chat Completions，可配置 `base_url`、`model` 和 API key。测试 provider 是 MockLLM，它按预设 action 序列返回结果。

LLMClient 只负责发送消息并返回模型输出。它不执行工具、不判断安全、不修改记忆，也不决定任务是否完成。

### 5.6 Agent Runner 与结构化 Action 协议

Agent Runner 是核心主循环。它控制任务生命周期，构造模型输入，调用 LLMClient，解析 action，通过护栏检查，分发工具，记录结果，运行验证，并判断继续或停止。

LLM 必须返回结构化 JSON action。例如：

```json
{
  "thought_summary": "Need to inspect parser tests before editing.",
  "action": "read_file",
  "args": {
    "path": "tests/test_parser.py"
  }
}
```

首版支持的 action 类型包括：

- `read_file`；
- `write_file`；
- `search`；
- `list_files`；
- `run_command`；
- `show_diff`；
- `record_memory`；
- `finish`。

非 JSON、未知 action、缺字段、参数类型错误和 schema 校验失败都不能执行，而是转换为结构化反馈进入下一轮。

### 5.7 Guardrail 与审批

Guardrail 在每个 action 执行前进行评估。结果为：

- `allow`；
- `deny`；
- `require_approval`。

Guardrail 检查包括：

- 规范化后的路径必须位于仓库根目录内；
- `.env`、密钥文件、疑似凭据路径等敏感文件需要拒绝或审批；
- 删除、覆盖关键配置、大范围文件变更属于高风险；
- 未知 shell 命令需要审批；
- 网络、发布、安装、Git 历史修改命令属于高风险；
- 极端危险命令直接拒绝。

需要审批的 action 会使 TaskRun 进入 `waiting_approval` 状态。CLI/WebUI 可以批准或拒绝请求。拒绝结果会作为 guardrail feedback 回灌给 Agent Runner。

### 5.8 Tool Dispatcher

Tool Dispatcher 只执行通过 schema 校验和护栏检查的 action。它提供受控的文件读取、文件写入、仓库搜索、目录列举、shell 命令、diff 查看和记忆记录能力。

所有工具结果都会记录状态、输出片段、退出码、变更文件、耗时和脱敏信息。工具输出在存储、展示或进入 prompt 前必须做大小限制和敏感信息脱敏。

### 5.9 Feedback Engine 与自修复

Feedback Engine 运行配置或自动发现的验证命令：

- 测试；
- lint；
- 类型检查；
- 构建；
- action schema 校验；
- guardrail feedback。

验证命令采用配置优先。如果没有配置，harness 根据 `package.json`、`pyproject.toml`、`Cargo.toml`、`pom.xml` 或常见仓库约定推断命令。

默认最多支持 6 轮自修复。每轮必须基于新的客观反馈推进。如果连续两轮失败类别和关键位置不变，系统提前停止并生成失败报告。

成功完成需要最后一次验证通过，或满足明确配置的成功条件。

### 5.10 记忆

MemoryEntry 保存长期仓库知识：

- 模块职责；
- 项目约定；
- 历史决策；
- 被否决方案；
- 常见失败模式；
- 任务总结。

记忆条目包含来源任务、置信度、时间戳和替代关系。冲突记忆不会被静默覆盖，新记录可以标记旧记录已被 supersede，同时保留审计链。

### 5.11 报告与导出

Harness 生成成功报告和失败报告。报告包含：

- 任务需求；
- 选中的上下文及理由；
- action 轨迹；
- 变更文件；
- 验证命令和结果；
- 修复轮次；
- 审批记录；
- 最终状态；
- 失败时的停止原因。

报告可以导出为脱敏 Markdown 或 JSON，用于课程证据和调试。

## 6. 领域与机制设计

### 6.1 Coding 领域工具

在 coding 领域，有用的动作包括读取文件、写入文件、搜索代码、列出文件、运行验证命令、查看 diff、记录记忆，以及完成或失败任务。这些能力由 harness 工具实现，并放在结构化 action 协议之后。

LLM 不能直接调用操作系统。它只能提出结构化 action，由 harness 判断是否执行以及如何执行。

### 6.2 客观反馈信号

客观反馈信号包括：

- 测试失败；
- lint 失败；
- 类型错误；
- 构建失败；
- action schema 不合法；
- guardrail 拒绝；
- 审批拒绝；
- 命令超时。

Feedback Engine 将这些信号转换为结构化反馈，包含来源、类别、摘要、位置和脱敏后的原始片段。

### 6.3 危险动作

危险动作包括：

- 读取或写入仓库根目录之外的路径；
- 访问凭据文件；
- 删除文件；
- 覆盖关键配置；
- 运行未知 shell 命令；
- 安装依赖；
- 发布产物；
- 修改 Git 历史；
- 执行网络相关命令。

危险动作处理必须由代码实现。仅在 prompt 中提醒模型注意安全，不算作安全机制实现。

### 6.4 作为主贡献的记忆机制

本项目的主贡献是结构化上下文与记忆机制。它把仓库知识转换成可查询、可审计的 ContextItem 和 ContextPackage。上下文选择可以通过 fixture 仓库和 MockLLM 测试。

即使没有真实 LLM，这个机制也仍然有意义：候选生成、评分、来源追踪、预算裁剪和上下文包创建都由代码完成。LLM 辅助是可选的，只用于排序或解释。

### 6.5 自修复机制

自修复由 Agent Runner 和 Feedback Engine 控制。LLM 不能决定无限重试。Harness 决定反馈是否有新信息、是否允许下一轮、是否应停止。

## 7. 系统架构与数据流

系统分为以下层次：

- 交互入口层：CLI、WebUI、API；
- 任务编排层：Core Service、Agent Runner、Task Profiler；
- 上下文层：Context Engine、Repository Index、Project Conventions、Decision Memory；
- 模型调用层：LLMClient；
- 工具执行层：Action Parser、Guardrail、Tool Dispatcher；
- 验证反馈层：Feedback Engine；
- 存储审计层：SQLite、JSONL Audit Store。

Agent Runner 是核心主循环。

CLI 和 WebUI 负责提交任务、查询状态和处理审批。Core Service 创建任务、启动运行、查询状态并记录审批结果。Task Profiler 分析用户需求。Context Engine 构建上下文包。LLMClient 调用真实模型或 MockLLM。Action Parser 校验 JSON action。Guardrail 判断 action 是允许、拒绝还是需要审批。Tool Dispatcher 执行已批准的 action。Feedback Engine 运行验证并返回结构化反馈。Audit Store 记录完整运行过程。

完整任务流程如下：

1. 用户提交任务。
2. Core Service 创建 Task 和 TaskRun。
3. Task Profiler 分析需求。
4. Context Engine 构建上下文包。
5. Agent Runner 调用 LLMClient。
6. LLM 返回结构化 action。
7. Action Parser 校验格式和 schema。
8. Guardrail 进行安全判断。
9. Tool Dispatcher 执行允许的 action。
10. Feedback Engine 在需要时运行验证。
11. 结果回灌给 Agent Runner。
12. Agent Runner 继续修复或结束运行。
13. Harness 生成完成报告或失败报告。

最重要的边界是：LLM 只提出结构化 action；Agent Runner 控制生命周期；Guardrail 负责安全判断；Tool Dispatcher 负责执行工具；Feedback Engine 使用真实验证信号判断进展。

## 8. 数据模型

### 8.1 Task

表示用户提交的功能需求。

字段：

- `id`；
- `title`；
- `description`；
- `repo_path`；
- `status`；
- `created_at`。

一个 Task 可以有多个 TaskRun。默认同一时间只允许一个 active TaskRun。

### 8.2 TaskRun

表示一次具体执行。

字段：

- `id`；
- `task_id`；
- `status`；
- `max_repair_rounds`；
- `current_round`；
- `stop_reason`；
- `started_at`；
- `finished_at`。

状态包括 `pending`、`running`、`waiting_approval`、`succeeded`、`failed` 和 `stopped`。

### 8.3 ContextItem

表示可检索的上下文单元。

字段：

- `id`；
- `repo_path`；
- `kind`；
- `source_path`；
- `symbol`；
- `summary`；
- `content_ref`；
- `metadata`；
- `updated_at`。

`kind` 包括 `code_structure`、`project_convention`、`decision_memory` 和 `test_mapping`。

### 8.4 ContextPackage

表示某一轮选中的上下文。

字段：

- `id`；
- `task_run_id`；
- `round_index`；
- `items`；
- `token_estimate`；
- `selection_reason`；
- `created_at`。

每个条目必须保留来源和选择理由。

### 8.5 Action

表示一次 LLM 返回的 action。

字段：

- `id`；
- `task_run_id`；
- `round_index`；
- `action_type`；
- `args_json`；
- `schema_status`；
- `guardrail_status`；
- `created_at`。

不合法或未知 action 会被记录，但不会执行。

### 8.6 ToolResult

表示工具执行结果。

字段：

- `id`；
- `action_id`；
- `status`；
- `stdout_excerpt`；
- `stderr_excerpt`；
- `exit_code`；
- `changed_files`；
- `duration_ms`；
- `created_at`。

输出必须脱敏并截断。

### 8.7 Feedback

表示验证反馈或机制反馈。

字段：

- `id`；
- `task_run_id`；
- `round_index`；
- `source`；
- `category`；
- `summary`；
- `locations`；
- `raw_excerpt`；
- `created_at`。

`source` 包括 `test`、`lint`、`typecheck`、`build`、`schema_validation` 和 `guardrail`。

`category` 包括 `assertion_failure`、`syntax_error`、`type_error`、`style_violation`、`unsafe_action`、`invalid_action` 和 `unknown`。

### 8.8 ApprovalRequest

表示待人工审批的动作。

字段：

- `id`；
- `task_run_id`；
- `action_id`；
- `risk_level`；
- `reason`；
- `status`；
- `decided_by`；
- `decided_at`。

动作在审批通过前不得执行。

### 8.9 MemoryEntry

表示长期仓库记忆。

字段：

- `id`；
- `repo_path`；
- `kind`；
- `content`；
- `source_task_id`；
- `confidence`；
- `created_at`；
- `superseded_by`。

历史通过 supersession 保留，而不是直接删除。

### 8.10 JSONL 审计事件

审计事件是 append-only 的 JSONL 记录，例如：

- `task.created`；
- `context.selected`；
- `action.received`；
- `schema.invalid`；
- `guardrail.blocked`；
- `approval.requested`；
- `approval.decided`；
- `tool.completed`；
- `feedback.generated`；
- `run.finished`。

## 9. 凭据与安全设计

凭据绝不硬编码、提交到 Git、写入日志、保存到 SQLite、保存到 JSONL、显示在 WebUI 明文中，或进入 prompt。

优先使用系统 keyring：

- Windows Credential Manager；
- macOS Keychain；
- Linux Secret Service。

CLI 提供：

- `auth set`：通过隐藏输入记录或更新凭据；
- `auth status`：显示 provider 和配置状态，但不显示 secret；
- `auth clear`：删除已保存凭据。

`.env` 只允许作为开发兜底。它必须被 Git 忽略，并在文档中明确说明明文风险。容器演示可以使用 `.env` 或 secret mount，但正式本地使用应优先使用 keyring。

### 威胁模型

#### 凭据泄露

威胁：API key 出现在 Git、日志、SQLite、JSONL、prompt、WebUI 或命令输出中。

对策：keyring 优先；`.env` 兜底时明确风险；输出脱敏；WebUI 只显示状态；测试覆盖脱敏逻辑。

#### 仓库外访问

威胁：LLM 请求访问仓库根目录之外的路径。

对策：每次文件操作前都做 canonical path 解析和仓库根目录检查。

#### 危险命令

威胁：LLM 请求破坏性、联网、发布、安装或 Git 历史修改命令。

对策：命令风险分级；验证命令白名单；未知或高风险命令需要审批；极端危险命令直接拒绝；命令有超时和输出限制。

#### 仓库文件中的 Prompt Injection

威胁：仓库内容诱导模型忽略规则、泄露凭据或执行危险 action。

对策：仓库内容被视为不可信上下文；action schema、guardrail 和凭据处理都不受模型控制。

#### 记忆污染

威胁：错误记忆影响后续任务。

对策：记忆条目包含来源、置信度和 supersession 链；低置信度记忆标记为 tentative。

#### 审计数据泄露

威胁：本地审计数据包含敏感路径、代码片段或 secret。

对策：导出时脱敏；输出截断；`.harness/` 默认不提交；文档说明本地数据边界。

## 10. 非功能需求

### 10.1 可测试性

核心机制必须能使用 MockLLM 和 fixture 仓库测试。测试不得依赖真实 LLM、API key 或网络。

### 10.2 可观测性

每次运行都记录上下文选择、action、工具结果、验证反馈、审批决策和最终状态。CLI/WebUI 可以查看这些状态，JSONL 审计日志可以导出。

### 10.3 可靠性

Harness 不得无限循环。默认最多 6 轮修复，并在连续重复失败时提前停止。

### 10.4 性能

Harness 应尽可能复用已有仓库索引。文件内容、命令输出、上下文包和 prompt 输入都必须有大小限制。

### 10.5 可移植性

Harness 支持在 Windows、macOS 和 Linux 上本地 Python 运行，也支持 Docker 运行。Docker 中 keyring 的限制必须写入文档。

### 10.6 可维护性

模块边界必须清晰：

- LLMClient 不执行工具。
- Guardrail 不调用 LLM。
- Tool Dispatcher 不决定任务生命周期。
- Feedback Engine 不直接修改代码。
- CLI/WebUI 不实现 agent loop 逻辑。

## 11. 技术选型

项目使用：

- Python：实现核心 harness 逻辑、文件系统操作、验证解析和仓库索引。
- Typer：实现 CLI。
- FastAPI：实现 WebUI/API。
- SQLite：保存本地结构化状态。
- JSONL：保存 append-only 审计日志。
- pytest：实现确定性单元测试和集成测试。
- keyring：存储凭据。
- OpenAI-compatible Chat Completions：作为首个真实 LLM provider。
- MockLLM：用于离线测试和机制演示。
- Docker：作为主要分发形态。

选择 Python 的原因是它适合 CLI、文件系统操作、子进程管理、测试和轻量 Web API。

## 12. 分发与部署

Docker 是主要分发形态。

仓库需要提供：

- `Dockerfile`；
- `docker build` 命令；
- `docker run` 命令；
- 目标仓库挂载说明；
- `.harness/` 数据目录挂载说明；
- provider 凭据配置说明；
- WebUI 访问说明。

镜像不得包含任何真实 API key。

如需公开演示，可以将 WebUI 部署到 Render、Fly.io 或 Railway 等免费额度平台。公开演示应使用 MockLLM 和样例仓库，避免暴露真实凭据或本地文件。

CI 必须包含名为 `unit-test` 的 job。CI 运行 pytest，使用 MockLLM，不依赖真实 API key，并构建 Docker 镜像。

## 13. 测试策略

### 13.1 单元测试

单元测试覆盖：

- Task Profiler；
- Context Engine；
- Action Parser；
- Guardrail；
- Tool Dispatcher；
- Feedback Engine；
- Memory Store；
- 凭据脱敏。

### 13.2 MockLLM 主循环测试

MockLLM 测试验证：

- 合法 action 会执行；
- 非法 action 会转换成反馈；
- 危险 action 会被拦截或进入审批；
- 验证失败会改变后续 action；
- 运行会在成功、重复失败或修复轮次耗尽时停止。

### 13.3 上下文机制测试

使用 fixture 仓库验证功能需求能检索到相关模块、测试、项目约定和历史决策。上下文包必须包含来源、评分和选择理由。

### 13.4 反馈解析测试

使用固定的 pytest、lint、typecheck、build、schema validation 和 guardrail denial 输出，验证反馈类别、摘要、位置和原始片段截断。

### 13.5 安全测试

测试覆盖路径穿越、敏感文件、危险命令、命令超时、输出截断和 secret 脱敏。

### 13.6 端到端机制演示

必需的机制演示使用 MockLLM 和样例仓库，展示：

1. 上下文包构建；
2. guardrail 拦截危险 action；
3. 一次失败实现经过结构化反馈后修复成功；
4. 主贡献上下文记忆机制的确定性行为。

## 14. 验收标准

- 用户可以通过 CLI 提交单仓库功能任务。
- Harness 会创建 Task 和 TaskRun 记录。
- Task Profiler 会生成任务画像。
- Context Engine 会从代码结构、项目约定和历史决策构建上下文包。
- CLI/WebUI 可以展示选中的上下文和原因。
- LLM 输出必须通过结构化 action schema 校验。
- 非法 action 不执行，并转换为反馈。
- 每个可执行 action 都必须先经过 Guardrail，再由 Tool Dispatcher 执行。
- 危险 action 会被拒绝或进入审批。
- ToolResult 会被记录并脱敏。
- 验证命令可以通过配置指定或自动发现。
- Feedback Engine 会结构化验证失败。
- Agent Runner 最多执行 6 轮修复，并在重复失败时提前停止。
- 成功报告和失败报告可以导出。
- MockLLM 测试覆盖 harness 核心，不依赖网络或 API key。
- API key 不出现在 Git、SQLite、JSONL、WebUI 明文、日志或 prompt 中。
- CI 包含 `unit-test` job 并运行 pytest。
- CI 构建 Docker 镜像。
- README 说明安装、运行、key 配置、分发方式和已知限制。

## 15. 风险与未决问题

### 15.1 上下文检索质量不足

风险：选中的上下文不完整或不相关。

缓解：结合仓库结构、测试映射、关键词、项目约定和记忆；在 WebUI 展示选择理由；用 fixture 测试上下文机制。

### 15.2 重构范围膨胀

风险：中型任务演变成大型架构重写。

缓解：Task Profiler 标记过大的任务，并要求用户拆分。

### 15.3 反馈解析覆盖不足

风险：不同语言和工具的验证输出格式差异大。

缓解：首版支持常见 pytest、lint、typecheck、build 和通用退出码解析；未知格式降级为脱敏输出片段。

### 15.4 Docker 与 Keyring 不匹配

风险：容器无法自然使用宿主系统 keyring。

缓解：文档明确本地 keyring 是优先方案，容器中的 `.env` 或 secret mount 只是演示兜底，并说明明文风险。

### 15.5 WebUI 范围膨胀

风险：WebUI 开发消耗过多时间，偏离 harness 核心。

缓解：WebUI 只支持任务提交、状态查看、上下文检查、action 轨迹、审批和报告。

### 15.6 真实 LLM 不稳定

风险：真实 provider 返回非法 JSON 或意外内容。

缓解：严格 Action Parser、结构化 invalid-action feedback，以及 MockLLM 机制测试。

## 16. 课程要求映射

本 SPEC 对 AI4SE Coding Agent Harness 要求的覆盖如下：

- 定义了自实现 harness 核心，而不是依赖现成高层 agent loop。
- 包含 LLM 抽象和 MockLLM。
- 定义了工具/action 机制、反馈信号、危险动作处理、记忆、配置和治理。
- 明确主贡献是结构化上下文记忆与上下文包构建。
- 要求核心机制在没有真实 LLM 的情况下也能确定性测试。
- 包含凭据安全、威胁模型、分发、CI 和 WebUI 要求。
- 定义 Docker 分发和 WebUI/API 演示入口。

