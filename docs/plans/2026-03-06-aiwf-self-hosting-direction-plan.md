# AIWF Self-Hosting Direction Plan
Status: Historical implementation plan, not current SoT.

If this plan conflicts with current behavior or priorities, follow:
- `docs/process/2026-03-09-development-requirements-entry.md`
- `docs/process/2026-03-09-develop-command-contract.md`

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make AIWF capable of governing its own development process with executable checks, measurable progress, and CI-backed enforcement.

**Architecture:** Prioritize executable process gates (A), then plan/progress contracts (B), then CI enforcement (C). Reuse existing CLI, workflow engine, policy engine, and schema validator.

**Tech Stack:** Python 3.10+, Typer, pytest, jsonschema, GitHub Actions

---

### Task 1: Add self-hosting readiness check command (`aiwf self-check`)

**Files:**
- Modify: `src/aiwf/cli/main.py`
- Test: `tests/test_cli.py`

Steps:
1. Add failing tests for `aiwf self-check` covering pass/fail.
2. Implement command to aggregate:
   - PR workflow readiness
   - state schema validity
   - latest run/artifact validity
   - latest run success status
3. Return stable JSON report and non-zero exit when any required check fails.
4. Run `pytest -q` and verify pass.

### Task 2: Gate preset for self-hosting projects

**Files:**
- Modify: `src/aiwf/cli/main.py`
- Reuse: `src/aiwf/storage/ai_workspace.py`
- Test: `tests/test_cli.py`

Steps:
1. Add failing tests for `aiwf init --self-hosted` (or equivalent command).
2. Write default gates/policy suitable for self-hosting:
   - unit tests
   - self-check
3. Verify config write is deterministic.
4. Run `pytest -q` and verify pass.

### Task 3: Plan contract enforcement loop

**Files:**
- Modify: `src/aiwf/cli/main.py`
- Reuse: `schemas/plan.schema.json`
- Test: `tests/test_cli.py`

Steps:
1. Add failing tests for `aiwf plan validate` and `aiwf plan progress`.
2. Implement schema validation and progress summary output.
3. Store progress summary in `.ai/state.json`.
4. Run `pytest -q` and verify pass.

### Task 4: CI workflow for PR enforcement

**Files:**
- Create: `.github/workflows/aiwf-verify.yml`
- Modify: `README.md`

Steps:
1. Add workflow to run pytest and core AIWF checks on PR.
2. Upload artifacts (`.ai/runs`, gate reports) when available.
3. Document CI behavior in README.
4. Run local checks and verify YAML validity.

### Task 5: Risk and exception registry

**Files:**
- Create: `schemas/risk_register.schema.json`
- Modify: `src/aiwf/cli/main.py`
- Test: `tests/test_cli.py`

Steps:
1. Add failing tests for `aiwf risk status` and `aiwf risk waive`.
2. Implement registry with expiry-aware waivers.
3. Include risk snapshot in `audit-summary`.
4. Run `pytest -q` and verify pass.
