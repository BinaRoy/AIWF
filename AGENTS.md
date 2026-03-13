# Agent guide (Codex / other coding agents)

This file is the **only agent entrypoint** for this repository.

This repo is designed for agentic development with **strict contracts**.

## Operating rules
1. **Read before write.** Inspect existing files before changing anything.
2. **Patch-first changes.** Propose a unified diff patch first; apply via framework logic.
3. **Everything is recorded.**
   - Task verification writes `.ai/runs/<run_id>/run.json`
   - Task artifacts live under `.ai/tasks/<task-id>/`
   - Telemetry writes `.ai/telemetry/events.jsonl`
4. **Small diffs.** Prefer minimal, high-confidence changes.

## Required Read Chain

Before changing code, read these files in order:

1. `README.md`
2. `docs/README.md`
3. `docs/current/project-structure.md`
4. `docs/current/module-task-list.md`
5. `docs/current/current-work-state.md`
6. `docs/current/agent-development-loop.md`
7. `docs/current/implementation-status.md`

If the task changes v2 behavior or contract, also read:

8. `docs/reference/v2-refactoring-target.md`

At the end of every implementation task, update all affected current docs and append a factual entry to:

9. `docs/progress/change-log.md`

## Repo Boundary

- `src/`, `schemas/`, `tests/`, `.github/workflows/`, `pyproject.toml` are project code.
- `docs/` contains development guidance, plans, and progress records.
- `.ai/` is runtime workspace data and verification evidence. It is **not** the source of truth for repository design decisions.

## Using Codex CLI
- Install: `npm i -g @openai/codex`
- Run (in this folder): `codex`
- First run prompts sign-in.

Docs: OpenAI Codex CLI setup and reference.
