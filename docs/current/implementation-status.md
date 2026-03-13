# AIWF Current Implementation Status

Last updated: 2026-03-13

**Target reference:** `docs/reference/v2-refactoring-target.md`  
**Assessment basis:** code in `src/`, `schemas/`, `tests/`, `.github/workflows/`, `pyproject.toml`  
**Overall completion:** ~97%  
**Latest verified full test command:** `PYTHONPATH=src python3 -m pytest tests/ -q`  
**Latest verified result:** `86 passed`

---

## Overall Assessment

The v2 refactor is largely implemented. The new task lifecycle, simplified `.ai/` workspace, new schemas, and rewritten tests are present and working. The main remaining gaps are:

1. CLI contract deviations from the target still exist.
2. Only broader future-expansion tasks remain in the tracked backlog.

---

## Current Phase Status

| Step | Description | Status | Current Evidence |
|------|-------------|--------|------------------|
| 1.1 | New schemas | Complete | `task_spec`, `task_record`, `task_verify`, simplified `state`, simplified `run_record`, and `project_map` are present |
| 1.2 | `task_store.py` pure I/O layer | Complete | Implemented and covered by `tests/test_task_store.py` |
| 1.3 | `task_engine.py` state machine + gate orchestration | Complete | Implemented and covered by `tests/test_task_engine.py` |
| 1.4 | Simplified `ai_workspace.py` | Complete | Layout, config, and state follow the v2 direction |
| 1.5 | New task lifecycle CLI | Complete | Commands exist and are tested; `task new` syntax, `init` output, invalid-state exit codes, and status verify summary fields are aligned |
| 1.6 | Delete deprecated modules | Complete | Deprecated Python modules/files and leftover empty package directories removed |
| 1.7 | Update CI workflow | Complete | Workflow installs the package, runs `aiwf init`, runs `aiwf verify`, runs tests, and uploads artifacts |

---

## What Is Implemented

### Core source modules

```text
src/aiwf/cli/main.py
src/aiwf/gate/gate_engine.py
src/aiwf/orchestrator/task_engine.py
src/aiwf/schema/json_validator.py
src/aiwf/storage/ai_workspace.py
src/aiwf/storage/project_map_store.py
src/aiwf/storage/task_store.py
src/aiwf/telemetry/sink.py
```

### Active schemas

```text
schemas/gate_result.schema.json
schemas/project_map.schema.json
schemas/run_record.schema.json
schemas/state.schema.json
schemas/task_record.schema.json
schemas/task_spec.schema.json
schemas/task_verify.schema.json
```

### Active tests

```text
tests/test_cli.py
tests/test_contract_schemas.py
tests/test_task_engine.py
tests/test_task_store.py
```

---

## Verified Working Behavior

The following behavior is implemented and covered by tests:

1. `aiwf init` creates `.ai/`, `.ai/state.json`, and `.ai/config.yaml`.
2. `aiwf task new` creates `.ai/tasks/task-xxx/spec.json`.
3. `aiwf task start` enforces a single active `in_progress` task.
4. `aiwf task current` returns the current in-progress task.
5. `aiwf task verify` runs configured gates, writes gate artifacts, writes `verify.json`, and updates task state.
6. `aiwf task close` requires successful verification and writes `record.json`.
7. `aiwf task block`, `unblock`, and `retry` work with state-transition checks.
8. `aiwf status` returns current task summary, task counts, and last verify summary including timestamp.
9. Standalone `aiwf verify` runs configured gates outside task context.
10. Packaging metadata uses `src/` package discovery and CI exercises installed `aiwf` smoke commands.
11. `aiwf map init/add/link/show` persists and displays module-level task completion under `.ai/project_map.json`.

---

## Current Deviations From Target

## Remaining Tracked Work

The remaining tracked work in `docs/current/module-task-list.md` is future-facing:

- `TASK-FUTURE-001`
- `TASK-FUTURE-002`
- `TASK-FUTURE-003`

---

## Maintenance Rule

Whenever implementation state changes, update this file in place. Do not create a new dated status file for the current state. The next agent session will reach this file through the single entrypoint `AGENTS.md`.

Companion planning surfaces:

- `docs/current/module-task-list.md`
- `docs/current/current-work-state.md`
