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
