# AIWF Current Work State

Last updated: 2026-03-13

This file is the current-state companion to `docs/current/module-task-list.md`.

Agents should read this file after the module/task list to know:

- what the current focus is
- which module is active
- which task should be selected next by default
- what is blocked
- what was completed most recently

---

current_focus: `Core v2 gaps are closed; only future-facing product expansion tasks remain`

active_module: `M4. Inspect Current State`

recommended_next_task: `TASK-STATE-003`

why_this_next: `It is now the earliest remaining defined task in the master list after the current v2 core contract and packaging work reached the documented target state.`

blocked_tasks:

- none currently recorded

recently_completed:

- `TASK-INIT-003` align packaging metadata with v2 target install expectations
- `TASK-VERIFY-004` expose `last_verify.timestamp` in status output
- `TASK-LIFE-004` align invalid-state exit codes with documented contract
- `TASK-INIT-002` align `aiwf init` output with target JSON contract
- `TASK-VERIFY-003` make standalone `aiwf verify` write `run.json`
- `TASK-LIFE-003` align `task new` CLI contract with target syntax
- `TASK-DOCS-001` single agent entrypoint and stable current-doc paths
- `TASK-DOCS-002` append-only repository change log
- `TASK-STATE-002` add module/task planning surface for repository development

must_read_before_next_task:

- `AGENTS.md`
- `docs/current/module-task-list.md`
- `docs/current/agent-development-loop.md`
- `docs/current/implementation-status.md`
- `docs/reference/v2-refactoring-target.md`

selection_rule:

1. If the user explicitly names a task, follow the user instruction.
2. Otherwise start from `recommended_next_task`.
3. If that task is blocked, already done, or no longer dependency-ready, recompute using the selection rule in `docs/current/module-task-list.md`.
4. After recomputing, update this file before implementing.

completion_rule:

After a task is completed, update:

- `docs/current/current-work-state.md`
- `docs/current/implementation-status.md` when status changed
- `docs/progress/change-log.md`

If the completed task changed module boundaries, dependencies, or priorities, also update `docs/current/module-task-list.md`.
