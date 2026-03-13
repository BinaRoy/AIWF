# AIWF Current Implementation Status

Last updated: 2026-03-13

**Target reference:** `docs/reference/v2-refactoring-target.md`  
**Assessment basis:** code in `src/`, `schemas/`, `tests/`, `.github/workflows/`, `pyproject.toml`  
**Overall completion:** ~90%  
**Latest verified full test command:** `PYTHONPATH=src python3 -m pytest tests/ -q`  
**Latest verified result:** `79 passed`

---

## Overall Assessment

The v2 refactor is largely implemented. The new task lifecycle, simplified `.ai/` workspace, new schemas, and rewritten tests are present and working. The main remaining gaps are:

1. CLI contract deviations from the target still exist.
2. CI workflow is only partially aligned with the target.
3. `pyproject.toml` is not fully aligned with the target packaging spec.
4. A few behavior details still differ from the target document.

---

## Current Phase Status

| Step | Description | Status | Current Evidence |
|------|-------------|--------|------------------|
| 1.1 | New schemas | Complete | `task_spec`, `task_record`, `task_verify`, simplified `state`, simplified `run_record` are present |
| 1.2 | `task_store.py` pure I/O layer | Complete | Implemented and covered by `tests/test_task_store.py` |
| 1.3 | `task_engine.py` state machine + gate orchestration | Complete | Implemented and covered by `tests/test_task_engine.py` |
| 1.4 | Simplified `ai_workspace.py` | Complete | Layout, config, and state follow the v2 direction |
| 1.5 | New task lifecycle CLI | Mostly complete | Commands exist and are tested, but several flags/output contracts differ from target |
| 1.6 | Delete deprecated modules | Mostly complete | Deprecated Python modules/files removed, but several empty directories remain |
| 1.7 | Update CI workflow | Partial | Workflow runs tests and uploads artifacts, but planned `aiwf init` / `aiwf verify` step is missing |

---

## What Is Implemented

### Core source modules

```text
src/aiwf/cli/main.py
src/aiwf/gate/gate_engine.py
src/aiwf/orchestrator/task_engine.py
src/aiwf/schema/json_validator.py
src/aiwf/storage/ai_workspace.py
src/aiwf/storage/task_store.py
src/aiwf/telemetry/sink.py
```

### Active schemas

```text
schemas/gate_result.schema.json
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
8. `aiwf status` returns current task summary, task counts, and last verify result.
9. Standalone `aiwf verify` runs configured gates outside task context.

---

## Current Deviations From Target

### CLI contract deviations

- `task new` title is still `--title`, not a positional argument.
- Options are `--acceptance` and repeatable `--file`, not `--accept` and `--files`.
- `task new` output omits the `spec` path.
- `aiwf init` prints a rich text message instead of the target JSON payload.
- Invalid-state exit codes generally return `1`, not the target `2`.
- `aiwf status` omits `last_verify.timestamp`.
- Standalone `aiwf verify` does not write `run.json`.

### Implementation / packaging deviations

- CI workflow does not yet run `aiwf init` and `aiwf verify`.
- `pyproject.toml` does not yet include `[tool.setuptools.packages.find]`.
- `build-system.requires` does not match the target document's `setuptools>=64` value.
- Empty deprecated directories still exist under `src/aiwf/`.

---

## Maintenance Rule

Whenever implementation state changes, update this file in place. Do not create a new dated status file for the current state. The next agent session will reach this file through the single entrypoint `AGENTS.md`.
