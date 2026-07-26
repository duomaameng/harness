# SPEC_PROCESS.md

# Superpowers 协作过程文档

## 1. 背景

本项目选择课程 A 类题目：Coding Agent Harness。过程上使用 Superpowers 的 `brainstorming` 先澄清需求和设计，再沉淀为 `SPEC.md`。本文件只记录 SPEC 形成过程中的关键节点、关键迭代、采纳与修正决策，以及对 brainstorming 技能的反思。

本项目最终形成的定位是：

> 一个面向单仓库中小功能开发的中量级、上下文感知 Coding Agent Harness。它通过结构化上下文记忆、结构化 action、代码层护栏和验证反馈闭环，让 LLM 在可解释、可审计、可测试的边界内完成功能开发任务。

与 SPEC 相关的文档包括：

- `SPEC.md`：英文规格文档。
- `SPEC.zh.md`：中文规格文档。

## 2. Brainstorming 关键节点

### 2.1 从“做一个 harness”澄清到“主贡献是什么”

一开始需求只有“做 Coding Agent Harness”，范围过大。智能体先追问主贡献方向：治理护栏、自修复、上下文、工具编排。这个问题让我意识到：课程要求中的动作、反馈、危险动作、记忆都必须做，但需要有一个主贡献做深，否则系统会变成平均用力的功能清单。

最终我选择：

- 主贡献：上下文型 harness。
- 辅助能力：自修复。

这个决策直接影响了 `SPEC.md` 中的核心表述：上下文记忆和 ContextPackage 构建是 main contribution，自修复建立在验证反馈上。

### 2.2 澄清 WebUI 的作用

当智能体建议“CLI 是核心入口，WebUI 是观察与审批界面”时，我一开始不清楚 WebUI 的价值，认为可能只是为了满足课程要求而额外加页面。

智能体进一步解释 WebUI 的三个作用：

- 展示上下文注入：让用户看到 harness 为什么选这些文件、约定和历史决策。
- 展示自修复循环：让用户看到每轮 action、验证失败、反馈摘要和下一步原因。
- 处理人工审批：让危险 action 的治理机制有可见交互面。

这个解释让我确认：WebUI 不是装饰，而是把 harness 的核心机制外显出来，服务于可解释性和课程验收。

### 2.3 从“小型维护任务”修正为“中量级功能开发”

智能体最初建议把任务范围限定为“小型维护任务”。我指出这不符合我的需求，因为这会让 harness 看起来作用很弱。

经过讨论后，范围被修正为：

- 单仓库；
- 允许跨相关模块；
- 可由测试、lint、typecheck、build 等验证；
- 不涉及外部服务上线；
- 不做大型架构重构；
- 支持中小规模局部重构。

这个迭代很关键。它让项目从“玩具级小任务执行器”变成“中量级功能开发 harness”，同时仍然保持边界清晰。

### 2.4 明确上下文检索不是让 LLM 猜

在上下文系统设计中，智能体建议采用“代码驱动候选生成 + LLM 辅助排序解释”的策略。我确认了这个方向。

这解决了一个重要评分风险：如果上下文检索完全靠 LLM 判断，就会变成 prompt 行为，而不是 harness 机制。最终 spec 明确规定：

- 代码先根据文件结构、依赖、测试映射、关键词和历史记忆生成候选集；
- LLM 只能用于排序或解释；
- 上下文包必须记录来源、评分和选择理由；
- 该机制必须能用 fixture 仓库和 MockLLM 测试。

### 2.5 明确主循环边界

智能体建议采用严格结构化 JSON action 协议。我确认后，系统边界变得清楚：

- LLM 只提出 action；
- Action Parser 校验格式；
- Guardrail 判断安全；
- Tool Dispatcher 执行工具；
- Feedback Engine 用真实验证结果判断进展；
- Agent Runner 控制任务生命周期。

这个边界后来成为 `SPEC.md` 系统架构部分的核心原则。

