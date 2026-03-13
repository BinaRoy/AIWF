"""End-to-end CLI tests for all aiwf task-lifecycle commands."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from aiwf.cli.main import app
from aiwf.storage.ai_workspace import AIWorkspace

runner = CliRunner()


def _pass_gate_cmd() -> str:
    return f"{sys.executable} -c 'import sys; sys.exit(0)'"


def _fail_gate_cmd() -> str:
    return f"{sys.executable} -c 'import sys; sys.exit(1)'"


def _write_gates(tmp_path: Path, gates: dict) -> None:
    (tmp_path / ".ai" / "config.yaml").write_text(yaml.dump({"gates": gates}), encoding="utf-8")


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------

def test_init_creates_ai_directory(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0
    out = json.loads(result.output)
    assert out == {
        "ok": True,
        "workspace": ".ai",
        "config": ".ai/config.yaml",
        "state": ".ai/state.json",
    }
    assert (tmp_path / ".ai").is_dir()
    assert (tmp_path / ".ai" / "state.json").exists()
    assert (tmp_path / ".ai" / "config.yaml").exists()


def test_init_idempotent(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])
    original_config = (tmp_path / ".ai" / "config.yaml").read_text()
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0
    assert (tmp_path / ".ai" / "config.yaml").read_text() == original_config


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------

def test_status_empty_workspace(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    out = json.loads(result.output)
    assert out["current_task"] is None
    assert out["tasks"]["total"] == 0


# ---------------------------------------------------------------------------
# task new
# ---------------------------------------------------------------------------

def test_task_new_creates_spec(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])
    result = runner.invoke(
        app,
        [
            "task",
            "new",
            "Test task",
            "--scope",
            "x",
            "--accept",
            "works",
            "--files",
            "src/a.py,tests/test_a.py",
        ],
    )
    assert result.exit_code == 0
    out = json.loads(result.output)
    assert out["ok"] is True
    assert out["task_id"] == "task-001"
    assert out["spec"] == ".ai/tasks/task-001/spec.json"
    assert (tmp_path / ".ai" / "tasks" / "task-001" / "spec.json").exists()
    spec = json.loads((tmp_path / ".ai" / "tasks" / "task-001" / "spec.json").read_text(encoding="utf-8"))
    assert spec["acceptance"] == "works"
    assert spec["affected_files"] == ["src/a.py", "tests/test_a.py"]


# ---------------------------------------------------------------------------
# task start
# ---------------------------------------------------------------------------

def test_task_start_transitions_status(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])
    runner.invoke(app, ["task", "new", "Task A"])
    result = runner.invoke(app, ["task", "start"])
    assert result.exit_code == 0
    out = json.loads(result.output)
    assert out["ok"] is True
    assert out["status"] == "in_progress"


def test_task_start_fails_when_none_defined(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])
    result = runner.invoke(app, ["task", "start"])
    assert result.exit_code == 2
    out = json.loads(result.output)
    assert out["ok"] is False


# ---------------------------------------------------------------------------
# task current
# ---------------------------------------------------------------------------

def test_task_current_shows_active_task(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])
    runner.invoke(app, ["task", "new", "Active task"])
    runner.invoke(app, ["task", "start"])
    result = runner.invoke(app, ["task", "current"])
    assert result.exit_code == 0
    out = json.loads(result.output)
    assert out["task_id"] == "task-001"
    assert out["status"] == "in_progress"


def test_task_current_fails_when_none_active(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])
    result = runner.invoke(app, ["task", "current"])
    assert result.exit_code == 2
    out = json.loads(result.output)
    assert out["ok"] is False


# ---------------------------------------------------------------------------
# task list
# ---------------------------------------------------------------------------

def test_task_list_shows_all_tasks(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])
    runner.invoke(app, ["task", "new", "Task 1"])
    runner.invoke(app, ["task", "new", "Task 2"])
    result = runner.invoke(app, ["task", "list"])
    assert result.exit_code == 0
    out = json.loads(result.output)
    assert out["count"] == 2


# ---------------------------------------------------------------------------
# task verify
# ---------------------------------------------------------------------------

def test_task_verify_passes_with_echo_gate(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])
    _write_gates(tmp_path, {"pass_gate": _pass_gate_cmd()})
    runner.invoke(app, ["task", "new", "Verify me"])
    runner.invoke(app, ["task", "start"])
    result = runner.invoke(app, ["task", "verify"])
    assert result.exit_code == 0
    out = json.loads(result.output)
    assert out["all_passed"] is True


def test_task_verify_fails_with_failing_gate(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])
    _write_gates(tmp_path, {"fail_gate": _fail_gate_cmd()})
    runner.invoke(app, ["task", "new", "Will fail"])
    runner.invoke(app, ["task", "start"])
    result = runner.invoke(app, ["task", "verify"])
    assert result.exit_code == 1
    out = json.loads(result.output)
    assert out["all_passed"] is False


# ---------------------------------------------------------------------------
# task close
# ---------------------------------------------------------------------------

def test_task_close_after_verify(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])
    _write_gates(tmp_path, {"pass_gate": _pass_gate_cmd()})
    runner.invoke(app, ["task", "new", "Full flow"])
    runner.invoke(app, ["task", "start"])
    runner.invoke(app, ["task", "verify"])
    result = runner.invoke(app, ["task", "close"])
    assert result.exit_code == 0
    out = json.loads(result.output)
    assert out["ok"] is True
    assert out["status"] == "done"


def test_task_close_rejects_without_verify(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])
    runner.invoke(app, ["task", "new", "No verify"])
    runner.invoke(app, ["task", "start"])
    result = runner.invoke(app, ["task", "close"])
    assert result.exit_code == 2
    out = json.loads(result.output)
    assert out["ok"] is False


# ---------------------------------------------------------------------------
# task block / unblock
# ---------------------------------------------------------------------------

def test_task_block_and_unblock(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])
    runner.invoke(app, ["task", "new", "Block me"])
    runner.invoke(app, ["task", "start"])

    # Block
    result = runner.invoke(app, ["task", "block", "--reason", "Waiting on API"])
    assert result.exit_code == 0
    out = json.loads(result.output)
    assert out["status"] == "blocked"

    # Unblock
    result = runner.invoke(app, ["task", "unblock", "task-001"])
    assert result.exit_code == 0
    out = json.loads(result.output)
    assert out["status"] == "in_progress"


# ---------------------------------------------------------------------------
# verify (standalone)
# ---------------------------------------------------------------------------

def test_verify_standalone_runs_gates(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])
    _write_gates(tmp_path, {"pass_gate": _pass_gate_cmd()})
    result = runner.invoke(app, ["verify"])
    assert result.exit_code == 0
    out = json.loads(result.output)
    assert out["all_passed"] is True
    assert "pass_gate" in out["gates"]
    run_id = out["run_id"]
    run_path = tmp_path / ".ai" / "runs" / run_id / "run.json"
    assert run_path.exists()
    run_record = json.loads(run_path.read_text(encoding="utf-8"))
    assert run_record["run_id"] == run_id
    assert run_record["task_id"] is None
    assert run_record["ok"] is True
    assert run_record["result"] == "pass"
    assert "pass_gate" in run_record["gates"]


def test_verify_standalone_fails_no_gates(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])
    result = runner.invoke(app, ["verify"])
    assert result.exit_code == 2
    out = json.loads(result.output)
    assert out["ok"] is False


# ---------------------------------------------------------------------------
# full lifecycle
# ---------------------------------------------------------------------------

def test_full_cli_lifecycle(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])
    _write_gates(tmp_path, {"pass_gate": _pass_gate_cmd()})

    runner.invoke(app, ["task", "new", "Lifecycle task"])
    runner.invoke(app, ["task", "start"])
    runner.invoke(app, ["task", "verify"])
    runner.invoke(app, ["task", "close"])

    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    out = json.loads(result.output)
    assert out["tasks"]["done"] == 1
    assert out["tasks"]["total"] == 1
