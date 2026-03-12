# AIWF 框架功能介绍与使用指南（中文）

Date: 2026-03-06

## 1. 这个框架规范了什么

AIWF 不是单纯的命令集合，而是一套“可执行的流程运行时约束”。它主要规范了：

1. 开发阶段规范  
- 用统一阶段表示项目状态（INIT/SPEC/PLAN/DEV/VERIFY/SHIP/DONE/FAILED）。

2. 证据与审计规范  
- 每次验证都必须生成可追溯工件（run record、gate report、telemetry）。

3. 契约规范  
- 用 JSON Schema 约束关键数据结构（state、plan、risk、roles、gate/run artifact）。

4. 流程门禁规范  
- 用 policy、PR 规则、固定闭环检查阻止“绕流程开发”。

5. 角色状态治理
- 用角色工作流（planner/implementer/reviewer/tester/supervisor）记录可判定协作状态与证据映射。

## 1.1 当前版本边界

当前版本应按 M1 理解：

- 只覆盖 workspace initialization、workflow state、basic development loop、verification gates、artifact recording
- 当前更适合 Python self-hosted repository
- 当前不是“任意工程可直接通用接入”的插件化平台
- 当前不是全能治理系统
- `roles` 当前是角色状态治理能力，不是严格意义上的多角色协作编排系统
- `dispatch` 当前是 run 级 work item / handoff / transition 记录骨架，不是完整多 Agent 调度器

## 2. 这个框架已经实现了什么

核心能力（当前已可用）：

- 工作区初始化：`aiwf init --self-hosted`
- 主闭环入口：`aiwf develop`
- 验证执行：`aiwf verify`
- 契约校验：`aiwf validate-state`、`aiwf validate-artifacts`
- 监管摘要：`aiwf audit-summary`
- 闭环检查：`aiwf self-check`、`aiwf loop-check`
- 角色状态治理：`aiwf roles init/status/check/update/autopilot`
- 调度记录骨架：`aiwf dispatch init/add-item/handoff/transition/status`
- 风险治理：`aiwf risk status/waive`
- PR 门禁：`aiwf pr-check/pr-status`
- CI 自动闭环：PR 中以 `aiwf develop` 作为唯一主入口

## 3. 在 Python self-hosted 工程中，如何结合 Agent 高效开发

### 3.1 初始化（一次性）

```bash
aiwf init --self-hosted
aiwf roles init
```

### 3.2 建议的最小文档骨架

先让 Agent 产出并维护：

- `docs/specs/<date>-problem-statement.md`
- `docs/plans/<date>-implementation-plan.md`
- `.ai/plan.json`
- `AGENTS.md`（明确“先文档后实现”和必跑命令）

### 3.3 每个任务的闭环命令链（建议固定）

```bash
git fetch origin
git checkout <feature-branch>
git rebase origin/main
aiwf pr-check
aiwf develop
aiwf audit-summary
```

解释：
- `aiwf develop` 是唯一主闭环入口。
- `aiwf verify` 是底层 gate executor，可独立调用，但不是主放行入口。
- `roles autopilot` 只负责辅助角色状态推进，不承担主闭环入口语义。
- `dispatch` 只负责记录本次 run 内的 work item / handoff / transition，不替代 `develop`。
- `audit-summary` 提供统一视图，便于人和 Agent 做继续/阻断决策。

### 3.4 PR 与 CI

在 CI 中同样跑：

1. `aiwf init --self-hosted`
2. `aiwf roles init`
3. `aiwf develop`
4. `aiwf audit-summary`

保证“本地规则”和“PR 规则”一致，避免本地过、线上挂的流程分叉。

## 4. 有效利用这个框架的建议

1. 把 `aiwf develop` 当作唯一主放行入口
- 不要同时维护多套“手工检查清单”。

2. 把 `roles` 理解为角色状态治理，而不是完整协作编排
- 它当前更像可判定的协作状态与证据映射。

3. 把 `dispatch` 理解为 run 内调度留痕，而不是多 Agent 执行器
- 它当前解决的是“本次 run 里发生了哪些任务流转”，不是“自动调度谁去做”。

4. 让 Agent 输出“证据导向结果”，不是口头结论
- 例如：run_id、gate report、summary JSON。

5. 对高风险变更提前建 risk 条目
- 用 `aiwf risk waive` 管理临时豁免并设置过期时间。

6. 限制“无计划编码”
- 没有 `.ai/plan.json` 或 plan 不合法时，不进入实现阶段。

7. 统一约束入口写入 `AGENTS.md`
- 明确必跑命令和失败后的处理方式，降低协作偏差。

## 5. 一句话实践原则

让 AIWF 负责“流程是否合规、证据是否完整”，让 Agent 负责“实现与迭代速度”。二者分工清晰，才能在速度和质量之间保持稳定。