## 3. 至少三轮关键迭代

### 迭代一：主贡献选择

**对话节选**

智能体问：

> 你希望这个 harness 的主贡献聚焦在哪个机制上？治理护栏、自修复、上下文、工具编排？

我追问：

> 这个主贡献是在讨论什么，这些难道不是都应该做吗？

智能体解释：

> 四类都应该做，主贡献不是决定其他不做，而是在满足基础完整性的前提下，选择一个机制做得更深、更有辨识度。

我最终决定：

> 我想主要是上下文型，同时有自修复的能力。

**处理决策**

采纳“所有基础机制都做，但上下文机制做深”的结构。SPEC 中因此同时覆盖 action/tool、反馈、危险动作、记忆四类机制，但把“结构化上下文记忆与上下文包构建”作为主贡献。

**影响**

避免了项目变成单纯工具调用器或自修复 demo，使其更符合 harness 层工程价值。

### 迭代二：WebUI 是否有必要

**对话节选**

智能体建议：

> CLI 是核心入口，WebUI 是观察与审批界面。

我提出疑问：

> 你的建议 WebUI 发挥了什么作用，我不是很清楚。

智能体解释 WebUI 的价值：

> 展示上下文注入、查看自修复循环、处理人工审批。

我确认：

> 可以就这样。

**处理决策**

采纳 WebUI，但限制其范围：不做复杂 IDE，不做完整开发环境，只做任务提交、状态查看、上下文解释、action 轨迹、审批和报告。

**影响**

WebUI 从“课程要求的附属页面”变成“可解释性与治理机制的展示面”。这也为后续 WebUI 设计和实现提供了边界。

### 迭代三：任务范围从小型改为中量级

**对话节选**

智能体建议：

> 先限定在小型维护任务，例如修复测试失败、实现小函数、修改配置。

我反驳：

> 我现在有点不理解，我要做的这个 harness 是发挥了什么作用，如果只限定小型维护任务。

智能体重新解释：

> 它不是只能做小事，而是把小型维护任务变成可控、可解释、可复现的 agent 工作单元。

我进一步要求：

> 我想要一个功能需求。

最终我确认边界：

> 单仓库，有相关模块，可由测试验证，不涉及大规模架构重构，但是支持中小规模的重构，不涉及外部服务上线。

**处理决策**

推翻“轻量级小型维护任务”定位，改为“中量级上下文型 Coding Agent Harness”。

**影响**

SPEC 的范围变成：支持单仓库中小功能开发，可跨相关模块，可做局部重构，但不做跨仓库、外部上线和大型架构重写。

### 迭代四：自修复轮次

**对话节选**

智能体建议：

> 自修复循环默认最多 3 轮。

我修改：

> 6 轮。

智能体补充：

> 改为默认最多 6 轮；如果连续两轮失败类型和关键错误位置没有变化，则提前停止。

**处理决策**

采纳 6 轮自修复，但增加重复失败提前停止条件。

**影响**

这样既给中量级功能任务足够修复空间，又避免 agent 无限循环。

### 迭代五：系统架构表达

**对话节选**

智能体先提出架构描述。我后来给出一版更明确的结构：

> 系统可以分为：交互入口层、任务编排层、上下文层、模型调用层、工具执行层、验证反馈层、存储审计层。其中 Agent Runner 是核心主循环。

智能体回应：

> 这版更清楚，我建议直接采用它作为 SPEC 里的系统架构与数据流主体。

**处理决策**

采纳我修正后的架构版本，并补充 schema 校验失败和 guardrail 拒绝也属于反馈信号。

**影响**

SPEC 的系统架构更清楚地划分了 Core Service、Agent Runner、Context Engine、LLMClient、Action Parser、Guardrail、Tool Dispatcher、Feedback Engine 和 Audit Store 的职责。

## 4. AI 建议的采纳、修正与推翻

### 4.1 采纳的 AI 建议

