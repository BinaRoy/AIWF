# AIWF CLI Runtime Helper Consolidation

Date: 2026-03-10

## Scope

This note records incremental CLI pressure relief work after M1 runtime core contract convergence.
It does not change command surface or top-level runtime semantics.

## What Changed

The following helper modules now carry stable runtime read logic that previously lived in `src/aiwf/cli/main.py`:

- `src/aiwf/storage/run_artifacts.py`
  - resolve `run_id` from explicit input or `state.last_run_id`
  - load and validate `run.json`
  - resolve and validate run-scoped gate reports

- `src/aiwf/runtime/checks.py`
  - build `self-check` result payload
  - build `loop-check` result payload
  - evaluate fixed loop policy and required gate status
  - default fixed-loop `required_stage` to `DEV` when not explicitly configured

- `src/aiwf/runtime/state_view.py`
  - build `audit-summary` runtime view
  - evaluate guarded stage transitions for `SHIP` and `DONE`
  - expose allowed stage list from schema
  - bind `audit-summary` policy evidence to `state.last_run_id`
  - allow `SHIP` after a successful verified `develop` run, not only standalone `verify`

- `src/aiwf/runtime/plan_view.py`
  - load and validate `.ai/plan.json`
  - compute persisted `plan_progress` summary

- `src/aiwf/runtime/roles_view.py`
  - load and validate `.ai/roles_workflow.json`
  - compute role counts and active role
  - evaluate role contract issues
  - apply role entry updates without embedding CLI concerns

- `src/aiwf/runtime/roles_runtime.py`
  - apply role progression from plan/self/loop checks
  - perform develop-time role sync side effects
  - run `roles autopilot` orchestration without embedding workflow read logic in CLI

- `src/aiwf/runtime/risk_view.py`
  - load and validate `.ai/risk_register.json`
  - create default registry on demand
  - compute waiver/open-risk counts
  - build audit risk snapshot
  - apply waiver updates without embedding CLI concerns

## Why

`main.py` had accumulated contract-sensitive runtime read logic in multiple command handlers.
This increased drift risk because the same read/validation rules had to be kept aligned across:

- `validate-artifacts`
- `self-check`
- `loop-check`
- `audit-summary`
- `stage set`
- `plan validate`
- `plan progress`
- `risk status`
- `risk waive`

The helpers introduced here keep those rules small, local, and reusable without introducing a larger service layer.

## Non-Goals

- No new commands
- No roles/risk/autopilot expansion
- No change to `develop` / `verify` runtime contract
- No container/service abstraction

## Follow-up Convergence

The latest adjustments close two remaining semantic gaps from the runtime-core convergence work:

- `develop` is now accepted as the primary release-closing run, as long as it completed successfully with `verified=true`
- fixed-loop defaults no longer fall back to legacy `VERIFY` semantics
- `audit-summary` no longer mixes latest run status with an unrelated policy event from a different run
