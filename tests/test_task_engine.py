"""Tests for TaskEngine — state machine transitions and verification orchestration."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

from aiwf.orchestrator.task_engine import TaskEngine, TaskStateError
from aiwf.storage.ai_workspace import AIWorkspace
from aiwf.storage.task_store import update_task_status
from aiwf.telemetry.sink import TelemetrySink


REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def ws(tmp_path: Path) -> AIWorkspace:
    workspace = AIWorkspace(tmp_path)
    workspace.ensure_layout()
    return workspace


@pytest.fixture()
def engine(ws: AIWorkspace, tmp_path: Path) -> TaskEngine:
    telemetry = TelemetrySink(ws.ai_dir / "telemetry" / "events.jsonl")
    return TaskEngine(repo_root=REPO_ROOT, ws=ws, telemetry=telemetry)


def _set_gates(ws: AIWorkspace, gates: dict) -> None:
    """Write gate config into .ai/config.yaml."""
    cfg = {"gates": gates}
    (ws.ai_dir / "config.yaml").write_text(
        yaml.dump(cfg), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# new_task
# ---------------------------------------------------------------------------

def test_new_task_creates_defined_task(engine: TaskEngine, ws: AIWorkspace) -> None:
    spec = engine.new_task("Do something")
    assert spec["task_id"] == "task-001"
    assert spec["status"] == "defined"
    assert spec["title"] == "Do something"
    assert (ws.ai_dir / "tasks" / "task-001" / "spec.json").exists()


# ---------------------------------------------------------------------------
# start_task
# ---------------------------------------------------------------------------

def test_start_task_transitions_to_in_progress(engine: TaskEngine, ws: AIWorkspace) -> None:
    engine.new_task("First task")
    spec = engine.start_task("task-001")
    assert spec["status"] == "in_progress"
    state = ws.read_state()
    assert state["current_task"] == "task-001"


def test_start_task_rejects_when_another_active(engine: TaskEngine) -> None:
    engine.new_task("Task A")
    engine.new_task("Task B")
    engine.start_task("task-001")
    with pytest.raises(TaskStateError, match="already in_progress"):
        engine.start_task("task-002")


def test_start_task_auto_selects_first_defined(engine: TaskEngine) -> None:
    engine.new_task("Alpha")
    engine.new_task("Beta")
    spec = engine.start_task()  # no task_id given
    assert spec["task_id"] == "task-001"
    assert spec["status"] == "in_progress"


def test_start_task_rejects_non_defined_task(engine: TaskEngine, ws: AIWorkspace) -> None:
    engine.new_task("Already done")
    # Manually force to done (bypassing engine transitions)
    update_task_status(ws, REPO_ROOT, "task-001", "in_progress")
    update_task_status(ws, REPO_ROOT, "task-001", "verifying")
    update_task_status(ws, REPO_ROOT, "task-001", "done")
    with pytest.raises(TaskStateError):
        engine.start_task("task-001")


# ---------------------------------------------------------------------------
# verify_task
# ---------------------------------------------------------------------------

def test_verify_task_runs_gates_and_records(engine: TaskEngine, ws: AIWorkspace) -> None:
    _set_gates(ws, {"echo_gate": f"{sys.executable} -c 'import sys; sys.exit(0)'"})
    engine.new_task("Verify me")
    engine.start_task("task-001")
    result = engine.verify_task("task-001")
    assert result["all_passed"] is True
    assert result["ok"] is True
    assert "echo_gate" in result["gates"]
    assert result["gates"]["echo_gate"]["status"] == "pass"
    assert (ws.ai_dir / "tasks" / "task-001" / "verify.json").exists()
    run_dir = ws.ai_dir / "runs" / result["run_id"]
    assert (run_dir / "run.json").exists()


def test_verify_task_fails_and_transitions_to_failed(engine: TaskEngine, ws: AIWorkspace) -> None:
    _set_gates(ws, {"fail_gate": f"{sys.executable} -c 'import sys; sys.exit(1)'"})
    engine.new_task("Will fail")
    engine.start_task("task-001")
    result = engine.verify_task("task-001")
    assert result["all_passed"] is False
    from aiwf.storage.task_store import load_task
    spec = load_task(ws, REPO_ROOT, "task-001")
    assert spec["status"] == "failed"


def test_verify_task_rejects_non_in_progress(engine: TaskEngine) -> None:
    engine.new_task("Not started")
    with pytest.raises(TaskStateError):
        engine.verify_task("task-001")


def test_verify_task_raises_when_no_gates(engine: TaskEngine, ws: AIWorkspace) -> None:
    _set_gates(ws, {})
    engine.new_task("No gates")
    engine.start_task("task-001")
    with pytest.raises(ValueError, match="No gates configured"):
        engine.verify_task("task-001")


# ---------------------------------------------------------------------------
# close_task
# ---------------------------------------------------------------------------

def test_close_task_transitions_to_done(engine: TaskEngine, ws: AIWorkspace) -> None:
    _set_gates(ws, {"pass_gate": f"{sys.executable} -c 'import sys; sys.exit(0)'"})
    engine.new_task("To close")
    engine.start_task("task-001")
    engine.verify_task("task-001")
    record = engine.close_task("task-001")
    assert record["status"] == "done"
    assert (ws.ai_dir / "tasks" / "task-001" / "record.json").exists()
    state = ws.read_state()
    assert state["current_task"] is None


def test_close_task_rejects_when_not_verified(engine: TaskEngine) -> None:
    engine.new_task("Not verified")
    engine.start_task("task-001")
    with pytest.raises(TaskStateError):
        engine.close_task("task-001")


def test_close_task_rejects_when_verify_failed(engine: TaskEngine, ws: AIWorkspace) -> None:
    _set_gates(ws, {"fail_gate": f"{sys.executable} -c 'import sys; sys.exit(1)'"})
    engine.new_task("Verify failed")
    engine.start_task("task-001")
    engine.verify_task("task-001")
    # Task is now in 'failed' — not verifying, so close should reject
    with pytest.raises(TaskStateError):
        engine.close_task("task-001")


# ---------------------------------------------------------------------------
# block_task / unblock_task
# ---------------------------------------------------------------------------

def test_block_task_transitions_to_blocked(engine: TaskEngine, ws: AIWorkspace) -> None:
    engine.new_task("Will block")
    engine.start_task("task-001")
    spec = engine.block_task("task-001", reason="Waiting on external API")
    assert spec["status"] == "blocked"
    assert spec["block_reason"] == "Waiting on external API"
    state = ws.read_state()
    assert state["current_task"] is None


def test_block_task_rejects_non_in_progress(engine: TaskEngine) -> None:
    engine.new_task("Defined task")
    with pytest.raises(TaskStateError):
        engine.block_task("task-001", reason="Should not work")


def test_unblock_task_transitions_to_in_progress(engine: TaskEngine, ws: AIWorkspace) -> None:
    engine.new_task("Blocked task")
    engine.start_task("task-001")
    engine.block_task("task-001", reason="Blocked")
    spec = engine.unblock_task("task-001")
    assert spec["status"] == "in_progress"
    state = ws.read_state()
    assert state["current_task"] == "task-001"


def test_unblock_task_rejects_when_another_active(engine: TaskEngine) -> None:
    engine.new_task("Active")
    engine.new_task("Blocked")
    engine.start_task("task-001")
    # Manually block task-002 by bypassing engine
    update_task_status(ws=engine.ws, repo_root=REPO_ROOT, task_id="task-002", new_status="in_progress")
    update_task_status(ws=engine.ws, repo_root=REPO_ROOT, task_id="task-002", new_status="blocked")
    with pytest.raises(TaskStateError, match="already in_progress"):
        engine.unblock_task("task-002")


# ---------------------------------------------------------------------------
# retry_task
# ---------------------------------------------------------------------------

def test_retry_task_transitions_failed_to_in_progress(engine: TaskEngine, ws: AIWorkspace) -> None:
    _set_gates(ws, {"fail_gate": f"{sys.executable} -c 'import sys; sys.exit(1)'"})
    engine.new_task("Will retry")
    engine.start_task("task-001")
    engine.verify_task("task-001")  # should fail -> status: failed
    spec = engine.retry_task("task-001")
    assert spec["status"] == "in_progress"


def test_retry_task_rejects_non_failed(engine: TaskEngine) -> None:
    engine.new_task("Done task")
    update_task_status(ws=engine.ws, repo_root=REPO_ROOT, task_id="task-001", new_status="in_progress")
    update_task_status(ws=engine.ws, repo_root=REPO_ROOT, task_id="task-001", new_status="verifying")
    update_task_status(ws=engine.ws, repo_root=REPO_ROOT, task_id="task-001", new_status="done")
    # Done task has no active task, but retry should raise TaskStateError
    with pytest.raises(TaskStateError):
        engine.retry_task("task-001")


# ---------------------------------------------------------------------------
# get_status
# ---------------------------------------------------------------------------

def test_get_status_returns_summary(engine: TaskEngine, ws: AIWorkspace) -> None:
    engine.new_task("A")  # defined
    engine.new_task("B")  # will be in_progress
    engine.start_task("task-002")
    status = engine.get_status()
    assert status["current_task"] is not None
    assert status["current_task"]["task_id"] == "task-002"
    assert status["tasks"]["total"] == 2
    assert status["tasks"]["defined"] == 1
    assert status["tasks"]["in_progress"] == 1


def test_get_status_includes_last_verify_timestamp(engine: TaskEngine, ws: AIWorkspace) -> None:
    _set_gates(ws, {"pass_gate": f"{sys.executable} -c 'import sys; sys.exit(0)'"})
    engine.new_task("Verified task")
    engine.start_task("task-001")
    engine.verify_task("task-001")

    verify_record = json.loads(
        (ws.ai_dir / "tasks" / "task-001" / "verify.json").read_text(encoding="utf-8")
    )
    status = engine.get_status()

    assert status["last_verify"]["run_id"] == verify_record["run_id"]
    assert status["last_verify"]["result"] == "pass"
    assert status["last_verify"]["timestamp"] == verify_record["timestamp"]


# ---------------------------------------------------------------------------
# Full lifecycle
# ---------------------------------------------------------------------------

def test_full_lifecycle_new_start_verify_close(engine: TaskEngine, ws: AIWorkspace) -> None:
    _set_gates(ws, {"pass_gate": f"{sys.executable} -c 'import sys; sys.exit(0)'"})

    # Create and start
    spec = engine.new_task("Full lifecycle task", scope="s", acceptance="a")
    assert spec["status"] == "defined"

    spec = engine.start_task("task-001")
    assert spec["status"] == "in_progress"

    # Verify
    result = engine.verify_task("task-001")
    assert result["all_passed"] is True

    # Close
    record = engine.close_task("task-001")
    assert record["status"] == "done"

    # State should have no active task
    state = ws.read_state()
    assert state["current_task"] is None
    assert state["last_run_result"] == "pass"
    assert state["task_counts"]["done"] == 1