1. **把上下文机制作为主贡献**

   采纳原因：它最符合我对 harness 价值的理解，也能体现课程要求中的“机制必须由代码实现”。

2. **CLI 为核心入口，WebUI 为观察和审批界面**

   采纳原因：CLI 更适合真实开发和 CI，WebUI 更适合展示上下文选择、运行轨迹和审批。

3. **结构化 JSON action 协议**

   采纳原因：它让工具调度、护栏、审计和 MockLLM 测试都有明确边界。

4. **配置优先、自动发现兜底的验证命令策略**

   采纳原因：真实仓库有自己的测试命令，自动发现能降低初始化成本，但不能覆盖用户配置。

5. **keyring 优先，`.env` 仅开发兜底**

   采纳原因：课程对凭据安全要求很硬，这个方案兼顾安全和开发便利。

6. **SQLite + JSONL 的存储审计方案**

   采纳原因：SQLite 适合结构化查询，JSONL 适合时间序列审计和课程展示。

7. **Python + Typer + FastAPI + pytest 技术栈**

   采纳原因：这套栈适合 CLI、WebUI/API、文件操作、子进程验证和测试。

### 4.2 我修正或推翻的 AI 建议

1. **推翻“轻量级”定位**

   原建议：上下文优先的轻量 harness。

   我的修正：改为中量级 harness，支持单仓库中小功能开发和中小规模局部重构。

   原因：轻量级定位不足以体现项目工程深度，也不能满足我希望它处理真实功能需求的目标。

2. **修改自修复轮次**

   原建议：最多 3 轮。

   我的修正：最多 6 轮，并保留重复失败提前停止。

   原因：中量级功能开发可能需要多轮反馈，3 轮偏少；但必须有停止条件。

3. **修正 WebUI 的理解**

   原理解：WebUI 可能只是为了满足课程要求。

   修正后：WebUI 是上下文解释、运行轨迹和审批机制的展示面。

   原因：如果 WebUI 没有机制价值，就会变成形式化交付物。

4. **重写系统架构表述**

   原建议：组件关系较概括。

   我的修正：明确分层为交互入口层、任务编排层、上下文层、模型调用层、工具执行层、验证反馈层、存储审计层。

   原因：分层后更容易在 SPEC 中表达模块职责、数据流和机制边界。

5. **要求中文版本**

   原结果：只有英文 `SPEC.md`。

   我的修正：要求另写中文版本，而不是覆盖英文版。

   原因：中文版本便于我阅读和检查，英文版本可保留为正式规格或对外材料。

## 5. SPEC 如何形成

SPEC 的形成过程遵循了“逐节确认”的方式。每一节设计都先由智能体提出，再由我确认或修正，然后进入下一节。

主要确认顺序如下：

1. 问题陈述与目标用户。
2. 用户故事与验收场景。
3. 功能模块与系统边界。
4. 领域与机制设计。
5. 系统架构与数据流。
6. 数据模型。
7. 功能规格与错误处理。
8. 非功能需求与安全威胁模型。
9. 技术选型、分发与部署。
10. 测试与验收标准。
11. 风险与未决问题。

在这些章节中，课程 A 类额外要求被显式纳入：

- agent 主循环必须自实现；
- 必须有可注入 MockLLM 的 LLM 抽象；
- 工具/action、反馈信号、危险动作、记忆都必须是代码机制；
- 机制必须能在移除真实 LLM 后用单元测试验证；
- 必须有凭据安全、分发、CI、WebUI 和机制演示。

SPEC 写入后做过一次自检，检查内容包括：

- 是否有 `TODO`、`TBD`、`FIXME`；
- 是否覆盖 MockLLM、Guardrail、ContextPackage、keyring、Docker、WebUI、`unit-test`；
- 是否前后一致地保持“上下文为主贡献，自修复为辅助能力”。

## 6. Brainstorming 技能做得好的地方

