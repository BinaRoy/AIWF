# AIWF Development Docs

本目录用于维护 AIWF 当前开发文档、边界说明和历史追溯材料。

默认规则：
- 默认先读当前 SoT
- historical 文档只用于追溯，不用于当前实现、对外表述、CLI help、CI 口径复用
- 后续文档默认以中文版主叙事为优先，除必要术语外不再混合首页叙事

## Current Source of Truth

- `process/2026-03-09-development-requirements-entry.md`
  - Active SoT for development requirements priority and execution order.
- `process/2026-03-09-develop-command-contract.md`
  - Active SoT for `aiwf develop` M1 contract, run/artifact boundary, and exit code semantics.
  - Older docs remain as historical records; if there is overlap, follow this doc first.
- `architecture/2026-03-10-m1-product-boundary-and-entrypoint.md`
  - Active positioning note for M1 boundary, supported usage framing, and primary entry-point semantics.

## Current Working Docs

- `architecture/2026-03-10-m1-product-boundary-and-entrypoint.md`
  - M1 product boundary and primary entry-point clarification.
- `process/2026-03-09-development-requirements-entry.md`
  - Unified entry for active development requirements and priority.
- `process/2026-03-09-develop-command-contract.md`
  - M1 contract for controlled `develop` runs and evidence correlation.
- `guide/2026-03-06-aiwf-framework-intro-and-usage-zh.md`
  - Chinese introduction and usage guide for new-project onboarding with agents.

## Historical Docs

These are retained for traceability only. They are not current SoT.

- `architecture/2026-03-06-current-architecture-baseline.md`
  - Early architecture baseline before M1 entry-point and boundary convergence.
- `process/2026-03-06-governance-and-stage-gates.md`
  - Historical process contract note.
- `process/2026-03-06-development-playbook.md`
  - Historical daily execution playbook.
- `process/2026-03-06-multi-role-sop.md`
  - Historical role-process note.
- `process/2026-03-06-closed-loop-flow-map.md`
  - Historical command-level flow map.
- `plans/2026-03-05-aiwf-phased-development.md`
  - Historical phased implementation plan.
- `plans/2026-03-06-aiwf-core-hardening-implementation-plan.md`
  - Historical hardening plan.
- `plans/2026-03-06-aiwf-self-hosting-direction-plan.md`
  - Historical self-hosting direction plan.

## How to Use

1. Read `process/2026-03-09-development-requirements-entry.md`.
2. Read `process/2026-03-09-develop-command-contract.md`.
3. Read `architecture/2026-03-10-m1-product-boundary-and-entrypoint.md`.
4. Use the guide and current process docs when updating README, CI, or help text.
5. Only consult historical docs when you need lineage or rationale.

## Mandatory Process Defaults

- Always sync from remote before coding (`fetch + rebase/merge`).
- Never develop feature work directly on default branch.
- After verification, open PR, pass checks/review, then merge.

## Quick Execution Path

Run these in order for each task:

1. `git fetch origin && git rebase origin/dev`
2. `aiwf pr-check`
3. `aiwf develop`
4. `aiwf audit-summary`
5. Push branch and open PR to `dev`, merge after checks/review pass.
6. On release milestone, open `dev -> main` PR and pass the same checks.
