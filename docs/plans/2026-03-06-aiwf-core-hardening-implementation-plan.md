# AIWF Core Hardening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Harden AIWF's self-hosted development loop with stronger contract validation, clearer stage operations, and better verification ergonomics.

**Architecture:** Build on the existing CLI + WorkflowEngine design without introducing new runtime services. Add incremental commands and checks that reuse `AIWorkspace`, schema validation utilities, and existing gate/policy outputs.

**Tech Stack:** Python 3.10+, Typer, pytest, jsonschema, PyYAML

---

### Task 1: Contract validation for run and gate artifacts

**Files:**
- Modify: `src/aiwf/cli/main.py`
- Test: `tests/test_cli.py`

Steps:
1. Add failing tests for a new command: `aiwf validate-artifacts`.
2. Implement command to validate:
   - latest `.ai/runs/<run_id>/run.json` against `run_record.schema.json`
   - each `.ai/artifacts/reports/*.json` against `gate_result.schema.json`
3. Return non-zero exit code when any artifact is invalid or missing.
4. Run `pytest -q` and verify pass.

### Task 2: Stage transition command with guardrails

**Files:**
- Modify: `src/aiwf/cli/main.py`
- Reuse: `src/aiwf/storage/ai_workspace.py`
- Test: `tests/test_cli.py`

Steps:
1. Add failing tests for `aiwf stage set <stage>`.
2. Implement stage setter constrained by allowed enum values from state schema.
3. Add simple transition guardrails:
   - block `SHIP` unless last verify run succeeded
   - block `DONE` unless current stage is `SHIP`
4. Emit clear JSON result payload and proper exit code.
5. Run `pytest -q` and verify pass.

### Task 3: Verification summary command for regulator role

**Files:**
- Modify: `src/aiwf/cli/main.py`
- Test: `tests/test_cli.py`

Steps:
1. Add failing tests for `aiwf audit-summary`.
2. Implement command output including:
   - current stage
   - last run id and result
   - gate pass/fail counts
   - policy status from latest telemetry `policy_check` event if present
3. Ensure output is stable JSON for machine and human review.
4. Run `pytest -q` and verify pass.

### Task 4: Strengthen workflow engine verify behavior

**Files:**
- Modify: `src/aiwf/orchestrator/workflow_engine.py`
- Test: `tests/test_workflow_engine.py`

Steps:
1. Add failing test for no-gate configured behavior.
2. Decide and implement deterministic behavior (recommended: fail with explicit reason).
3. Add telemetry event for no-gate condition.
4. Run `pytest -q` and verify pass.

### Task 5: Documentation sync and usage examples

**Files:**
- Modify: `README.md`
- Modify: `docs/README.md`

Steps:
1. Add CLI usage examples for new commands.
2. Add short development loop section:
   - `aiwf init`
   - `aiwf status`
   - `aiwf verify`
   - `aiwf validate-state`
   - `aiwf validate-artifacts`
   - `aiwf audit-summary`
3. Run `pytest -q` after docs update to ensure no accidental breakage.
