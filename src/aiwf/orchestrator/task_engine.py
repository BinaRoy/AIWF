"""Task lifecycle engine. Enforces state machine and orchestrates verification."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from aiwf.gate.gate_engine import GateEngine, GateSpec
from aiwf.schema.json_validator import load_schema, validate_payload
from aiwf.storage.ai_workspace import AIWorkspace
from aiwf.storage.task_store import (
    create_task,
    find_current_task,
    list_tasks,
    load_task,
    recount_tasks,
    update_task_status,
    write_task_record,
    write_verify_results,
)
from aiwf.telemetry.sink import TelemetrySink


class TaskStateError(ValueError):
    """Raised when a task state transition is invalid."""


def _run_id() -> str:
    return datetime.now(timezone.utc).strftime("run_%Y%m%d_%H%M%S")


# Valid state transitions: {from_status: {allowed_to_statuses}}
TRANSITIONS: Dict[str, set] = {
    "defined": {"in_progress"},
    "in_progress": {"verifying", "blocked"},
    "verifying": {"done", "failed"},
    "failed": {"in_progress"},
    "blocked": {"in_progress"},
    "done": set(),  # terminal
}


def _assert_transition(from_status: str, to_status: str) -> None:
    """Raise TaskStateError if the transition is not allowed."""
    allowed = TRANSITIONS.get(from_status, set())
    if to_status not in allowed:
        raise TaskStateError(
            f"Cannot transition from '{from_status}' to '{to_status}'. "
            f"Allowed: {sorted(allowed) if allowed else 'none (terminal state)'}"
        )


def _sync_state(
    ws: AIWorkspace,
    repo_root: Path,
    current_task_id: Optional[str] = None,
    last_run_id: Optional[str] = None,
    last_run_result: Optional[str] = None,
) -> None:
    """Update state.json with current task_counts, current_task, and run info."""
    state = ws.read_state()
    state["task_counts"] = recount_tasks(ws, repo_root)
    state["current_task"] = current_task_id
    if last_run_id is not None:
        state["last_run_id"] = last_run_id
    if last_run_result is not None:
        state["last_run_result"] = last_run_result
    ws.write_state(state)


@dataclass
class TaskEngine:
    repo_root: Path
    ws: AIWorkspace
    telemetry: TelemetrySink

    def new_task(
        self,
        title: str,
        *,
        scope: Optional[str] = None,
        acceptance: Optional[str] = None,
        affected_files: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Create a new task in 'defined' status.

        Returns the spec dict.
        Does NOT change current_task in state — task must be explicitly started.
        """
        spec = create_task(
            self.ws,
            self.repo_root,
            title=title,
            scope=scope,
            acceptance=acceptance,
            affected_files=affected_files,
        )
        _sync_state(self.ws, self.repo_root, self._current_task_id())
        self.telemetry.emit("task_created", {"task_id": spec["task_id"], "title": title})
        return spec

    def start_task(self, task_id: Optional[str] = None) -> Dict[str, Any]:
        """Transition a task from 'defined' to 'in_progress'.

        If task_id is None, starts the first task with status 'defined' (by task_id order).

        Raises:
            TaskStateError: if another task is already in_progress
            TaskStateError: if the task is not in 'defined' status
            FileNotFoundError: if the task does not exist
            ValueError: if task_id is None and no defined tasks exist
        """
        current = find_current_task(self.ws, self.repo_root)
        if current is not None:
            raise TaskStateError(
                f"Cannot start task: '{current['task_id']}' is already in_progress"
            )

        if task_id is None:
            for spec in list_tasks(self.ws, self.repo_root):
                if spec.get("status") == "defined":
                    task_id = spec["task_id"]
                    break
            if task_id is None:
                raise ValueError("No tasks with status 'defined' to start")

        spec = load_task(self.ws, self.repo_root, task_id)
        _assert_transition(spec["status"], "in_progress")
        spec = update_task_status(self.ws, self.repo_root, task_id, "in_progress")
        _sync_state(self.ws, self.repo_root, task_id)
        self.telemetry.emit("task_started", {"task_id": task_id})
        return spec

    def verify_task(self, task_id: Optional[str] = None) -> Dict[str, Any]:
        """Run all gates for a task and record results.

        If task_id is None, uses the current in_progress task.

        Steps:
        1. Resolve task (must be in_progress)
        2. Transition to 'verifying'
        3. Read gate config from config.yaml
        4. Run each gate via GateEngine
        5. Write gate reports to .ai/runs/<run_id>/
        6. Write verify results to .ai/tasks/<task_id>/verify.json
        7. If all pass: stay in 'verifying' (ready for close)
        8. If any fail: transition to 'failed'
        9. Update state.json

        Returns dict with: ok, task_id, run_id, gates, all_passed

        Raises:
            TaskStateError: if task is not in 'in_progress'
            FileNotFoundError: if task does not exist
            ValueError: if no gates are configured
        """
        spec = self._resolve_task(task_id, expected_status="in_progress")
        resolved_task_id = spec["task_id"]
        _assert_transition("in_progress", "verifying")
        update_task_status(self.ws, self.repo_root, resolved_task_id, "verifying")

        run_id = _run_id()
        cfg = self.ws.read_config()
        gates_cfg = cfg.get("gates") or {}
        if not gates_cfg:
            update_task_status(self.ws, self.repo_root, resolved_task_id, "failed")
            _sync_state(self.ws, self.repo_root, resolved_task_id)
            raise ValueError("No gates configured in .ai/config.yaml")

        reports_dir = self.ws.ai_dir / "runs" / run_id
        gate_engine = GateEngine(reports_dir=reports_dir)
        gate_schema = load_schema(self.repo_root, "gate_result.schema.json")
        run_schema = load_schema(self.repo_root, "run_record.schema.json")

        self.telemetry.emit(
            "verify_started", {"task_id": resolved_task_id, "run_id": run_id}
        )

        gates_result: Dict[str, Any] = {}
        all_passed = True
        for name, cmd in gates_cfg.items():
            res = gate_engine.run(GateSpec(name=name, command=str(cmd)), run_id=run_id)
            gate_payload = res.__dict__
            validate_payload(gate_payload, gate_schema)
            gates_result[name] = {
                "status": res.status,
                "exit_code": res.exit_code,
                "duration_seconds": res.duration_seconds,
            }
            self.telemetry.emit(
                "gate_result", {"name": name, "status": res.status}, run_id=run_id
            )
            if res.status != "pass":
                all_passed = False

        # Write run record
        run_record = {
            "run_id": run_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "task_id": resolved_task_id,
            "result": "pass" if all_passed else "fail",
            "ok": all_passed,
            "gates": gates_result,
        }
        validate_payload(run_record, run_schema)
        run_dir = self.ws.ai_dir / "runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "run.json").write_text(
            json.dumps(run_record, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        # Write task verify results
        write_verify_results(
            self.ws,
            self.repo_root,
            resolved_task_id,
            run_id=run_id,
            gates=gates_result,
            all_passed=all_passed,
        )

        # Transition based on result
        if not all_passed:
            update_task_status(self.ws, self.repo_root, resolved_task_id, "failed")

        _sync_state(
            self.ws,
            self.repo_root,
            current_task_id=resolved_task_id,
            last_run_id=run_id,
            last_run_result="pass" if all_passed else "fail",
        )

        self.telemetry.emit(
            "verify_finished",
            {"task_id": resolved_task_id, "run_id": run_id, "all_passed": all_passed},
        )
        return {
            "ok": all_passed,
            "task_id": resolved_task_id,
            "run_id": run_id,
            "gates": gates_result,
            "all_passed": all_passed,
        }

    def close_task(self, task_id: Optional[str] = None) -> Dict[str, Any]:
        """Close a task that has passed verification.

        Task must be in 'verifying' status with all_passed=True in verify_results.

        Returns the completion record dict.

        Raises:
            TaskStateError: if task is not in 'verifying'
            TaskStateError: if last verification did not pass
        """
        spec = self._resolve_task(task_id, expected_status="verifying")
        resolved_task_id = spec["task_id"]

        verify_results = spec.get("verify_results") or {}
        if not verify_results.get("all_passed"):
            raise TaskStateError(
                "Cannot close task: last verification did not pass. "
                "Run 'aiwf task verify' first."
            )

        _assert_transition("verifying", "done")
        update_task_status(self.ws, self.repo_root, resolved_task_id, "done")

        last_run_id = verify_results.get("run_id", "")
        gates_passed: List[str] = []
        verify_path = self.ws.ai_dir / "tasks" / resolved_task_id / "verify.json"
        if verify_path.exists():
            verify_data = json.loads(verify_path.read_text(encoding="utf-8"))
            gates_passed = [
                name
                for name, g in (verify_data.get("gates") or {}).items()
                if isinstance(g, dict) and g.get("status") == "pass"
            ]

        record = write_task_record(
            self.ws,
            self.repo_root,
            resolved_task_id,
            last_run_id=last_run_id,
            gates_passed=gates_passed,
        )

        _sync_state(self.ws, self.repo_root, current_task_id=None)
        self.telemetry.emit("task_closed", {"task_id": resolved_task_id})
        return record

    def block_task(
        self, task_id: Optional[str] = None, *, reason: str
    ) -> Dict[str, Any]:
        """Block a task that is in_progress.

        Raises:
            TaskStateError: if task is not in 'in_progress'
        """
        spec = self._resolve_task(task_id, expected_status="in_progress")
        resolved_task_id = spec["task_id"]
        _assert_transition("in_progress", "blocked")
        spec = update_task_status(
            self.ws,
            self.repo_root,
            resolved_task_id,
            "blocked",
            block_reason=reason,
        )
        _sync_state(self.ws, self.repo_root, current_task_id=None)
        self.telemetry.emit(
            "task_blocked", {"task_id": resolved_task_id, "reason": reason}
        )
        return spec

    def unblock_task(self, task_id: str) -> Dict[str, Any]:
        """Unblock a blocked task, returning it to in_progress.

        Raises:
            TaskStateError: if task is not in 'blocked'
            TaskStateError: if another task is already in_progress
        """
        current = find_current_task(self.ws, self.repo_root)
        if current is not None:
            raise TaskStateError(
                f"Cannot unblock: '{current['task_id']}' is already in_progress"
            )
        spec = load_task(self.ws, self.repo_root, task_id)
        _assert_transition(spec["status"], "in_progress")
        spec = update_task_status(self.ws, self.repo_root, task_id, "in_progress")
        _sync_state(self.ws, self.repo_root, current_task_id=task_id)
        self.telemetry.emit("task_unblocked", {"task_id": task_id})
        return spec

    def retry_task(self, task_id: Optional[str] = None) -> Dict[str, Any]:
        """Retry a failed task, returning it to in_progress.

        If task_id is None, retries the most recently failed task.

        Raises:
            TaskStateError: if task is not in 'failed'
            TaskStateError: if another task is already in_progress
            ValueError: if no failed tasks exist
        """
        if task_id is None:
            for spec in reversed(list_tasks(self.ws, self.repo_root)):
                if spec.get("status") == "failed":
                    task_id = spec["task_id"]
                    break
            if task_id is None:
                raise ValueError("No failed tasks to retry")

        current = find_current_task(self.ws, self.repo_root)
        if current is not None:
            raise TaskStateError(
                f"Cannot retry: '{current['task_id']}' is already in_progress"
            )
        spec = load_task(self.ws, self.repo_root, task_id)
        _assert_transition(spec["status"], "in_progress")
        spec = update_task_status(self.ws, self.repo_root, task_id, "in_progress")
        _sync_state(self.ws, self.repo_root, current_task_id=task_id)
        self.telemetry.emit("task_retried", {"task_id": task_id})
        return spec

    def get_status(self) -> Dict[str, Any]:
        """Build the global status summary.

        Returns dict with: current_task, tasks (counts), last_verify.
        """
        state = self.ws.read_state()
        current = find_current_task(self.ws, self.repo_root)
        last_verify = self._last_verify_summary(state.get("last_run_id"), state.get("last_run_result"))
        current_info = None
        if current:
            current_info = {
                "task_id": current["task_id"],
                "title": current["title"],
                "status": current["status"],
            }
        return {
            "current_task": current_info,
            "tasks": recount_tasks(self.ws, self.repo_root),
            "last_verify": last_verify,
        }

    def _last_verify_summary(
        self, last_run_id: Optional[str], last_run_result: Optional[str]
    ) -> Dict[str, Any]:
        summary: Dict[str, Any] = {
            "run_id": last_run_id,
            "result": last_run_result,
            "timestamp": None,
        }
        if not last_run_id:
            return summary

        for spec in reversed(list_tasks(self.ws, self.repo_root)):
            verify_path = self.ws.ai_dir / "tasks" / spec["task_id"] / "verify.json"
            if not verify_path.exists():
                continue
            verify_record = json.loads(verify_path.read_text(encoding="utf-8"))
            if verify_record.get("run_id") == last_run_id:
                summary["timestamp"] = verify_record.get("timestamp")
                return summary
        return summary

    def _resolve_task(
        self, task_id: Optional[str], *, expected_status: str
    ) -> Dict[str, Any]:
        """Resolve task_id (or use current/scan) and assert expected status.

        Raises:
            FileNotFoundError: task not found
            TaskStateError: task is not in the expected status
        """
        if task_id is not None:
            spec = load_task(self.ws, self.repo_root, task_id)
        elif expected_status == "in_progress":
            spec_or_none = find_current_task(self.ws, self.repo_root)
            if spec_or_none is None:
                raise TaskStateError("No task is currently in_progress")
            spec = spec_or_none
        elif expected_status == "verifying":
            spec = None
            for s in list_tasks(self.ws, self.repo_root):
                if s.get("status") == "verifying":
                    spec = s
                    break
            if spec is None:
                raise TaskStateError("No task is in 'verifying' status")
        else:
            raise TaskStateError(
                f"Cannot auto-resolve task for status '{expected_status}'"
            )

        if spec["status"] != expected_status:
            raise TaskStateError(
                f"Task '{spec['task_id']}' is in '{spec['status']}', "
                f"expected '{expected_status}'"
            )
        return spec

    def _current_task_id(self) -> Optional[str]:
        current = find_current_task(self.ws, self.repo_root)
        return current["task_id"] if current else None
