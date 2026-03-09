# AIWF Development Playbook

Date: 2026-03-06

## 1. Purpose

This playbook is the execution guide for daily development. Follow it in order to keep AIWF changes traceable and policy-compliant.

Priority note:
- Active development requirements and ordering are defined in `2026-03-09-development-requirements-entry.md`.
- `aiwf develop` behavior contract is defined in `2026-03-09-develop-command-contract.md`.

## 2. Single Task Workflow

1. Sync latest repository state before any code changes:
   - `git fetch origin`
   - `git checkout <feature-branch>` (must not be `main` or `dev`)
   - `git rebase origin/dev` (or merge equivalent)
   - `aiwf pr-check` (must pass)
2. Confirm current state:
   - `aiwf status`
3. Set task intent in your own notes (one sentence):
   - what is being changed
   - what is intentionally not changed
4. Implement minimal code changes.
5. Run targeted tests first:
   - `pytest -q tests/test_cli.py` or specific test file
6. Run controlled develop unit:
   - `aiwf develop`
   - If preflight only is needed: `aiwf develop --no-verify` (not release-ready)
7. Generate regulator summary:
   - `aiwf audit-summary`
8. Review evidence files:
   - `.ai/artifacts/reports/*.json`
   - `.ai/runs/<run_id>/run.json`
   - `.ai/telemetry/events.jsonl`
   - `.ai/roles_workflow.json`
9. Create/update PR and request review:
   - push feature branch
   - open PR to `dev`
   - attach verify/test evidence
10. Merge PR only after checks and review pass.

## 3. Stage-by-Stage Execution Checklist

### SPEC checklist
- Problem statement is explicit.
- Success criteria are testable.
- Non-goals are listed.

### PLAN checklist
- Plan exists under `docs/plans/`.
- Files-to-touch are explicit.
- Test commands are explicit.

### DEV checklist
- Changes are minimal and scoped.
- New behavior has tests or updated tests.
- No policy-denied files were modified.

### VERIFY checklist
- `aiwf develop` with verify enabled returns success.
- Gate reports exist and are readable.
- Run record includes expected stage/result.
- Telemetry has both `run_started` and `run_finished`.

### SHIP checklist
- Risks and follow-ups are written.
- Change summary is ready.
- PR is opened from feature branch to default branch.
- CI and required checks pass.
- PR is approved and merged.

## 4. Failure Handling

If any check fails:
1. Do not advance stage.
2. Set current stage to `FAILED` in process notes.
3. Capture the failure reason from gate report or telemetry.
4. Apply minimal fix.
5. Re-run verify and validation.

## 5. Regulator Review Format

Use this template at each checkpoint:

```text
Direction status: aligned / deviated
Feature status: done / in-progress / blocked
Process compliance: pass / partial / fail
Primary risks: <top 1-3>
Next action: <single highest priority>
```

## 6. Cross-Window Coordination

When using multiple CLI sessions, use one shared handoff file:
- Recommended file: `.ai/handoff.md`
- Minimal fields per update:
  - timestamp
  - stage
  - changed files
  - verification result
  - blockers

Without this handoff, regulator review cannot be considered complete.
