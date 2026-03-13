# AIWF Change Log

This is the append-only session record for completed development tasks on this repository.

Every completed task must append one factual entry here after code/docs updates and verification.

## 2026-03-13 00:00 - Establish stable current-doc paths and mandatory record loop

- Summary: Replaced dated current-state document paths with stable `docs/current/*` and `docs/reference/*` paths; updated repository guidance so future sessions always read the same entrypoints and append a completion record.
- Files changed: `AGENTS.md`, `README.md`, `docs/README.md`, `docs/current/project-structure.md`, `docs/current/agent-development-loop.md`, `docs/current/implementation-status.md`, `docs/reference/v2-refactoring-target.md`, `docs/progress/change-log.md`
- Verification: `find docs -maxdepth 3 -type f | sort` and manual review of updated current docs
- Result: pass
- Current docs updated: `README.md`, `docs/README.md`, `docs/current/project-structure.md`, `docs/current/agent-development-loop.md`, `docs/current/implementation-status.md`, `docs/reference/v2-refactoring-target.md`, `AGENTS.md`
- Follow-ups: Update any remaining references in future tasks if code or workflow semantics change again.

## 2026-03-13 00:30 - Remove residual directories and enforce single agent entrypoint

- Summary: Removed empty and legacy directories, deleted old v1-only `.ai` leftovers and build caches, and tightened documentation so `AGENTS.md` is the only agent entrypoint.
- Files changed: `AGENTS.md`, `README.md`, `docs/README.md`, `docs/current/project-structure.md`, `docs/current/agent-development-loop.md`, `docs/current/implementation-status.md`, `docs/progress/change-log.md`
- Verification: `find docs -maxdepth 3 -type f | sort`, `find . -maxdepth 3 -type d | sort`, `rg -n "2026-03-13-current-project-structure|2026-03-13-agent-development-loop|2026-03-13-v2-implementation-status|2026-03-12-aiwf-v2-refactoring-plan" README.md AGENTS.md docs .github src tests pyproject.toml`
- Result: pass
- Current docs updated: `AGENTS.md`, `README.md`, `docs/README.md`, `docs/current/project-structure.md`, `docs/current/agent-development-loop.md`, `docs/current/implementation-status.md`, `docs/progress/change-log.md`
- Follow-ups: Remove any future duplicate guidance immediately if new workflow docs are introduced.

## 2026-03-13 00:40 - Update .gitignore for current runtime and build leftovers

- Summary: Replaced old v1-specific `.ai` ignore entries with a single ignore rule for the entire runtime workspace and added `build/` to the ignored build leftovers.
- Files changed: `.gitignore`, `docs/progress/change-log.md`
- Verification: `sed -n '1,240p' .gitignore`
- Result: pass
- Current docs updated: `docs/progress/change-log.md`
- Follow-ups: Revisit `.gitignore` only if the repository later decides to version selected `.ai/` fixtures or examples.

## 2026-03-13 01:00 - Add module/task list and current work state docs

- Summary: Added a user-capability-oriented module/task master list and a current work state companion so future agent sessions can follow a stable project checklist and know the default next task.
- Files changed: `AGENTS.md`, `README.md`, `docs/README.md`, `docs/current/project-structure.md`, `docs/current/agent-development-loop.md`, `docs/current/module-task-list.md`, `docs/current/current-work-state.md`, `docs/current/implementation-status.md`, `tests/test_docs_workflow.py`, `docs/progress/change-log.md`
- Verification: `PYTHONPATH=src python3 -m pytest tests/test_docs_workflow.py -q` and `PYTHONPATH=src python3 -m pytest tests/ -q`
- Result: pass
- Current docs updated: `AGENTS.md`, `README.md`, `docs/README.md`, `docs/current/project-structure.md`, `docs/current/agent-development-loop.md`, `docs/current/module-task-list.md`, `docs/current/current-work-state.md`, `docs/current/implementation-status.md`, `docs/progress/change-log.md`
- Follow-ups: Keep `docs/current/current-work-state.md` synchronized whenever the recommended next task changes.

## 2026-03-13 01:10 - Align task new CLI syntax with target contract

- Summary: Changed `aiwf task new` to use a positional title argument, `--accept`, comma-separated `--files`, and a JSON response that includes the created spec path.
- Files changed: `src/aiwf/cli/main.py`, `tests/test_cli.py`, `README.md`, `docs/current/module-task-list.md`, `docs/current/current-work-state.md`, `docs/current/implementation-status.md`, `docs/progress/change-log.md`
- Verification: `PYTHONPATH=src python3 -m pytest tests/test_cli.py -q` and `PYTHONPATH=src python3 -m pytest tests/ -q`
- Result: pass
- Current docs updated: `README.md`, `docs/current/module-task-list.md`, `docs/current/current-work-state.md`, `docs/current/implementation-status.md`, `docs/progress/change-log.md`
- Follow-ups: Recommended next task is now `TASK-VERIFY-003`.

