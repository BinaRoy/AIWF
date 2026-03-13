# AIWF Module And Task List

Last updated: 2026-03-13

This is the master module and task list for ongoing AIWF development.

It is organized by user capability first, with code-path mappings second. Agents should use this file to understand:

- which large capability area a task belongs to
- which tasks are already done
- which tasks are blocked or future-facing
- which task can be selected next when the user has not specified one

Status values align with the current AIWF task lifecycle:

- `defined`
- `in_progress`
- `verifying`
- `done`
- `failed`
- `blocked`

Priority values:

- `P0` highest
- `P1` high
- `P2` medium
- `P3` future

---

## M1. Initialize And Configure AIWF

**Goal:** A developer can initialize `.ai/`, provide gate commands, and get a valid workspace without project intrusion.  
**Status summary:** Core behavior implemented; output and packaging details still need alignment.

### Tasks

- `TASK-INIT-001`
  Title: Create `.ai/` workspace with minimal config and state files
  Status: `done`
  Priority: `P0`
  Depends on: none
  Maps to: `storage/ai_workspace.py`, `cli/main.py`, `tests/test_cli.py`
  Done when: `aiwf init` creates `.ai/`, `.ai/config.yaml`, and `.ai/state.json`

- `TASK-INIT-002`
  Title: Align `aiwf init` output with target JSON contract
  Status: `done`
  Priority: `P1`
  Depends on: `TASK-INIT-001`
  Maps to: `cli/main.py`, `tests/test_cli.py`, `README.md`, `docs/current/implementation-status.md`
  Done when: `aiwf init` returns machine-readable JSON matching the current target doc

- `TASK-INIT-003`
  Title: Align packaging metadata with v2 target install expectations
  Status: `defined`
  Priority: `P2`
  Depends on: `TASK-INIT-001`
  Maps to: `pyproject.toml`, `.github/workflows/aiwf-verify.yml`, `docs/current/implementation-status.md`
  Done when: package discovery and documented install behavior match the current target direction

---

## M2. Define And Drive Tasks

**Goal:** A developer or agent can create, start, inspect, block, retry, and close scoped tasks through a controlled task lifecycle.  
**Status summary:** Core lifecycle exists; CLI contract still needs alignment.

### Tasks

- `TASK-LIFE-001`
  Title: Persist task specs and task state transitions
  Status: `done`
  Priority: `P0`
  Depends on: `TASK-INIT-001`
  Maps to: `storage/task_store.py`, `orchestrator/task_engine.py`, `schemas/task_*.json`, `tests/test_task_store.py`, `tests/test_task_engine.py`
  Done when: task lifecycle records are created and validated under `.ai/tasks/`

- `TASK-LIFE-002`
  Title: Expose task lifecycle commands in CLI
  Status: `done`
  Priority: `P0`
  Depends on: `TASK-LIFE-001`
  Maps to: `cli/main.py`, `tests/test_cli.py`
  Done when: `task new/start/current/list/verify/close/block/unblock/retry` all exist and pass current tests

- `TASK-LIFE-003`
  Title: Align `task new` CLI contract with target syntax
  Status: `done`
  Priority: `P0`
  Depends on: `TASK-LIFE-002`
  Maps to: `cli/main.py`, `tests/test_cli.py`, `README.md`, `docs/reference/v2-refactoring-target.md`, `docs/current/implementation-status.md`
  Done when: title/accept/files syntax and output shape match the target doc

- `TASK-LIFE-004`
  Title: Align invalid-state exit codes with documented contract
  Status: `defined`
  Priority: `P1`
  Depends on: `TASK-LIFE-002`
  Maps to: `cli/main.py`, `tests/test_cli.py`, `docs/current/implementation-status.md`
  Done when: invalid input/state paths return the documented exit code semantics consistently

---

## M3. Verify And Record Evidence

**Goal:** The framework runs real gates, records evidence, and ties verification back to task progress.  
**Status summary:** Task-bound verification works; standalone verification evidence is incomplete.

### Tasks

- `TASK-VERIFY-001`
  Title: Run configured gates and persist gate reports
  Status: `done`
  Priority: `P0`
  Depends on: `TASK-INIT-001`
  Maps to: `gate/gate_engine.py`, `orchestrator/task_engine.py`, `schemas/gate_result.schema.json`, `schemas/run_record.schema.json`, `tests/test_task_engine.py`
  Done when: task verification writes gate artifacts and task verify metadata

- `TASK-VERIFY-002`
  Title: Persist task completion records after successful verification
  Status: `done`
  Priority: `P0`
  Depends on: `TASK-VERIFY-001`
  Maps to: `storage/task_store.py`, `orchestrator/task_engine.py`, `tests/test_task_store.py`, `tests/test_task_engine.py`
  Done when: close writes `record.json` with validated completion data

