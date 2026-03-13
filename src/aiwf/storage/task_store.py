"""Task storage layer. All task file I/O lives here. No business logic."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from aiwf.schema.json_validator import load_schema, validate_payload
from aiwf.storage.ai_workspace import AIWorkspace


def _now() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _next_task_id(ws: AIWorkspace) -> str:
    """Generate the next sequential task ID like 'task-001', 'task-002', etc.

    Scans existing directories in .ai/tasks/ to find the highest number,
    then returns the next one. If no tasks exist, returns 'task-001'.
    """
    tasks_dir = ws.ai_dir / "tasks"
    existing: list[int] = []
    if tasks_dir.exists():
        for child in tasks_dir.iterdir():
            if child.is_dir() and child.name.startswith("task-"):
                try:
                    existing.append(int(child.name.split("-", 1)[1]))
                except (ValueError, IndexError):
                    pass
    next_num = max(existing, default=0) + 1
    return f"task-{next_num:03d}"


def _task_dir(ws: AIWorkspace, task_id: str) -> Path:
    """Return path to .ai/tasks/<task_id>/."""
    return ws.ai_dir / "tasks" / task_id


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def create_task(
    ws: AIWorkspace,
    repo_root: Path,
    *,
    title: str,
    scope: Optional[str] = None,
    acceptance: Optional[str] = None,
    affected_files: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Create a new task spec file and return the spec dict.

    - Generates a sequential task_id
    - Writes .ai/tasks/<task_id>/spec.json
    - Validates against task_spec.schema.json
    - Returns the spec dict

    Raises:
        jsonschema.ValidationError: if the generated spec is invalid (bug)
    """
    task_id = _next_task_id(ws)
    ts = _now()
    spec: Dict[str, Any] = {
        "task_id": task_id,
        "title": title,
        "status": "defined",
        "created_at": ts,
        "updated_at": ts,
        "scope": scope,
        "acceptance": acceptance,
        "affected_files": list(affected_files or []),
        "verify_results": None,
        "block_reason": None,
        "closed_at": None,
    }
    schema = load_schema(repo_root, "task_spec.schema.json")
    validate_payload(spec, schema)
    _write_json(_task_dir(ws, task_id) / "spec.json", spec)
    return spec


def load_task(ws: AIWorkspace, repo_root: Path, task_id: str) -> Dict[str, Any]:
    """Load and validate a task spec.

    Raises:
        FileNotFoundError: if spec.json does not exist
        jsonschema.ValidationError: if spec.json is invalid
    """
    path = _task_dir(ws, task_id) / "spec.json"
    if not path.exists():
        raise FileNotFoundError(f"Task not found: {task_id}")
    spec = _read_json(path)
    validate_payload(spec, load_schema(repo_root, "task_spec.schema.json"))
    return spec


def list_tasks(ws: AIWorkspace, repo_root: Path) -> List[Dict[str, Any]]:
    """Return all task specs, sorted by task_id ascending.

    Invalid or unreadable task directories are silently skipped.
    """
    tasks_dir = ws.ai_dir / "tasks"
    if not tasks_dir.exists():
        return []
    result: list[Dict[str, Any]] = []
    for child in sorted(tasks_dir.iterdir()):
        spec_path = child / "spec.json"
        if child.is_dir() and spec_path.exists():
            try:
                result.append(_read_json(spec_path))
            except (json.JSONDecodeError, OSError):
                pass
    return result


def update_task_status(
    ws: AIWorkspace,
    repo_root: Path,
    task_id: str,
    new_status: str,
    *,
    block_reason: Optional[str] = None,
) -> Dict[str, Any]:
    """Update a task's status field and write back to disk.

    Does NOT validate state machine transitions — that is TaskEngine's job.
    This function only does I/O.

    If new_status is 'blocked', block_reason is written.
    If new_status is not 'blocked', block_reason is cleared to None.
    If new_status is 'done', closed_at is set to now.

    Returns the updated spec dict.

    Raises:
        FileNotFoundError: if task does not exist
    """
    spec = load_task(ws, repo_root, task_id)
    spec["status"] = new_status
    spec["updated_at"] = _now()
    if new_status == "blocked":
        spec["block_reason"] = block_reason
    else:
        spec["block_reason"] = None
    if new_status == "done":
        spec["closed_at"] = _now()
    validate_payload(spec, load_schema(repo_root, "task_spec.schema.json"))
    _write_json(_task_dir(ws, task_id) / "spec.json", spec)
    return spec


def write_verify_results(
    ws: AIWorkspace,
    repo_root: Path,
    task_id: str,
    *,
    run_id: str,
    gates: Dict[str, Any],
    all_passed: bool,
) -> Dict[str, Any]:
    """Write verification results to .ai/tasks/<task_id>/verify.json.

    Also updates the spec's verify_results field.

    Returns the verify record dict.
    """
    ts = _now()
    verify_record: Dict[str, Any] = {
        "task_id": task_id,
        "run_id": run_id,
        "timestamp": ts,
        "gates": gates,
        "all_passed": all_passed,
    }
    schema = load_schema(repo_root, "task_verify.schema.json")
    validate_payload(verify_record, schema)
    _write_json(_task_dir(ws, task_id) / "verify.json", verify_record)

    # Update spec.verify_results
    spec = load_task(ws, repo_root, task_id)
    spec["verify_results"] = {"run_id": run_id, "all_passed": all_passed}
    spec["updated_at"] = ts
    validate_payload(spec, load_schema(repo_root, "task_spec.schema.json"))
    _write_json(_task_dir(ws, task_id) / "spec.json", spec)
    return verify_record


def write_task_record(
    ws: AIWorkspace,
    repo_root: Path,
    task_id: str,
    *,
    last_run_id: str,
    gates_passed: List[str],
) -> Dict[str, Any]:
    """Write completion record to .ai/tasks/<task_id>/record.json.

    Returns the record dict.
    """
    spec = load_task(ws, repo_root, task_id)
    ts = _now()
    record: Dict[str, Any] = {
        "task_id": task_id,
        "title": spec["title"],
        "status": "done",
        "closed_at": ts,
        "last_run_id": last_run_id,
        "gates_passed": gates_passed,
    }
    schema = load_schema(repo_root, "task_record.schema.json")
    validate_payload(record, schema)
    _write_json(_task_dir(ws, task_id) / "record.json", record)
    return record


def find_current_task(ws: AIWorkspace, repo_root: Path) -> Optional[Dict[str, Any]]:
    """Find the task that is currently in_progress.

    Returns the spec dict, or None if no task is in_progress.
    Uses state.json current_task as a hint, falls back to full scan.
    """
    state = ws.read_state()
    hint = state.get("current_task")
    if hint:
        try:
            spec = load_task(ws, repo_root, str(hint))
            if spec.get("status") == "in_progress":
                return spec
        except FileNotFoundError:
            pass
    # Fallback: scan all tasks
    for spec in list_tasks(ws, repo_root):
        if spec.get("status") == "in_progress":
            return spec
    return None


def recount_tasks(ws: AIWorkspace, repo_root: Path) -> Dict[str, int]:
    """Recount all task statuses and return counts dict.

    This is the authoritative way to compute task_counts for state.json.
    """
    counts: Dict[str, int] = {
        "total": 0,
        "defined": 0,
        "in_progress": 0,
        "done": 0,
        "failed": 0,
        "blocked": 0,
    }
    for spec in list_tasks(ws, repo_root):
        status = str(spec.get("status", ""))
        counts["total"] += 1
        if status in counts:
            counts[status] += 1
    return counts
