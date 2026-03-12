# Run-Centered Dispatch Skeleton Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a minimal run-scoped dispatch skeleton for AIWF so each `aiwf develop` run can record work items, handoffs, and transitions as auditable evidence without claiming full multi-agent orchestration.

**Architecture:** Extend the existing run artifact model with a new `dispatch.json` record under `.ai/runs/<run_id>/`. Keep `aiwf develop` as the only primary closed-loop entry point. Add a small dispatch storage/runtime layer, a focused CLI surface, and minimal consistency checks that integrate with current run/audit flows.

**Tech Stack:** Python, Typer CLI, JSON Schema, pytest

---

### Task 1: Define Dispatch Contract

**Files:**
- Create: `schemas/dispatch_record.schema.json`
- Modify: `tests/test_contract_schemas.py`
- Reference: `schemas/run_record.schema.json`
- Reference: `schemas/develop_record.schema.json`

**Step 1: Write the failing schema tests**

Add tests that:
- accept a valid dispatch payload with `run_id`, timestamps, `work_items`, `handoffs`, `transitions`, and `summary`
- reject missing `run_id`
- reject invalid `work_item.status`
- reject a transition without `from_status` / `to_status`

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_contract_schemas.py -k dispatch -v`
Expected: FAIL because `dispatch_record.schema.json` does not exist and/or dispatch tests fail.

**Step 3: Write minimal schema**

Create `schemas/dispatch_record.schema.json` with:
- top-level required fields: `run_id`, `timestamp`, `work_items`, `handoffs`, `transitions`, `summary`
- allowed `work_item.status`: `pending`, `in_progress`, `handoff`, `review`, `done`, `blocked`
- required handoff fields: `work_item_id`, `from_role`, `to_role`, `timestamp`
- required transition fields: `work_item_id`, `from_status`, `to_status`, `timestamp`
- summary counts for each status plus total counts

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_contract_schemas.py -k dispatch -v`
Expected: PASS

**Step 5: Commit**

```bash
git add schemas/dispatch_record.schema.json tests/test_contract_schemas.py
git commit -m "test: add dispatch record schema contract"
```

### Task 2: Add Dispatch Storage and Runtime Rules

**Files:**
- Create: `src/aiwf/storage/dispatch_artifacts.py`
- Modify: `tests/test_workflow_engine.py`
- Modify: `tests/test_cli.py`
- Reference: `src/aiwf/storage/run_artifacts.py`

**Step 1: Write the failing storage/runtime tests**

Add tests that:
- initialize an empty dispatch record for a run
- append a work item and persist it
- record a handoff for an existing work item
- enforce valid transitions, including:
  - `pending -> in_progress` allowed
  - direct `pending -> done` rejected
- compute summary counts from stored items

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_workflow_engine.py -k dispatch -v`
Expected: FAIL because dispatch storage/runtime helpers do not exist.

**Step 3: Write minimal implementation**

Implement `src/aiwf/storage/dispatch_artifacts.py` with functions to:
- create/load/save `dispatch.json`
- validate payload against `dispatch_record.schema.json`
- add work item
- add handoff
- add transition with minimal status guard
- build summary counts

Keep implementation additive and run-scoped only.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_workflow_engine.py -k dispatch -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/aiwf/storage/dispatch_artifacts.py tests/test_workflow_engine.py tests/test_cli.py
git commit -m "feat: add run-scoped dispatch storage"
```

### Task 3: Expose Dispatch CLI Commands

**Files:**
- Modify: `src/aiwf/cli/main.py`
- Modify: `tests/test_cli.py`
- Reference: `src/aiwf/storage/dispatch_artifacts.py`

**Step 1: Write the failing CLI tests**

Add CLI tests for:
- `aiwf dispatch init --run-id <id>`
- `aiwf dispatch add-item --run-id <id> --id ... --title ... --owner-role ...`
- `aiwf dispatch handoff --run-id <id> --work-item-id ... --from-role ... --to-role ...`
- `aiwf dispatch transition --run-id <id> --work-item-id ... --to-status ...`
- `aiwf dispatch status --run-id <id>`

Assert output JSON and file side effects in `.ai/runs/<run_id>/dispatch.json`.

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli.py -k dispatch -v`
Expected: FAIL because `dispatch` CLI subcommands do not exist.

**Step 3: Write minimal implementation**

Add a `dispatch` typer app with commands that call the storage/runtime helpers.
Use JSON output consistent with the rest of the CLI.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli.py -k dispatch -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/aiwf/cli/main.py tests/test_cli.py
git commit -m "feat: add dispatch CLI commands"
```

### Task 4: Integrate Dispatch with Develop Runs

**Files:**
- Modify: `src/aiwf/orchestrator/workflow_engine.py`
- Modify: `tests/test_workflow_engine.py`
- Reference: `src/aiwf/storage/dispatch_artifacts.py`
- Reference: `docs/process/2026-03-09-develop-command-contract.md`