1. **强制把模糊想法变成具体边界**

   如果没有逐问逐答，项目很容易停留在“做一个 harness”的大概念。Brainstorming 把问题拆成主贡献、目标用户、任务范围、架构边界、数据模型、安全模型等部分，让 spec 更可执行。

2. **避免过早进入实现**

   一开始我明确要求只执行 brainstorming，不写实现代码。这个流程确实帮助我先把“做什么、为什么做、做到什么程度”说清楚。

3. **推动我质疑 AI 的建议**

   当 AI 提出“轻量级”“小型维护任务”“3 轮修复”时，我并没有直接接受，而是追问或修正。这个过程让最终设计更贴合我的真实需求。

4. **让课程要求自然进入设计**

   凭据安全、MockLLM、可测试机制、分发、WebUI、CI、机制演示等要求都在 brainstorming 中被逐步纳入，而不是最后才硬塞。

5. **逐节确认降低返工**

   每一节确认后再进入下一节，使 SPEC 形成过程比较稳定，也让我能在局部及时修正方向。

## 7. Brainstorming 技能让我不满的地方

1. **有时倾向于保守缩小范围**

   智能体最初建议“小型维护任务”或“轻量 harness”，这虽然有利于控制范围，但不完全符合我希望做中量级项目的目标。需要我主动指出项目价值不足。

2. **有些概念需要二次解释**

   例如“主贡献”“WebUI 的作用”“大型多 agent 平台”等概念，一开始并不直观，需要追问后才变清楚。

3. **默认文档输出曾经偏英文**

   `SPEC.md` 先写成英文，对我阅读不方便。后来补了 `SPEC.zh.md`，但这说明智能体应该更早确认文档语言偏好。

4. **过程文档没有在第一时间补齐**

   `SPEC_PROCESS.md` 是课程要求之一，但在最初完成 SPEC 后没有立即生成。这个遗漏说明 brainstorming 流程虽然帮助形成设计，但仍需要对课程交付清单做显式 checklist。

## 8. 结论

这次 Superpowers brainstorming 的最大价值，是把一个模糊的“Coding Agent Harness”想法，逐步收敛成了一个有主贡献、有边界、有测试策略、有安全模型、有分发计划的工程规格。

我没有完全照单全收 AI 的建议，而是在关键点上做了修正：

- 从轻量级改为中量级；
- 从小型维护改为中小功能开发；
- 从 3 轮修复改为 6 轮；
- 强化 WebUI 的解释和审批价值；
- 强化系统架构分层；
- 保留中文规格文档以便审阅。

因此，最终的 `SPEC.md` 不是单纯由 AI 生成的答案，而是经过人机共同质询、修正和确认后的设计结果。

## 9. PLAN 如何形成

在完成 `SPEC.md` 和 `SPEC.zh.md` 之后，我继续要求智能体使用 Superpowers 的 `writing-plans` skill，根据 `SPEC.md` 创建实现计划。这个阶段的重点已经不是继续发散需求，而是把规格文档拆成可执行、可验证、适合 subagent 分派的任务序列。

### 9.1 计划生成的输入与约束

我给出的要求包括：

- 每个 task 控制在一个 subagent 的一次会话内完成；
- 每个 task 写明目标、涉及文件、实现要点；
- 明确先写哪个失败测试；
- 写出具体验证命令；
- 标记 task 依赖关系；
- 标记可以并行执行的 task；
- 此时仍然不要编写实现代码。

智能体先读取 `superpowers:writing-plans` 的说明，再读取 `SPEC.md` 和仓库文件结构。由于当时仓库基本只有规格文档，智能体判断这是一个从零开始的 Python harness，于是先在计划中锁定模块边界，再拆 task。

### 9.2 Plan 阶段的关键决策

**第一，先固定文件结构，再拆任务。**