- `TASK-VERIFY-003`
  Title: Make standalone `aiwf verify` write `run.json`
  Status: `done`
  Priority: `P0`
  Depends on: `TASK-VERIFY-001`
  Maps to: `cli/main.py`, `gate/gate_engine.py`, `tests/test_cli.py`, `docs/current/implementation-status.md`
  Done when: standalone verification leaves a run summary consistent with task-bound verification evidence

- `TASK-VERIFY-004`
  Title: Expose `last_verify.timestamp` in status output
  Status: `defined`
  Priority: `P1`
  Depends on: `TASK-VERIFY-001`
  Maps to: `orchestrator/task_engine.py`, `cli/main.py`, `tests/test_task_engine.py`, `tests/test_cli.py`
  Done when: status output includes the latest verification timestamp

---

## M4. Inspect Current State

**Goal:** A developer can tell what task is active, what recently passed verification, and what remains to be built.  
**Status summary:** Task counts and current task summary exist; project-wide module visibility is still missing.

### Tasks

- `TASK-STATE-001`
  Title: Report current task summary and task counts
  Status: `done`
  Priority: `P1`
  Depends on: `TASK-LIFE-001`
  Maps to: `orchestrator/task_engine.py`, `cli/main.py`, `tests/test_task_engine.py`, `tests/test_cli.py`
  Done when: `aiwf status` returns current task summary and task counts

- `TASK-STATE-002`
  Title: Introduce module/task planning surface for repository development
  Status: `done`
  Priority: `P1`
  Depends on: `TASK-STATE-001`
  Maps to: `docs/current/module-task-list.md`, `docs/current/current-work-state.md`, `docs/current/agent-development-loop.md`
  Done when: agents can identify capability module, next task, and current blockers from stable docs

- `TASK-STATE-003`
  Title: Add project map / feature map capability to product
  Status: `defined`
  Priority: `P3`
  Depends on: `TASK-STATE-001`
  Maps to: future `docs/reference/v2-refactoring-target.md`, future code under `src/aiwf/`
  Done when: AIWF can persist and display project/module completion beyond flat task counts

---

## M5. Keep Agent Workflow Deterministic

**Goal:** Repository development stays followable by agents without relying on ad-hoc memory or stale docs.  
**Status summary:** Single entrypoint and stable docs exist; workflow must keep being synchronized with future behavior changes.

### Tasks

- `TASK-DOCS-001`
  Title: Enforce a single agent entrypoint and stable current-doc paths
  Status: `done`
  Priority: `P1`
  Depends on: none
  Maps to: `AGENTS.md`, `docs/README.md`, `docs/current/*.md`, `docs/progress/change-log.md`
  Done when: all agent sessions start at `AGENTS.md` and read stable current docs

- `TASK-DOCS-002`
  Title: Maintain an append-only repository change log
  Status: `done`
  Priority: `P1`
  Depends on: `TASK-DOCS-001`
  Maps to: `docs/progress/change-log.md`, `docs/current/agent-development-loop.md`
  Done when: each completed development task appends one factual record

- `TASK-DOCS-003`
  Title: Keep current docs synchronized with code and target state
  Status: `in_progress`
  Priority: `P1`
  Depends on: `TASK-DOCS-001`
  Maps to: `README.md`, `docs/current/*.md`, `docs/reference/v2-refactoring-target.md`, `docs/progress/change-log.md`
  Done when: no current doc drifts from implemented behavior or current roadmap

---

## M6. Extend Beyond Current v2 Core

**Goal:** Capture future-facing AIWF capability areas without confusing them with current v2 scope.  
**Status summary:** Future modules are explicitly tracked but not active for immediate implementation.

### Tasks

- `TASK-FUTURE-001`
  Title: Add project cognition / onboarding support
  Status: `defined`
  Priority: `P3`
  Depends on: `TASK-STATE-003`
  Maps to: future `project.json` and onboarding commands
  Done when: AIWF can capture or read project-level context beyond task state

- `TASK-FUTURE-002`
  Title: Add git-aware closure support
  Status: `defined`
  Priority: `P3`
  Depends on: `TASK-VERIFY-002`
  Maps to: future CLI and repository docs
  Done when: AIWF can associate verified work with git closure in a documented, minimal way

- `TASK-FUTURE-003`
  Title: Add trusted verification layering beyond basic gate execution
  Status: `defined`
  Priority: `P3`
  Depends on: `TASK-VERIFY-003`
  Maps to: future verification/reporting design
  Done when: AIWF can distinguish raw gate success from stronger verification trust signals

---

## Selection Rule

If the user does not specify a task, select the next task using this order:

1. not `done`
2. not `blocked`
3. dependencies satisfied
4. lowest priority number first (`P0` before `P1`, etc.)
5. within the same priority, pick the earliest task in this document

The currently recommended next task is maintained separately in `docs/current/current-work-state.md`.
