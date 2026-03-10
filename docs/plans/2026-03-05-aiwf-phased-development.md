# AIWF Phased Development Implementation Plan
Status: Historical implementation plan, not current SoT.

If this plan conflicts with current behavior or priorities, follow:
- `docs/process/2026-03-09-development-requirements-entry.md`
- `docs/process/2026-03-09-develop-command-contract.md`

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a usable development loop for AIWF itself with progress visibility, policy checks, and state contract validation.

**Architecture:** Extend CLI commands while reusing existing `AIWorkspace`, `PolicyEngine`, and JSON schema contracts. Keep behavior minimal and deterministic, then verify with focused pytest coverage.

**Tech Stack:** Python 3.10+, Typer, pytest, jsonschema

---

### Task 1: Progress visibility (`aiwf status`)

**Files:**
- Modify: `src/aiwf/cli/main.py`
- Test: `tests/test_cli.py`

Steps:
1. Write failing test for `aiwf status`.
2. Implement command to print current `.ai/state.json`.
3. Run `pytest -q` and verify pass.

### Task 2: Policy check (`aiwf policy-check`)

**Files:**
- Modify: `src/aiwf/cli/main.py`
- Test: `tests/test_cli.py`

Steps:
1. Write failing tests for allowed and denied path decisions.
2. Implement command using `PolicyEngine`.
3. Return non-zero exit when denied.
4. Run `pytest -q` and verify pass.

### Task 3: State contract validation (`aiwf validate-state`)

**Files:**
- Modify: `src/aiwf/cli/main.py`
- Reuse: `src/aiwf/schema/json_validator.py`
- Test: `tests/test_cli.py`

Steps:
1. Write failing test for valid state schema.
2. Implement command to validate `.ai/state.json` against `schemas/state.schema.json`.
3. Run `pytest -q` and verify pass.
