# AIWF Governance and Stage Gates

Date: 2026-03-06

## 1. Purpose

This document defines the process contract for self-hosted AIWF development, so every phase has clear entry/exit criteria and auditable evidence.

## 2. Stage Model

Allowed stage values follow `state.schema.json`:
- `INIT`
- `SPEC`
- `PLAN`
- `DEV`
- `VERIFY`
- `SHIP`
- `DONE`
- `FAILED`

## 3. Stage Entry and Exit Criteria

### INIT
- Entry: repository initialized, `.ai/` layout created.
- Exit evidence:
  - `.ai/config.yaml` exists
  - `.ai/state.json` exists and validates

### SPEC
- Entry: requirement or change intent is identified.
- Exit evidence:
  - scope statement written
  - non-goals written
  - success criteria listed

### PLAN
- Entry: SPEC approved.
- Exit evidence:
  - implementation plan in `docs/plans/`
  - explicit files-to-touch list
  - test strategy documented

### DEV
- Entry: PLAN approved.
- Exit evidence:
  - latest remote branch state synced before coding
  - minimal implementation complete
  - targeted tests added/updated
  - no undocumented scope expansion

### VERIFY
- Entry: DEV changes ready for quality checks.
- Exit evidence:
  - `aiwf verify` executed
  - `.ai/artifacts/reports/*.json` updated
  - `.ai/runs/<run_id>/run.json` created
  - `.ai/telemetry/events.jsonl` contains run events

### SHIP
- Entry: VERIFY success and no blocking risk.
- Exit evidence:
  - development happened on non-default branch
  - PR opened to default branch
  - required checks and review passed
  - PR merged
  - release/change note prepared
  - outstanding risks documented with owner

### DONE
- Entry: SHIP accepted.
- Exit evidence:
  - merge commit or equivalent recorded in git history
  - final status snapshot written

### FAILED
- Entry: blocking quality or policy condition.
- Exit evidence:
  - root cause noted
  - rollback or recovery plan recorded

## 4. Review Checklist (Per Phase)

- Direction check: still aligned with AIWF goals?
- Contract check: schema/policy/process constraints still respected?
- Evidence check: required artifacts produced and readable?
- Risk check: top 3 risks updated with mitigation owner?

## 5. Required Artifacts

- State: `.ai/state.json`
- Gate reports: `.ai/artifacts/reports/<gate>.json`
- Run record: `.ai/runs/<run_id>/run.json`
- Telemetry: `.ai/telemetry/events.jsonl`
- Plan docs: `docs/plans/*.md`

## 6. Escalation Rules

- Policy denial: stop gate execution, mark run failure, record reason.
- Schema mismatch: treat as contract violation, block stage exit.
- Missing evidence: stage cannot be marked complete.
- Direct commit to default branch for feature work: treat as process violation.