`writing-plans` skill 要求在定义任务前先映射文件结构。智能体据此列出 `harness/domain.py`、`harness/storage.py`、`harness/profiler.py`、`harness/repo_index.py`、`harness/context_engine.py`、`harness/memory.py`、`harness/actions.py`、`harness/guardrails.py`、`harness/tools.py`、`harness/feedback.py`、`harness/runner.py`、`harness/service.py`、`harness/cli.py`、`harness/api.py`、`harness/webui.py` 等模块。这个决策把 SPEC 中的架构层次转成了清晰的代码边界。

**第二，把 Task 1 设为所有任务的基础。**

智能体把 project skeleton、domain model、SQLite storage 和 JSONL audit store 合并成 Task 1。这个安排是合理的，因为后续 profiler、context、memory、action、guardrail、runner 都依赖统一的数据模型和存储接口。如果先写其他模块，容易出现类型和持久化结构反复变化。

**第三，把可并行任务显式标出来。**

计划中明确写出 Tasks 2、3、4、5 在 Task 1 后可以并行，Tasks 9、10 在 Task 8 后可以并行，Task 11 可以与部分核心机制任务并行。这满足了我对 subagent 一次会话粒度的要求，也让后续执行时可以用 `subagent-driven-development` 分派。

**第四，坚持 TDD，把每个 task 的第一个失败测试写清楚。**

每个 task 都有一个明确的 first failing test，例如：

- Task 1：`tests/test_storage.py::test_storage_creates_task_run_and_audit_event`；
- Task 5：`tests/test_actions.py::test_unknown_action_becomes_schema_feedback_and_is_not_executable`；
- Task 6：`tests/test_guardrails.py::test_path_traversal_read_is_denied_before_dispatch`；
- Task 8：`tests/test_context_engine.py::test_context_package_includes_code_test_convention_and_memory_reasons`；
- Task 10：`tests/test_runner.py::test_invalid_action_from_mock_llm_becomes_feedback_without_tool_execution`。

这让计划不是单纯的模块清单，而是可以直接驱动实现的测试计划。

### 9.3 至少三轮 plan 相关关键迭代

#### 迭代一：从 SPEC 转成英文 `PLAN.md`

**对话节选**

我要求：

> 使用 Superpowers 的 writing-plans skill，根据 SPEC.md 创建 PLAN.md。

并补充：

> 每个 task 控制在一个 subagent 的一次会话内完成；明确失败测试、验证命令、依赖关系、并行关系；此时不要编写实现代码。

智能体处理：

> 先加载 `using-superpowers` 和 `writing-plans`，再读取 `SPEC.md` 和项目结构。

**处理决策**

采纳智能体生成的 13 个 task 结构：从 project skeleton 和 storage 开始，依次覆盖 profiler、repo index、memory、action parser、guardrails、tools、context engine、feedback、LLM/runner、auth/report、service/CLI/API/WebUI、Docker/CI/README/E2E demo。

**影响**

`PLAN.md` 把 `SPEC.md` 的大规格拆成了可执行任务，并且每个任务都能用单独 subagent 完成。它还避免了过早写实现代码。

#### 迭代二：补写中文计划，但不覆盖英文计划

**对话节选**

我要求：

> 写一版中文的，新写一版，不要改原版。

智能体处理：

> 新建 `PLAN.zh.md`，保留英文 `PLAN.md` 不动。

**处理决策**

采纳“双版本计划”的方式。英文 `PLAN.md` 保留为较正式的实现计划，中文 `PLAN.zh.md` 方便我阅读、检查和后续分派。

**影响**

计划文档和 SPEC 文档保持了一致的双语结构：`SPEC.md` / `SPEC.zh.md`，`PLAN.md` / `PLAN.zh.md`。这降低了我审阅任务拆分时的理解成本。

#### 迭代三：补齐过程文档中的 plan 部分

**对话节选**

我发现：

> `SPEC_PROCESS.md` 这个似乎没有完成，你来完成 plan 部分。

智能体处理：

