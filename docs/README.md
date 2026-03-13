# AIWF Docs

This repository uses a stable document set. Current source-of-truth files do not use dates in their paths.

For agents, this file is **not** the entrypoint. Start from `../AGENTS.md` and follow the read chain defined there.

## Stable Document Set

### Current source of truth

- `current/project-structure.md`
- `current/agent-development-loop.md`
- `current/implementation-status.md`

### Target reference

- `reference/v2-refactoring-target.md`

### Session record

- `progress/change-log.md`

## Rules

- Current-state documents are overwritten in place when the repository state changes.
- The path names above must stay stable so the next agent session can always read the same entrypoints.
- Historical reasoning belongs in git history and the append-only change log, not in parallel active docs with different filenames.
