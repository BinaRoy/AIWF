# AIWF Agent Development Loop

Last updated: 2026-03-13

This document defines the mandatory loop for an agent continuing development on this repository.

Its purpose is:

- always start from the same current documents
- guarantee that changed repository state is written back to the same stable paths
- require a post-task record so the next session can recover context quickly

This loop is for developing the AIWF repository itself. It is not the runtime behavior of AIWF on another project.

---

## 1. Absolute Entry And Read Order Before Coding

Every implementation session must begin at `AGENTS.md`. That file is the only agent entrypoint.

From `AGENTS.md`, continue with this read order:

1. `README.md`
2. `docs/README.md`
3. `docs/current/project-structure.md`
4. `docs/current/agent-development-loop.md`
5. `docs/current/implementation-status.md`

Read this additional file when needed:

6. `docs/reference/v2-refactoring-target.md`
   Required when the task changes behavior that the v2 target already specifies, or when closing a target deviation.

Read this additional file before closing the task:

7. `docs/progress/change-log.md`
   Read the latest entries to avoid duplicating or contradicting the most recent recorded state.

After that, read only the relevant implementation paths:

- `src/aiwf/`
- `schemas/`
- `tests/`
- `.github/workflows/`
- `pyproject.toml`

Do not begin from `.ai/` unless the task is explicitly about runtime artifacts or persisted execution evidence.

---

## 2. Stable Path Rule

The current guidance paths are stable and must not drift with dates:

- `AGENTS.md`
- `docs/current/project-structure.md`
- `docs/current/agent-development-loop.md`
- `docs/current/implementation-status.md`
- `docs/reference/v2-refactoring-target.md`
- `docs/progress/change-log.md`

If repository state changes, update these files in place instead of creating a new dated current-state document.

Use dated filenames only when a task explicitly needs a standalone plan artifact, not for the current read entrypoints.

---

## 3. Repository Boundary Rules

Keep these categories separate:

### Project code

- `src/aiwf/`
- `schemas/`
- `tests/`
- `.github/workflows/`
- `pyproject.toml`

### Development-process records

- `AGENTS.md`
- `README.md`
- `docs/`

### Runtime evidence

- `.ai/`

Rule:

- code and current docs define repository truth
- runtime evidence confirms execution
- runtime evidence does not replace current documentation

---

## 4. Implementation Loop

### Step 1: Rebuild context

Read the mandatory current docs, then the relevant code and tests.

Decide whether the task is:

- a current-behavior change
- a target-alignment change
- a documentation-only clarification
- a repository-structure change

### Step 2: Identify required sync targets

Before editing, identify which files must remain aligned:

- CLI behavior: `src/aiwf/cli/main.py`
- engine/state behavior: `src/aiwf/orchestrator/task_engine.py`
- persisted contracts: `schemas/`
- tests: `tests/`
- user-facing current description: `README.md`
- repo guidance and read order: `AGENTS.md`, `docs/README.md`, `docs/current/*.md`
- target design: `docs/reference/v2-refactoring-target.md`

No state-changing task is complete until all affected sync targets are updated.

### Step 3: Implement with small diffs

Modify the minimum necessary files.

When behavior changes:

- update code
- update tests
- update current docs that describe the changed behavior

When structure changes:

- update path descriptions
- update read order references
- remove conflicting guidance

### Step 4: Verify

Run the relevant verification command for the change.

Current repository-wide test command:

```bash
PYTHONPATH=src python3 -m pytest tests/ -q
```

Run the smallest relevant subset first when useful, then the broader verification before claiming completion when feasible.

### Step 5: Mandatory post-task record actions

After implementation and verification, the agent must perform all applicable record actions.

#### A. Update current-state docs in place

Update these files when applicable:

- `README.md`
  When current behavior, supported commands, or repository boundary wording changes.
- `docs/current/project-structure.md`
  When directory responsibilities, ownership, or read paths change.
- `docs/current/agent-development-loop.md`
  When the required workflow, mandatory reads, or completion-record rules change.
- `docs/current/implementation-status.md`
  When implementation status, gaps, deviations, or completed work changes.
- `docs/README.md`
  When the read order or current document set changes.
- `AGENTS.md`
  When the repository-level agent instructions or required read order changes.
- `docs/reference/v2-refactoring-target.md`
  Only when the intended v2 target itself changes.

#### B. Append a factual session record

Append one new entry to `docs/progress/change-log.md` for every completed development task.

Each entry must include:

- date
- task summary
- files changed
- verification command actually run
- result
- which current docs were updated
- open follow-up items, if any

Do not skip this step even if the change was documentation-only.

#### C. Remove conflicts

If the task made a current document obsolete or contradictory, delete or rewrite the conflicting file in the same task. Do not leave parallel active guidance behind.

---

## 5. Change-Log Entry Template

Use this template when appending to `docs/progress/change-log.md`:

```md
## YYYY-MM-DD HH:MM - Short task title

- Summary: ...
- Files changed: `path/a`, `path/b`
- Verification: `command`
- Result: pass | fail | not run
- Current docs updated: `README.md`, `docs/current/...`
- Follow-ups: ...
```

Write only factual statements. Do not claim behavior that was not verified.

---

## 6. Anti-Patterns

Do not do these:

- create a new dated current-state doc instead of updating the stable current path
- update code without updating affected current docs
- finish a task without appending to `docs/progress/change-log.md`
- start from a document other than `AGENTS.md`
- use `.ai/plan.json` or `.ai/roles_workflow.json` as current repository guidance
- update README with aspirational features
- leave multiple conflicting workflow documents alive

---

## 7. One-Line Rule

Start at `AGENTS.md`, read the stable current docs, change code, verify, update all affected current docs, and append one factual change-log entry last.
