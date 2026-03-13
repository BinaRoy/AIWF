from __future__ import annotations

from pathlib import Path

import pytest

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


@pytest.fixture()
def ws(tmp_path: Path) -> AIWorkspace:
    workspace = AIWorkspace(tmp_path)
    workspace.ensure_layout()
    return workspace


@pytest.fixture()
def repo_root(tmp_path: Path) -> Path:
    return Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# create_task
# ---------------------------------------------------------------------------

def test_create_task_writes_spec_and_returns_dict(ws: AIWorkspace, repo_root: Path) -> None:
    spec = create_task(ws, repo_root, title="First task")
    assert spec["task_id"] == "task-001"
    assert spec["status"] == "defined"
    assert spec["title"] == "First task"
    assert (ws.ai_dir / "tasks" / "task-001" / "spec.json").exists()


def test_create_task_increments_id(ws: AIWorkspace, repo_root: Path) -> None:
    spec1 = create_task(ws, repo_root, title="First")
    spec2 = create_task(ws, repo_root, title="Second")
    assert spec1["task_id"] == "task-001"
    assert spec2["task_id"] == "task-002"


def test_create_task_stores_optional_fields(ws: AIWorkspace, repo_root: Path) -> None:
    spec = create_task(
        ws,
        repo_root,
        title="With details",
        scope="Some scope",
        acceptance="Criteria here",
        affected_files=["src/foo.py", "tests/test_foo.py"],
    )
    assert spec["scope"] == "Some scope"
    assert spec["acceptance"] == "Criteria here"
    assert spec["affected_files"] == ["src/foo.py", "tests/test_foo.py"]


def test_create_task_sets_null_for_missing_optional_fields(ws: AIWorkspace, repo_root: Path) -> None:
    spec = create_task(ws, repo_root, title="Minimal")
    assert spec["scope"] is None
    assert spec["acceptance"] is None
    assert spec["affected_files"] == []
    assert spec["verify_results"] is None
    assert spec["block_reason"] is None
    assert spec["closed_at"] is None


# ---------------------------------------------------------------------------
# load_task
# ---------------------------------------------------------------------------

def test_load_task_reads_existing_spec(ws: AIWorkspace, repo_root: Path) -> None:
    created = create_task(ws, repo_root, title="Load me")
    loaded = load_task(ws, repo_root, "task-001")
    assert loaded["task_id"] == created["task_id"]
    assert loaded["title"] == created["title"]


