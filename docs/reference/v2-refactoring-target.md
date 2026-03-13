# AIWF v2 Refactoring Target

Last updated: 2026-03-13

This file is the stable-path target reference for the v2 refactor. It replaces dated target-read paths as the file agents should consult when judging current behavior against intended behavior.

The target v2 direction is:

- AIWF remains a CLI tool for controlled, traceable, verifiable development work with AI agents.
- The tool lives inside `.ai/` and does not impose project-file structure outside that workspace.
- The core enforced loop is:

```text
init -> task new -> task start -> development happens -> task verify -> task close -> status
```

- The task lifecycle states are:

```text
defined -> in_progress -> verifying -> done
in_progress -> blocked
verifying -> failed
failed -> in_progress
blocked -> in_progress
```

The target active CLI surface is:

- `aiwf init`
- `aiwf status`
- `aiwf verify`
- `aiwf task new "<title>" [--scope] [--accept] [--files]`
- `aiwf task start [task-id]`
- `aiwf task current`
- `aiwf task list`
- `aiwf task verify [task-id]`
- `aiwf task close [task-id]`
- `aiwf task block [task-id] --reason "..."`
- `aiwf task unblock [task-id]`
- `aiwf task retry [task-id]`
- `aiwf map init`
- `aiwf map add <module-id> "<title>" [--description "..."]`
- `aiwf map link <module-id> <task-id>`
- `aiwf map show`

The target machine-readable init payload is:

```json
{
  "ok": true,
  "workspace": ".ai",
  "config": ".ai/config.yaml",
  "state": ".ai/state.json"
}
```

The target exit-code contract is:

- `0` for successful command completion
- `1` for execution failures after a valid command was accepted, such as a gate returning fail
- `2` for invalid input or invalid task/workspace state

The target status payload includes:

- `current_task`
- `tasks`
- `last_verify.run_id`
- `last_verify.result`
- `last_verify.timestamp`

The target workspace layout is:

```text
.ai/
  config.yaml
  state.json
  tasks/
    task-001/
      spec.json
      verify.json
      record.json
  project_map.json
  runs/
    <run_id>/
      run.json
      <gate>.json
  telemetry/
    events.jsonl
```

The target data-contract direction is:

- `task_spec.schema.json`
- `task_verify.schema.json`
- `task_record.schema.json`
- simplified `state.schema.json`
- simplified `run_record.schema.json`
- retained `gate_result.schema.json`
- `project_map.schema.json`

The target packaging and CI direction is:

- `pyproject.toml` uses `setuptools>=64`
- setuptools package discovery reads packages from `src/`
- CI installs the package, runs `aiwf init`, runs `aiwf verify`, and then runs the test suite

The target intentionally does not include:

- project scanning as a finished feature
- git automation as a finished feature
- multi-agent orchestration as a finished feature
- v1 `develop` / `roles` / `dispatch` runtime as current behavior

When target behavior changes, update this file in place. Do not create a new dated target file for the current refactor target.
