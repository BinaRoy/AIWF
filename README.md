# AIWF (AI Workflow Framework)

AIWF 是一个面向 Agent 协作开发的“流程执行层”。  
它把研发过程中的阶段、门禁、证据、审计统一成可执行命令，目标是让“规范开发”从文档约定变成机器可判定。

## This Project Solves

- 让开发流程可追踪：状态、计划、角色、风险都落盘到 `.ai/`
- 让质量门禁可执行：`verify` / `validate-*` / `self-check` / `loop-check`
- 让多角色协作可判定：`roles init/update/check/autopilot`
- 让 CI 与本地流程一致：PR 中走同一条闭环命令链

## Quickstart (Local)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 初始化自托管默认配置
aiwf init --self-hosted
aiwf roles init

# 单入口闭环检查（推荐）
aiwf roles autopilot --verify
aiwf audit-summary
```

## Core Closed-Loop Command

推荐把以下命令作为“唯一放行入口”：

```bash
aiwf roles autopilot --verify
```

语义：
- 自动执行验证（`verify`）
- 自动汇总并判定 `plan/self/loop/roles` 检查
- 自动推进角色状态并落盘到 `.ai/roles_workflow.json`
- 任一关键检查失败返回非 0

## Develop Contract (M1)

`aiwf develop` 在 M1 中被定义为“一次受控开发推进运行单元”。

规范入口文档（SoT）：
- `docs/process/2026-03-09-develop-command-contract.md`

说明：
- 旧流程文档继续保留用于追溯；
- 若与 develop 行为定义有冲突，以上述 SoT 为准。

## New Project + Agent Workflow

在全新工程里，建议固定执行顺序：

```bash
git fetch origin
git checkout <feature-branch>
git rebase origin/dev
aiwf pr-check

aiwf roles autopilot --verify
aiwf audit-summary
```

如果 `autopilot` 失败，不进入合并阶段，先按输出的失败项修复再重跑。

## CI Enforcement (PR)

CI workflow: `.github/workflows/aiwf-verify.yml`

PR 到 `dev` 或 `main` 时，CI 执行：
1. `aiwf init --self-hosted`
2. seed minimal `.ai/plan.json` + `aiwf roles init`
3. `aiwf roles autopilot --verify`
4. `aiwf audit-summary`

并上传 `.ai` 证据：
- `.ai/state.json`
- `.ai/runs/`
- `.ai/artifacts/reports/`
- `.ai/telemetry/events.jsonl`

## Branch Strategy (main + dev)

- `main`: 默认分支，仅用于阶段性稳定发布
- `dev`: 日常开发集成分支（feature 分支通过 PR 合入 `dev`）

日常开发：
1. 从 `dev` 拉最新并切功能分支
2. 功能分支通过 PR 合入 `dev`

阶段发布：
1. 从 `dev` 开 PR 到 `main`
2. 通过同样闭环检查后合入

建议在 `.ai/config.yaml` 中配置受保护分支：

```yaml
git:
  remote: origin
  default_branch: dev
  protected_branches:
    - main
    - dev
  require_pr: true
```

## Repo Layout

- `src/aiwf/`: CLI 与工作流引擎实现
- `schemas/`: 关键契约（state/plan/risk/roles/run/gate）
- `docs/`: 架构、流程、SOP、计划、中文指南
- `.ai/`: 运行态与审计证据目录

## Documentation Entry

完整流程导航见：
- `docs/README.md`
- `docs/process/2026-03-06-closed-loop-flow-map.md`
- `docs/guide/2026-03-06-aiwf-framework-intro-and-usage-zh.md`
