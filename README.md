# AIWF (AI Workflow Framework)

AIWF 是一个面向 Agent 协作开发的“流程执行层”。  
它把研发过程中的阶段、门禁、证据、审计统一成可执行命令，目标是让“规范开发”从文档约定变成机器可判定。

当前版本边界：
- M1 只覆盖 workspace initialization、workflow state management、basic development loop、verification gates、artifact recording，以及 run-scoped dispatch skeleton
- 当前默认落地形态是 Python self-hosted repository
- 当前不是通用插件化平台，也不是全能治理系统
- `roles` 当前表达的是角色状态治理与证据映射，不是严格的多角色协作编排系统
- `dispatch` 当前表达的是 run 内 work item / handoff / transition 的记录骨架，不是完整的多 Agent 调度执行器

## 非目标

- 不是通用仓库接入平台（not a universal repo integration platform）
- 不是通用插件系统（not a generic plugin system）
- 不是完整的多 Agent 编排引擎（not a full multi-agent orchestration engine）
- 不是完整的治理操作系统（not a complete governance operating system）

## 这个项目解决什么

- 让开发流程可追踪：状态、计划、角色、风险都落盘到 `.ai/`
- 让质量门禁可执行：`verify` / `validate-*` / `self-check` / `loop-check`
- 让角色状态可判定：`roles init/update/check/autopilot`
- 让 CI 与本地流程一致：PR 中走同一条闭环命令链

## 本地快速开始

```bash
python3 --version
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"

# 初始化自托管默认配置
aiwf init --self-hosted
aiwf roles init

# 单入口闭环检查（推荐）
aiwf develop
aiwf audit-summary
```

如果系统里没有 `python3` 或 `venv`：
- Ubuntu/Debian: `sudo apt-get install python3 python3-venv`
- macOS with Homebrew: `brew install python`
- Windows PowerShell: `py -3 -m venv .venv`

## 闭环主命令

推荐把以下命令作为“主放行入口”：

```bash
aiwf develop
```

语义：
- 以一个 `run_id` 组织一次受控开发推进
- 默认包含 roles sync + verify
- 输出 `verified` 状态用于区分 full/preflight
- 任一关键步骤失败返回非 0

相关能力：
- `aiwf verify`: 底层 gate executor，可独立调用
- `aiwf roles autopilot`: 辅助角色状态推进，不再承担主闭环入口语义
- `aiwf dispatch *`: 管理本次 run 的 work item / handoff / transition 记录，但不构成新的主闭环入口

## `develop` 行为合同（M1）

`aiwf develop` 在 M1 中被定义为“一次受控开发推进运行单元”。

规范入口文档（SoT）：
- `docs/process/2026-03-09-develop-command-contract.md`

说明：
- 旧流程文档继续保留用于追溯；
- 若与 develop 行为定义有冲突，以上述 SoT 为准。

## 开发需求入口（M1）

固定开发需求入口文档（SoT）：
- `docs/process/2026-03-09-development-requirements-entry.md`

说明：
- 当前阶段的需求优先级、执行顺序、边界与完成标准统一在该文档维护。

## Python 自托管仓库接入方式

当前更准确的接入方式是“把 AIWF 接入一个 Python self-hosted 仓库”。
建议固定执行顺序：

```bash
git fetch origin
git checkout <feature-branch>
git rebase origin/dev
aiwf pr-check

aiwf develop
aiwf audit-summary
```

如果 `develop` 失败，不进入合并阶段，先按输出的失败项修复再重跑。

不建议当前版本对外表述为“任意工程可直接通用接入”。
默认自托管配置仍明显依赖：
- `.ai/` 工作区
- git / PR 流程约束
- JSON Schema 契约
- Python / pytest gate 约定

## CI 执行（PR）

CI workflow: `.github/workflows/aiwf-verify.yml`

PR 到 `dev` 或 `main` 时，CI 执行：
1. `aiwf init --self-hosted`
2. 写入最小 `.ai/plan.json` 并执行 `aiwf roles init`
3. `aiwf develop`
4. `aiwf audit-summary`

并上传 `.ai` 证据：
- `.ai/state.json`
- `.ai/runs/`
- `.ai/artifacts/reports/`
- `.ai/telemetry/events.jsonl`

## 分支策略（`main` + `dev`）

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

## 仓库结构

- `src/aiwf/`: CLI 与工作流引擎实现
- `schemas/`: 关键契约（state/plan/risk/roles/run/gate/dispatch）
- `docs/`: 架构、流程、SOP、计划、中文指南
- `.ai/`: 运行态与审计证据目录

## 文档入口

完整流程导航见：
- `docs/README.md`
- `docs/process/2026-03-06-closed-loop-flow-map.md`
- `docs/guide/2026-03-06-aiwf-framework-intro-and-usage-zh.md`
- `docs/architecture/2026-03-10-m1-product-boundary-and-entrypoint.md`