def test_load_task_raises_for_missing_task(ws: AIWorkspace, repo_root: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_task(ws, repo_root, "task-999")


# ---------------------------------------------------------------------------
# list_tasks
# ---------------------------------------------------------------------------

def test_list_tasks_returns_all_sorted(ws: AIWorkspace, repo_root: Path) -> None:
    create_task(ws, repo_root, title="C")
    create_task(ws, repo_root, title="A")
    create_task(ws, repo_root, title="B")
    tasks = list_tasks(ws, repo_root)
    assert len(tasks) == 3
    assert [t["task_id"] for t in tasks] == ["task-001", "task-002", "task-003"]


def test_list_tasks_empty_when_no_tasks(ws: AIWorkspace, repo_root: Path) -> None:
    assert list_tasks(ws, repo_root) == []


# ---------------------------------------------------------------------------
# update_task_status
# ---------------------------------------------------------------------------

def test_update_task_status_writes_new_status(ws: AIWorkspace, repo_root: Path) -> None:
    create_task(ws, repo_root, title="Update me")
    updated = update_task_status(ws, repo_root, "task-001", "in_progress")
    assert updated["status"] == "in_progress"
    # Verify file was updated
    reloaded = load_task(ws, repo_root, "task-001")
    assert reloaded["status"] == "in_progress"


def test_update_task_status_changes_updated_at(ws: AIWorkspace, repo_root: Path) -> None:
    spec = create_task(ws, repo_root, title="Time test")
    original_updated_at = spec["updated_at"]
    import time; time.sleep(0.01)
    updated = update_task_status(ws, repo_root, "task-001", "in_progress")
    assert updated["updated_at"] >= original_updated_at


def test_update_task_status_sets_block_reason(ws: AIWorkspace, repo_root: Path) -> None:
    create_task(ws, repo_root, title="Will block")
    update_task_status(ws, repo_root, "task-001", "in_progress")
    updated = update_task_status(ws, repo_root, "task-001", "blocked", block_reason="Waiting on API")
    assert updated["block_reason"] == "Waiting on API"


def test_update_task_status_clears_block_reason(ws: AIWorkspace, repo_root: Path) -> None:
    create_task(ws, repo_root, title="Unblock me")
    update_task_status(ws, repo_root, "task-001", "in_progress")
    update_task_status(ws, repo_root, "task-001", "blocked", block_reason="Some reason")
    updated = update_task_status(ws, repo_root, "task-001", "in_progress")
    assert updated["block_reason"] is None


def test_update_task_status_sets_closed_at_for_done(ws: AIWorkspace, repo_root: Path) -> None:
    create_task(ws, repo_root, title="Close me")
    updated = update_task_status(ws, repo_root, "task-001", "done")
    assert updated["closed_at"] is not None


def test_update_task_status_raises_for_missing_task(ws: AIWorkspace, repo_root: Path) -> None:
    with pytest.raises(FileNotFoundError):
        update_task_status(ws, repo_root, "task-999", "in_progress")


# ---------------------------------------------------------------------------
# write_verify_results
# ---------------------------------------------------------------------------

def test_write_verify_results_creates_verify_json(ws: AIWorkspace, repo_root: Path) -> None:
    create_task(ws, repo_root, title="Verify me")
    update_task_status(ws, repo_root, "task-001", "in_progress")
    record = write_verify_results(
        ws, repo_root, "task-001",
        run_id="run_test_001",
        gates={"tests": {"status": "pass", "exit_code": 0, "duration_seconds": 1.0}},
        all_passed=True,
    )
    assert record["all_passed"] is True
    assert record["run_id"] == "run_test_001"
    assert (ws.ai_dir / "tasks" / "task-001" / "verify.json").exists()


def test_write_verify_results_updates_spec(ws: AIWorkspace, repo_root: Path) -> None:
    create_task(ws, repo_root, title="Verify spec update")
    update_task_status(ws, repo_root, "task-001", "in_progress")
    write_verify_results(
        ws, repo_root, "task-001",
        run_id="run_test_002",
        gates={"tests": {"status": "pass", "exit_code": 0, "duration_seconds": 0.5}},
        all_passed=True,
    )
    spec = load_task(ws, repo_root, "task-001")
    assert spec["verify_results"] is not None
    assert spec["verify_results"]["all_passed"] is True
    assert spec["verify_results"]["run_id"] == "run_test_002"


# ---------------------------------------------------------------------------
# write_task_record
# ---------------------------------------------------------------------------

def test_write_task_record_creates_record_json(ws: AIWorkspace, repo_root: Path) -> None:
    create_task(ws, repo_root, title="Record me")
    record = write_task_record(
        ws, repo_root, "task-001",
        last_run_id="run_test_003",
        gates_passed=["tests"],
    )
    assert record["status"] == "done"
    assert record["last_run_id"] == "run_test_003"
    assert record["gates_passed"] == ["tests"]
    assert (ws.ai_dir / "tasks" / "task-001" / "record.json").exists()


# ---------------------------------------------------------------------------
# find_current_task
# ---------------------------------------------------------------------------

def test_find_current_task_returns_in_progress(ws: AIWorkspace, repo_root: Path) -> None:
    create_task(ws, repo_root, title="Active")
    update_task_status(ws, repo_root, "task-001", "in_progress")
    # Update state.json to reflect current task
    state = ws.read_state()
    state["current_task"] = "task-001"
    ws.write_state(state)

    result = find_current_task(ws, repo_root)
    assert result is not None
    assert result["task_id"] == "task-001"


def test_find_current_task_returns_none_when_none_active(ws: AIWorkspace, repo_root: Path) -> None:
    create_task(ws, repo_root, title="Not started")
    result = find_current_task(ws, repo_root)
    assert result is None


def test_find_current_task_fallback_scan(ws: AIWorkspace, repo_root: Path) -> None:
    """find_current_task should work even if state.json hint is stale."""
    create_task(ws, repo_root, title="Fallback scan")
    update_task_status(ws, repo_root, "task-001", "in_progress")
    # Don't set state.json current_task — rely on scan
    result = find_current_task(ws, repo_root)
    assert result is not None
    assert result["status"] == "in_progress"


# ---------------------------------------------------------------------------
# recount_tasks
# ---------------------------------------------------------------------------

def test_recount_tasks_returns_accurate_counts(ws: AIWorkspace, repo_root: Path) -> None:
    create_task(ws, repo_root, title="Task A")  # defined
    create_task(ws, repo_root, title="Task B")  # will be in_progress
    create_task(ws, repo_root, title="Task C")  # will be done
    create_task(ws, repo_root, title="Task D")  # will be blocked

    update_task_status(ws, repo_root, "task-002", "in_progress")
    update_task_status(ws, repo_root, "task-003", "done")
    update_task_status(ws, repo_root, "task-004", "in_progress")
    update_task_status(ws, repo_root, "task-004", "blocked")

    counts = recount_tasks(ws, repo_root)
    assert counts["total"] == 4
    assert counts["defined"] == 1
    assert counts["in_progress"] == 1
    assert counts["done"] == 1
    assert counts["blocked"] == 1
    assert counts["failed"] == 0