## 2026-03-13 01:20 - Write run.json for standalone verify

- Summary: Updated standalone `aiwf verify` so it writes `.ai/runs/<run_id>/run.json` using the existing run record contract with `task_id: null`.
- Files changed: `src/aiwf/cli/main.py`, `tests/test_cli.py`, `docs/current/module-task-list.md`, `docs/current/current-work-state.md`, `docs/current/implementation-status.md`, `docs/progress/change-log.md`
- Verification: `PYTHONPATH=src python3 -m pytest tests/test_cli.py::test_verify_standalone_runs_gates -q`, `PYTHONPATH=src python3 -m pytest tests/test_cli.py -q`, and `PYTHONPATH=src python3 -m pytest tests/ -q`
- Result: pass
- Current docs updated: `docs/current/module-task-list.md`, `docs/current/current-work-state.md`, `docs/current/implementation-status.md`, `docs/progress/change-log.md`
- Follow-ups: Recommended next task is now `TASK-INIT-002`.

## 2026-03-13 01:35 - Align init output with target JSON contract

- Summary: Changed `aiwf init` to return a machine-readable JSON payload with the stable `.ai` workspace, config, and state paths.
- Files changed: `src/aiwf/cli/main.py`, `tests/test_cli.py`, `README.md`, `docs/reference/v2-refactoring-target.md`, `docs/current/module-task-list.md`, `docs/current/current-work-state.md`, `docs/current/implementation-status.md`, `docs/progress/change-log.md`
- Verification: `PYTHONPATH=src python3 -m pytest tests/test_cli.py::test_init_creates_ai_directory -q` and `PYTHONPATH=src python3 -m pytest tests/test_cli.py -q`
- Result: pass
- Current docs updated: `README.md`, `docs/reference/v2-refactoring-target.md`, `docs/current/module-task-list.md`, `docs/current/current-work-state.md`, `docs/current/implementation-status.md`, `docs/progress/change-log.md`
- Follow-ups: Recommended next task is now `TASK-LIFE-004`.

## 2026-03-13 02:05 - Align invalid-state exit codes with documented contract

- Summary: Updated CLI contract errors so invalid input and invalid task or workspace state return exit code `2`, while execution failures such as gate failures still return `1`.
- Files changed: `src/aiwf/cli/main.py`, `tests/test_cli.py`, `docs/reference/v2-refactoring-target.md`, `docs/current/module-task-list.md`, `docs/current/current-work-state.md`, `docs/current/implementation-status.md`, `docs/progress/change-log.md`
- Verification: `PYTHONPATH=src python3 -m pytest tests/test_cli.py::test_task_start_fails_when_none_defined tests/test_cli.py::test_task_current_fails_when_none_active tests/test_cli.py::test_task_close_rejects_without_verify tests/test_cli.py::test_verify_standalone_fails_no_gates -q` and `PYTHONPATH=src python3 -m pytest tests/test_cli.py -q`
- Result: pass
- Current docs updated: `docs/reference/v2-refactoring-target.md`, `docs/current/module-task-list.md`, `docs/current/current-work-state.md`, `docs/current/implementation-status.md`, `docs/progress/change-log.md`
- Follow-ups: Recommended next task is now `TASK-VERIFY-004`.

## 2026-03-13 02:20 - Expose last_verify timestamp in status output

- Summary: Updated task-engine status reporting so `aiwf status` includes `last_verify.timestamp` by resolving the latest persisted task verification record for the current `last_run_id`.
- Files changed: `src/aiwf/orchestrator/task_engine.py`, `tests/test_task_engine.py`, `tests/test_cli.py`, `docs/reference/v2-refactoring-target.md`, `docs/current/module-task-list.md`, `docs/current/current-work-state.md`, `docs/current/implementation-status.md`, `docs/progress/change-log.md`
- Verification: `PYTHONPATH=src python3 -m pytest tests/test_task_engine.py::test_get_status_includes_last_verify_timestamp tests/test_cli.py::test_status_includes_last_verify_timestamp -q` and `PYTHONPATH=src python3 -m pytest tests/test_task_engine.py tests/test_cli.py -q`
- Result: pass
- Current docs updated: `docs/reference/v2-refactoring-target.md`, `docs/current/module-task-list.md`, `docs/current/current-work-state.md`, `docs/current/implementation-status.md`, `docs/progress/change-log.md`
- Follow-ups: Recommended next task is now `TASK-INIT-003`.
