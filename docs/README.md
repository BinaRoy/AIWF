# AIWF Development Docs

This folder contains the baseline docs for developing AIWF with predictable process and auditable outputs.

## Document Map

- `architecture/2026-03-06-current-architecture-baseline.md`
  - Current architecture boundaries, runtime flow, and data contracts.
- `process/2026-03-06-governance-and-stage-gates.md`
  - Stage governance, DoD checks, and evidence requirements.
- `process/2026-03-06-development-playbook.md`
  - Step-by-step execution playbook for daily development.
- `process/2026-03-06-multi-role-sop.md`
  - Multi-role SOP for assignment, implementation, supervision, and testing.
- `process/2026-03-06-closed-loop-flow-map.md`
  - Closed-loop flow map with command-level checkpoints and evidence chain.
- `guide/2026-03-06-aiwf-framework-intro-and-usage-zh.md`
  - Chinese introduction and usage guide for new-project onboarding with agents.
- `plans/2026-03-06-aiwf-core-hardening-implementation-plan.md`
  - Next-phase implementation plan broken into executable tasks.

## How to Use

1. Read the architecture baseline first.
2. Use governance/stage-gate doc as the process contract during development.
3. Follow the development playbook for day-to-day execution.
4. Use the closed-loop flow map as the command-level execution path.
5. Execute the implementation plan task-by-task.

## Mandatory Process Defaults

- Always sync from remote before coding (`fetch + rebase/merge`).
- Never develop feature work directly on default branch.
- After verification, open PR, pass checks/review, then merge.

## Quick Execution Path

Run these in order for each task:

1. `git fetch origin && git rebase origin/dev`
2. `aiwf pr-check`
3. `aiwf roles autopilot --verify`
4. `aiwf audit-summary`
5. Push branch and open PR to `dev`, merge after checks/review pass.
6. On release milestone, open `dev -> main` PR and pass the same checks.
