# AIWF Develop Command Contract (M1 SoT)

Date: 2026-03-09  
Status: Active Source of Truth (SoT) for `aiwf develop` in M1.

## 1. Scope

This document defines the contract for `aiwf develop` as a controlled development run unit.
For any overlap, this document has higher priority than older process docs.
Active requirements priority/order is maintained in:
- `2026-03-09-development-requirements-entry.md`

## 2. Command Definition

`aiwf develop` is an orchestrated run, not a plain alias.
One invocation corresponds to one `run_id`.

Default behavior:
1. Validate plan contract (precondition)
2. Run role sync step (default enabled)
3. Run verification step (default enabled)
4. Initialize or reuse the run-scoped dispatch record
5. Write run artifacts and summary

## 3. Input Contract

CLI options (M1 minimal):
- `--verify/--no-verify` (default: `--verify`)
- `--sync-roles/--no-sync-roles` (default: `--sync-roles`)
- `--strict-plan/--no-strict-plan` (default: `--strict-plan`)
- `--run-id <id>` (optional)

Runtime inputs:
- `.ai/config.yaml`
- `.ai/state.json`
- `.ai/plan.json` (required when strict plan is enabled)
- `.ai/roles_workflow.json` (created/loaded when role sync is enabled)
- `.ai/runs/<run_id>/dispatch.json` (initialized or reused inside the run)

## 4. Output Contract

`aiwf develop` prints JSON output including:
- `run_id`
- `ok`
- `verified` (boolean)
- `mode` (`full` or `preflight`)
- `steps` (plan/roles/verify step results)
- `artifacts` (paths relevant to the same run)

Meaning of `--no-verify`:
- This is a degraded preflight mode.
- It never means release-ready or merge-ready by itself.
- Output must explicitly include `verified: false`.

## 5. Success and Failure Conditions

Exit code contract:
- `0`: develop succeeds; if verify is enabled, verification passed.
- `1`: develop execution failed or verify failed.
- `2`: invalid input or workspace/config contract error.

Success conditions:
- Orchestration finished without runtime error.
- If verify is enabled, verify result is successful.
- If strict plan is enabled, plan contract is valid.

Failure conditions:
- Any required step fails.
- Verify fails when enabled.
- Contract input invalid (CLI argument error, missing/invalid required workspace files under strict mode).

## 6. Run and Artifact Responsibility Boundary

Single-run principle:
- One `aiwf develop` invocation -> one `run_id`.
- This `run_id` is the unified correlation key for all evidence of this invocation.

Record boundary:
- `run.json`: unified run overview record (not verify-only semantics).
- `develop.json`: develop orchestration detail record.
- `dispatch.json`: run-scoped work item / handoff / transition evidence record.

If verify is executed inside develop, it must reuse the same `run_id` to keep evidence coherent.

## 7. Exception and Interrupt Recording

For every invocation, even failed runs should leave machine-readable evidence:
- telemetry events with the same `run_id`:
  - `develop_started`
  - `develop_step`
  - `develop_finished`
- `.ai/runs/<run_id>/develop.json`:
  - input options snapshot
  - per-step result
  - error summary (if any)
  - artifact pointers
- `.ai/runs/<run_id>/dispatch.json`:
  - work items
  - handoffs
  - transitions
  - dispatch summary

## 8. Boundary: develop vs verify

- `verify` is the quality-gate executor (policy, gate execution, verification result recording).
- `develop` is the orchestrator for controlled development progression.
- Role sync is default pre-step of develop, but it is not the semantic core of develop.
- `dispatch` is a run-scoped evidence skeleton for task flow, not a second orchestrator.

## 9. M1 Implementation Constraints

To keep scope minimal:
- Reuse existing workspace, verify, role, and state logic.
- Keep current CLI file layout (no large refactor in M1).
- Prefer additive changes in orchestrator and CLI.
