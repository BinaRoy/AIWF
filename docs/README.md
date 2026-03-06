# AIWF Development Docs

This folder contains the baseline docs for developing AIWF with predictable process and auditable outputs.

## Document Map

- `architecture/2026-03-06-current-architecture-baseline.md`
  - Current architecture boundaries, runtime flow, and data contracts.
- `process/2026-03-06-governance-and-stage-gates.md`
  - Stage governance, DoD checks, and evidence requirements.
- `process/2026-03-06-development-playbook.md`
  - Step-by-step execution playbook for daily development.
- `plans/2026-03-06-aiwf-core-hardening-implementation-plan.md`
  - Next-phase implementation plan broken into executable tasks.

## How to Use

1. Read the architecture baseline first.
2. Use governance/stage-gate doc as the process contract during development.
3. Follow the development playbook for day-to-day execution.
4. Execute the implementation plan task-by-task.

## Mandatory Process Defaults

- Always sync from remote before coding (`fetch + rebase/merge`).
- Never develop feature work directly on default branch.
- After verification, open PR, pass checks/review, then merge.

## Quick Execution Path

Run these in order for each task:

1. `git fetch origin && git rebase origin/main`
2. `aiwf pr-check`
3. `pytest -q`
4. `aiwf verify`
5. `aiwf validate-state`
6. `aiwf validate-artifacts`
7. `aiwf audit-summary`
8. Push branch and open PR, merge after checks/review pass.
