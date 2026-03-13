# AIWF Current Project Structure

Last updated: 2026-03-13

This document explains the repository as it exists today. It separates:

1. project code
2. development-process files
3. runtime workspace data

The goal is to keep future development sessions reading the right files and to prevent code, process records, and generated artifacts from being mixed together.

---

## 1. Project Code

These paths define AIWF itself.

### `src/aiwf/`

Primary source code:

- `cli/main.py`
  CLI entrypoint and command registration.
- `orchestrator/task_engine.py`
  Task lifecycle state machine and verification orchestration.
- `storage/ai_workspace.py`
  `.ai/` workspace layout and top-level state/config access.
- `storage/task_store.py`
  Task file I/O for `spec.json`, `verify.json`, and `record.json`.
- `gate/gate_engine.py`
  Shell-command gate execution and gate report writing.
- `schema/json_validator.py`
  JSON schema loading and payload validation.
- `telemetry/sink.py`
  Append-only telemetry event output.

### `schemas/`

Persisted data contracts used by the implementation:

- `task_spec.schema.json`
- `task_verify.schema.json`
- `task_record.schema.json`
- `state.schema.json`
- `run_record.schema.json`
- `gate_result.schema.json`

### `tests/`

Executable verification for the implementation:

- `test_cli.py`
- `test_task_engine.py`
- `test_task_store.py`
- `test_contract_schemas.py`

### Infrastructure files

- `pyproject.toml`
  Packaging, dependencies, and CLI entrypoint.
- `.github/workflows/aiwf-verify.yml`
  CI test workflow.

---

## 2. Development-Process Files

These files guide humans and agents while developing the repository. They do not implement AIWF behavior.

### Root guidance

- `AGENTS.md`
  The only agent entrypoint for this repository.
- `README.md`
  User-facing repository description. It must only describe behavior that exists in code today.

### Stable current docs referenced by `AGENTS.md`

- `docs/current/project-structure.md`
  This file. Explains repository boundaries and active paths.
- `docs/current/module-task-list.md`
  User-capability-oriented module and task tree for ongoing development.
- `docs/current/current-work-state.md`
  Current focus, recommended next task, and active blockers.
- `docs/current/agent-development-loop.md`
  Mandatory development loop for future agent sessions.
- `docs/current/implementation-status.md`
  Current implementation state and known gaps.

### Stable target reference

- `docs/reference/v2-refactoring-target.md`
  Intended v2 target behavior used to judge deviations.

### Stable development record

- `docs/progress/change-log.md`
  Append-only record of completed development tasks and doc updates.

Rule:

- code lives in `src/`, `schemas/`, `tests/`, `.github/workflows/`, `pyproject.toml`
- active guidance lives in `AGENTS.md`, `README.md`, and `docs/`
- the next session should never need dated filenames to find current guidance
- the next agent session should always start at `AGENTS.md`

---

## 3. Runtime Workspace Data

### `.ai/`

This directory is AIWF runtime state and evidence, not repository design documentation.

Under the current v2 implementation, the meaningful runtime structure is:

- `.ai/config.yaml`
- `.ai/state.json`
- `.ai/tasks/<task-id>/spec.json`
- `.ai/tasks/<task-id>/verify.json`
- `.ai/tasks/<task-id>/record.json`
- `.ai/runs/<run_id>/run.json`
- `.ai/runs/<run_id>/<gate>.json`
- `.ai/telemetry/events.jsonl`

Important:

- `.ai/` can contain leftovers from earlier local runs or older iterations.
- Do not update repository docs by copying `.ai/` contents blindly.
- Runtime evidence confirms execution after the fact; it does not define the intended behavior of the repository.

---

## 4. What To Ignore During Normal Development

These paths are not the primary development surface:

- `build/`
- `UNKNOWN.egg-info/`
- `__pycache__/`

Treat them as packaging or execution leftovers unless a specific packaging/debugging task requires them.

---

## 5. Required Sync Rule

Whenever repository state changes, update every affected current doc in place:

- behavior change: update `README.md` and `docs/current/implementation-status.md`
- path / ownership / layout change: update `docs/current/project-structure.md`
- task decomposition / module map / recommended next task change: update `docs/current/module-task-list.md` and `docs/current/current-work-state.md`
- workflow / read order / mandatory record behavior change: update `AGENTS.md`, `docs/README.md`, and `docs/current/agent-development-loop.md`
- target-behavior change: update `docs/reference/v2-refactoring-target.md`

After those updates, append a factual summary entry to `docs/progress/change-log.md`.
