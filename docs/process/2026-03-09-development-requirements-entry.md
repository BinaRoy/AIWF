# AIWF 开发需求入口（M1）

Date: 2026-03-09  
Status: Active Source of Truth (SoT) for development requirements.

## 1. 目的

本文件是 AIWF 当前阶段的“开发需求入口”。  
后续开发优先以本文件定义的需求顺序执行，避免需求分散在多个文档中导致偏航。

如果与历史文档冲突：
1. 以本文件为准（需求优先级与执行顺序）
2. `2026-03-09-develop-command-contract.md` 作为 `aiwf develop` 行为合同

## 2. M1 边界（不扩框架体积）

M1 只覆盖：
- workspace initialization
- workflow state management
- basic development loop
- verification gates
- artifact recording

不做：
- 大规模模块拆分
- 新增复杂插件体系
- “全能型平台化”扩展

## 3. 固定执行顺序（每个任务）

1. 同步分支：`git fetch origin` + 基于 `dev` 开功能分支
2. 前置检查：`aiwf pr-check`
3. 开发推进：`aiwf develop`（必要时 `--no-verify` 仅作 preflight）
4. 审计摘要：`aiwf audit-summary`
5. 提交 PR：`feature -> dev`
6. CI 通过后合并；阶段性再 `dev -> main`

## 4. 当前需求池（按优先级）

### R1（进行中）统一单入口

- 目标：在文档与 CI 中明确 `aiwf develop` 为主入口
- 完成标准：README/docs/CI 的主路径一致

### R2（待做）run-artifact 关联强化

- 目标：按 `last_run_id` 能清晰判断本次 run 证据完整性
- 完成标准：`run.json` + `develop.json` + gate reports 关联可机器判定

### R3（待做）exit code 契约固化

- 目标：`develop` 的 `0/1/2` 语义在 CLI/help/tests/文档一致
- 完成标准：失败类型可稳定分类，无歧义

### R4（待做）最小 SOP 固化

- 目标：给 agent/开发者一页可跟随的最小闭环 SOP
- 完成标准：新成员按 SOP 可独立完成一次 feature->dev 提交流程

## 5. 维护规则

1. 只在本文件维护“当前有效需求列表和优先级”
2. 新需求进入时必须标注：目标、边界、完成标准
3. 已完成需求移到“历史记录”并保留日期
4. 每次 PR 若影响开发流程，必须检查并更新本文件

## 6. 历史记录（M1）

- 2026-03-09：建立固定开发需求入口文档，作为需求调度单一入口。
- 2026-03-09：将该入口文档挂接到 develop contract / playbook / closed-loop flow-map，形成一致索引链路。
