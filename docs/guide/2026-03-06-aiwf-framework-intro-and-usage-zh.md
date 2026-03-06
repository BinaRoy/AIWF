# AIWF 框架功能介绍与使用指南（中文）

Date: 2026-03-06

## 1. 这个框架规范了什么

AIWF 不是单纯的命令集合，而是一套“可执行的工程治理规范”。它主要规范了：

1. 开发阶段规范  
- 用统一阶段表示项目状态（INIT/SPEC/PLAN/DEV/VERIFY/SHIP/DONE/FAILED）。

2. 证据与审计规范  
- 每次验证都必须生成可追溯工件（run record、gate report、telemetry）。

3. 契约规范  
- 用 JSON Schema 约束关键数据结构（state、plan、risk、roles、gate/run artifact）。

4. 流程门禁规范  
- 用 policy、PR 规则、固定闭环检查阻止“绕流程开发”。

5. 多角色协作规范  
- 用角色工作流（planner/implementer/reviewer/tester/supervisor）形成可判定交接。

## 2. 这个框架已经实现了什么

核心能力（当前已可用）：

- 工作区初始化：`aiwf init --self-hosted`
- 验证执行：`aiwf verify`
- 契约校验：`aiwf validate-state`、`aiwf validate-artifacts`
- 监管摘要：`aiwf audit-summary`
- 闭环检查：`aiwf self-check`、`aiwf loop-check`
- 角色编排：`aiwf roles init/status/check/update/autopilot`
- 风险治理：`aiwf risk status/waive`
- PR 门禁：`aiwf pr-check/pr-status`
- CI 自动闭环：PR 中可用 `aiwf roles autopilot --verify` 作为单入口门禁

## 3. 在全新工程中，如何结合 Agent 高效开发

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
aiwf roles autopilot --verify
aiwf audit-summary
```

解释：
- `roles autopilot --verify` 会自动执行验证并根据结果推进角色状态。
- `audit-summary` 提供统一视图，便于人和 Agent 做继续/阻断决策。

### 3.4 PR 与 CI

在 CI 中同样跑：

1. `aiwf init --self-hosted`
2. `aiwf roles init`
3. `aiwf roles autopilot --verify`
4. `aiwf audit-summary`

保证“本地规则”和“PR 规则”一致，避免本地过、线上挂的流程分叉。

## 4. 有效利用这个框架的建议

1. 把 `roles autopilot --verify` 当作唯一放行入口  
- 不要同时维护多套“手工检查清单”。

2. 让 Agent 输出“证据导向结果”，不是口头结论  
- 例如：run_id、gate report、summary JSON。

3. 对高风险变更提前建 risk 条目  
- 用 `aiwf risk waive` 管理临时豁免并设置过期时间。

4. 限制“无计划编码”  
- 没有 `.ai/plan.json` 或 plan 不合法时，不进入实现阶段。

5. 统一约束入口写入 `AGENTS.md`  
- 明确必跑命令和失败后的处理方式，降低协作偏差。

## 5. 一句话实践原则

让 AIWF 负责“流程是否合规、证据是否完整”，让 Agent 负责“实现与迭代速度”。二者分工清晰，才能在速度和质量之间保持稳定。
