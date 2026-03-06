# AIWF 闭环流程地图（可索引执行版）

Date: 2026-03-06

## 1. 入口

从这三个入口开始：

1. `README.md`（项目定位与快速上手）
2. `docs/README.md`（文档导航索引）
3. 本文档（闭环步骤图 + 命令 + 产物）

## 2. 单任务闭环（从开始到放行）

### Step A: 准备上下文

输入：
- 功能分支
- 最新远端代码

命令：
```bash
git fetch origin
git checkout <feature-branch>
git rebase origin/dev
aiwf pr-check
```

通过条件：
- `aiwf pr-check` 返回 0

### Step B: 闭环主判定

命令：
```bash
aiwf roles autopilot --verify
```

内部会自动执行：
- `verify`
- plan/self/loop/roles 判定
- 角色状态自动推进并落盘

通过条件：
- `autopilot` 返回 0

失败处理：
- 读取 `autopilot` 输出中的 `checks`
- 修复对应项后重跑

### Step C: 审计摘要

命令：
```bash
aiwf audit-summary
```

输出用于：
- 人工评审
- PR 描述中的证据引用

### Step D: 合并前要求

必须同时满足：
- `aiwf roles autopilot --verify` 成功
- `aiwf audit-summary` 可读
- PR（feature -> dev）检查通过、审核通过

### Step E: 阶段性发布同步

当 `dev` 达到阶段目标后：
- 发起 `dev -> main` PR
- 重跑同一闭环检查
- 合并到 `main`

## 3. 关键落盘产物（证据链）

- `.ai/state.json`
- `.ai/runs/<run_id>/run.json`
- `.ai/artifacts/reports/*.json`
- `.ai/telemetry/events.jsonl`
- `.ai/roles_workflow.json`
- `.ai/plan.json`
- `.ai/risk_register.json`（如启用）

## 4. Agent 跟随规则（建议写入 AGENTS.md）

Agent 每次任务必须遵循：

1. 先执行 `aiwf pr-check`
2. 开发后执行 `aiwf roles autopilot --verify`
3. 生成 `aiwf audit-summary`
4. 失败则修复，不进入 PR 合并阶段

不允许：
- 跳过闭环主判定
- 仅口头声明“已完成”但没有 `.ai` 证据
