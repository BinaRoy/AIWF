# AIWF Multi-Role Development SOP

Date: 2026-03-06

## 1. Role Model

Use fixed roles for one development cycle:
- `planner`: scope, plan, and acceptance criteria
- `implementer`: code changes and local checks
- `reviewer`: design/code risk review and fix requests
- `tester`: scenario validation and regression checks
- `supervisor`: process compliance and ship decision

Role contract file: `.ai/roles_workflow.json`

## 2. Bootstrap

```bash
aiwf init --self-hosted
aiwf roles init
```

Then confirm role workflow state:

```bash
aiwf roles status
aiwf roles check
```

## 3. Single-Cycle Execution

1. Planner
- write/update plan in `docs/plans/`
- define completion criteria and test commands

2. Implementer
- implement minimal scoped changes
- run targeted tests
- run `aiwf verify`

3. Reviewer
- review risks and policy alignment
- ensure required evidence is attached

4. Tester
- run regression checks
- run contract checks:
  - `aiwf validate-state`
  - `aiwf validate-artifacts`
  - `aiwf self-check`
  - `aiwf loop-check`

5. Supervisor
- run `aiwf audit-summary`
- run `aiwf roles check`
- decide ship/no-ship

## 4. Machine-Gated Commands

- `aiwf roles status`: count roles by status
- `aiwf roles update <role>`: update role state/evidence
  - example:
    - `aiwf roles update planner --status completed --evidence docs/plans/x.md`
    - `aiwf roles update implementer --status in_progress --owner codex`
- `aiwf roles check`: fail when handoff contract is broken
  - completed role without evidence
  - out-of-order completion
  - more than one role in progress

## 5. Merge Rules

Only allow PR merge when all are true:
- `aiwf verify` succeeds
- `aiwf self-check` succeeds
- `aiwf loop-check` succeeds
- `aiwf roles check` succeeds
- PR checks/review pass

If any fails, cycle remains open.