**Step 1: Write the failing integration tests**

Add tests that verify:
- `develop()` initializes `dispatch.json` for the run
- `run.json` / `develop.json` artifact references include `dispatch.json`
- preflight and verified runs both keep a dispatch record
- verified run fails or reports failure when dispatch record contains unresolved blocked items

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_workflow_engine.py -k \"develop and dispatch\" -v`
Expected: FAIL because develop does not manage dispatch artifacts.

**Step 3: Write minimal implementation**

Update `WorkflowEngine.develop()` to:
- initialize a dispatch record at run start
- include dispatch artifact reference in run/develop records
- evaluate a minimal dispatch consistency check before final success
- preserve dispatch evidence on failure paths

Do not add a second primary run entry point.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_workflow_engine.py -k \"develop and dispatch\" -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/aiwf/orchestrator/workflow_engine.py tests/test_workflow_engine.py
git commit -m "feat: link dispatch record to develop runs"
```

### Task 5: Add Audit and Artifact Validation Coverage

**Files:**
- Modify: `src/aiwf/storage/run_artifacts.py`
- Modify: `src/aiwf/runtime/state_view.py`
- Modify: `src/aiwf/cli/main.py`
- Modify: `tests/test_cli.py`
- Modify: `tests/test_runtime_checks.py`

**Step 1: Write the failing verification tests**

Add tests that:
- `validate-artifacts` validates `dispatch.json` when present for the run
- `audit-summary` includes dispatch summary counts or presence flags
- latest run summary remains stable when no dispatch record exists for older runs

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli.py -k \"dispatch and (validate_artifacts or audit_summary)\" -v`
Expected: FAIL because dispatch artifacts are not validated or summarized.

**Step 3: Write minimal implementation**

Update:
- run artifact validation to include `dispatch.json` when referenced
- audit summary builder to surface dispatch presence and summary counts
- CLI JSON output only as needed to expose the new fields

Keep changes backward-compatible for runs without dispatch artifacts.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli.py -k \"dispatch and (validate_artifacts or audit_summary)\" -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/aiwf/storage/run_artifacts.py src/aiwf/runtime/state_view.py src/aiwf/cli/main.py tests/test_cli.py tests/test_runtime_checks.py
git commit -m "feat: include dispatch evidence in audit and validation"
```

### Task 6: Update Product Boundary and Usage Docs

**Files:**
- Modify: `README.md`
- Modify: `docs/architecture/2026-03-10-m1-product-boundary-and-entrypoint.md`
- Modify: `docs/guide/2026-03-06-aiwf-framework-intro-and-usage-zh.md`
- Modify: `docs/process/2026-03-09-develop-command-contract.md`

**Step 1: Write doc assertions as checklist**

Document the exact framing to preserve:
- still not a full multi-agent orchestration engine
- now includes run-scoped dispatch skeleton
- `develop` remains the only primary closed-loop entry point

**Step 2: Update docs**

Add concise documentation for:
- what `dispatch.json` is
- how dispatch CLI commands relate to `develop`
- current non-goals and follow-on scope

**Step 3: Verify docs match implementation**

Run:
`pytest tests/test_cli.py -k dispatch -v`
`pytest tests/test_workflow_engine.py -k dispatch -v`

Expected: PASS, and docs make no stronger claim than implementation supports.

**Step 4: Commit**

```bash
git add README.md docs/architecture/2026-03-10-m1-product-boundary-and-entrypoint.md docs/guide/2026-03-06-aiwf-framework-intro-and-usage-zh.md docs/process/2026-03-09-develop-command-contract.md
git commit -m "docs: describe run-scoped dispatch skeleton"
```

### Task 7: Final Verification

**Files:**
- No code changes expected

**Step 1: Run focused test suites**

Run:
- `pytest tests/test_contract_schemas.py -k dispatch -v`
- `pytest tests/test_workflow_engine.py -k dispatch -v`
- `pytest tests/test_cli.py -k dispatch -v`

Expected: PASS

**Step 2: Run broader regression coverage**

Run:
- `pytest tests/test_contract_schemas.py tests/test_workflow_engine.py tests/test_cli.py tests/test_runtime_checks.py -q`

Expected: PASS

**Step 3: Manual smoke check**

Run:
- `aiwf init --self-hosted`
- `aiwf dispatch init --run-id run_manual`
- `aiwf dispatch add-item --run-id run_manual --id item1 --title "demo" --owner-role manager`
- `aiwf dispatch status --run-id run_manual`

Expected:
- `dispatch.json` created under `.ai/runs/run_manual/`
- JSON output includes one work item and summary counts

**Step 4: Record completion**

Only after all commands pass, summarize:
- added schema
- added storage/runtime/CLI
- linked dispatch evidence into develop and audit flows