> 读取已有 `SPEC_PROCESS.md`、`PLAN.md`、`PLAN.zh.md` 和 `AGENT_LOG.md`，只补充 plan 协作过程，不重写已有 SPEC 过程内容。

**处理决策**

这次没有改动 `PLAN.md` 或 `PLAN.zh.md`，而是在 `SPEC_PROCESS.md` 中追加本节，说明 plan 是如何从 spec 生成的、有哪些关键拆分决策、哪些建议被采纳或修正。

**影响**

过程文档从“只记录 SPEC brainstorming”补充为“同时记录 SPEC 与 PLAN 的协作过程”，更贴合课程交付物 3 的要求。

### 9.4 AI 在 plan 阶段提出且我采纳的建议

1. **先建立文件结构，再拆任务**

   采纳原因：这让模块职责先稳定下来，避免 task 拆分只是按照 SPEC 章节机械切割。

2. **把存储和领域模型放入 Task 1**

   采纳原因：后续所有机制都依赖统一的数据模型、状态枚举和审计记录。先做这个基础层，可以减少后续 task 之间的接口冲突。

3. **每个 task 都绑定一个 first failing test**

   采纳原因：这符合 TDD，也让 subagent 执行时有明确的 RED/GREEN 起点。

4. **显式写出依赖和并行关系**

   采纳原因：后续使用 subagent 执行时，可以知道哪些任务必须串行，哪些任务可以并行。

5. **把 Docker、CI、README 和 E2E demo 放到最后一个 task**

   采纳原因：这些内容依赖核心机制基本完成，放在最后更符合验证和交付顺序。

### 9.5 我修正或补充的 plan 要求

1. **要求中文计划另写一版，不覆盖原版**

   原始结果只有英文 `PLAN.md`。我要求新建中文版本，因此形成了 `PLAN.zh.md`。这样保留了英文计划的正式性，也提高了中文审阅效率。

2. **强调每个 task 必须适合 subagent 一次会话**

   这个约束来自我的明确要求。它让计划没有把所有模块堆成几个巨大阶段，而是拆成 13 个较小、可测试、可审查的任务。

3. **强调计划阶段不写实现代码**

   这防止智能体从计划直接跳到实现。最终产出只包括 `PLAN.md` 和 `PLAN.zh.md`，没有在该阶段创建 Python 实现文件。

### 9.6 对 writing-plans 技能的反思

**做得好的地方**

1. 它强制把规格拆成小任务，而不是停留在“实现 Core Service、实现 WebUI”这种粗粒度描述。

2. 它要求每个 task 都写 first failing test 和验证命令，让计划天然适合 TDD 和课程验收。

3. 它要求依赖关系和并行关系显式化，这对 subagent-driven development 很有帮助。

4. 它会做 self-review，例如扫描占位词、检查 SPEC 覆盖，这降低了计划文档漏项的风险。

**让我不满或需要人工修正的地方**

1. 默认保存位置和文档语言不一定符合我的偏好。skill 默认建议 `docs/superpowers/plans/...`，但我需要根目录 `PLAN.md`；第一次输出也是英文，需要我再要求中文版本。

2. 计划容易非常长。虽然这对执行有帮助，但阅读成本较高，所以中文版本对我很重要。

3. 它主要关注实现计划本身，不会自动补齐课程要求的过程文档。因此 `SPEC_PROCESS.md` 的 plan 部分需要我额外提醒后才补上。

### 9.7 Plan 阶段结论

`PLAN.md` 和 `PLAN.zh.md` 不是简单把 `SPEC.md` 改写成任务列表，而是把规格中的机制边界、数据模型、测试策略、安全要求和交付要求，重组为可由 subagent 分批执行的 TDD 任务序列。

这个阶段最大的价值是把“要做什么”进一步变成“先测什么、改哪些文件、如何验证、哪些任务可并行”。因此，PLAN 是 SPEC 到实现之间的桥梁，也是后续 subagent 执行和验收的依据。
