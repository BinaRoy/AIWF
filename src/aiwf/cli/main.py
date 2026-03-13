"""AIWF CLI — task lifecycle commands."""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

import typer
from rich import print

from aiwf.gate.gate_engine import GateEngine, GateSpec
from aiwf.orchestrator.task_engine import TaskEngine, TaskStateError
from aiwf.storage.ai_workspace import AIWorkspace
from aiwf.storage.task_store import list_tasks
from aiwf.telemetry.sink import TelemetrySink

app = typer.Typer(add_completion=False, help="AIWF — AI Workflow Framework")
task_app = typer.Typer(add_completion=False, help="Task lifecycle commands")
app.add_typer(task_app, name="task")


def _repo_root() -> Path:
    return Path.cwd()


def _print_json(payload: dict) -> None:
    typer.echo(json.dumps(payload, indent=2, ensure_ascii=False))


def _error_message(exc: Exception) -> str:
    msg = str(exc).splitlines()[0].strip()
    return msg[:300]


def _make_engine(ws: AIWorkspace) -> TaskEngine:
    telemetry = TelemetrySink(ws.ai_dir / "telemetry" / "events.jsonl")
    return TaskEngine(repo_root=_repo_root(), ws=ws, telemetry=telemetry)


# ---------------------------------------------------------------------------
# aiwf init
# ---------------------------------------------------------------------------

@app.command()
def init() -> None:
    """Initialize .ai workspace layout in the current directory."""
    ws = AIWorkspace(_repo_root())
    ws.ensure_layout()
    print("[green]Initialized .ai workspace[/green]")


# ---------------------------------------------------------------------------
# aiwf status
# ---------------------------------------------------------------------------

@app.command("status")
def status_cmd() -> None:
    """Print current task status summary."""
    ws = AIWorkspace(_repo_root())
    ws.ensure_layout()
    engine = _make_engine(ws)
    _print_json(engine.get_status())


# ---------------------------------------------------------------------------
# aiwf task new
# ---------------------------------------------------------------------------

@task_app.command("new")
def task_new(
    title: str = typer.Option(..., "--title", help="Task title"),
    scope: Optional[str] = typer.Option(None, "--scope", help="Scope description"),
    acceptance: Optional[str] = typer.Option(None, "--acceptance", help="Acceptance criteria"),
    file: Optional[List[str]] = typer.Option(None, "--file", help="Affected file path(s)"),
) -> None:
    """Create a new task in 'defined' status."""
    ws = AIWorkspace(_repo_root())
    ws.ensure_layout()
    engine = _make_engine(ws)
    spec = engine.new_task(
        title,
        scope=scope,
        acceptance=acceptance,
        affected_files=list(file or []),
    )
    _print_json({"ok": True, "task_id": spec["task_id"], "status": spec["status"]})


# ---------------------------------------------------------------------------
# aiwf task start
# ---------------------------------------------------------------------------

@task_app.command("start")
def task_start(
    task_id: Optional[str] = typer.Argument(None, help="Task ID to start (default: first defined)"),
) -> None:
    """Transition a task from 'defined' to 'in_progress'."""
    ws = AIWorkspace(_repo_root())
    ws.ensure_layout()
    engine = _make_engine(ws)
    try:
        spec = engine.start_task(task_id)
    except (TaskStateError, ValueError) as exc:
        _print_json({"ok": False, "error": _error_message(exc)})
        raise typer.Exit(code=1)
    _print_json({"ok": True, "task_id": spec["task_id"], "status": spec["status"]})


# ---------------------------------------------------------------------------
# aiwf task verify
# ---------------------------------------------------------------------------

@task_app.command("verify")
def task_verify(
    task_id: Optional[str] = typer.Argument(None, help="Task ID to verify (default: current in_progress)"),
) -> None:
    """Run all gates for a task and record results."""
    ws = AIWorkspace(_repo_root())
    ws.ensure_layout()
    engine = _make_engine(ws)
    try:
        result = engine.verify_task(task_id)
    except (TaskStateError, ValueError) as exc:
        _print_json({"ok": False, "error": _error_message(exc)})
        raise typer.Exit(code=1)
    _print_json(result)
    if not result["ok"]:
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# aiwf task close
# ---------------------------------------------------------------------------

@task_app.command("close")
def task_close(
    task_id: Optional[str] = typer.Argument(None, help="Task ID to close (default: current verifying)"),
) -> None:
    """Close a task that has passed verification."""
    ws = AIWorkspace(_repo_root())
    ws.ensure_layout()
    engine = _make_engine(ws)
    try:
        record = engine.close_task(task_id)
    except TaskStateError as exc:
        _print_json({"ok": False, "error": _error_message(exc)})
        raise typer.Exit(code=1)
    _print_json({"ok": True, "task_id": record["task_id"], "status": record["status"]})


# ---------------------------------------------------------------------------
# aiwf task block
# ---------------------------------------------------------------------------

@task_app.command("block")
def task_block(
    task_id: Optional[str] = typer.Argument(None, help="Task ID to block (default: current in_progress)"),
    reason: str = typer.Option(..., "--reason", help="Reason for blocking"),
) -> None:
    """Block the current in_progress task."""
    ws = AIWorkspace(_repo_root())
    ws.ensure_layout()
    engine = _make_engine(ws)
    try:
        spec = engine.block_task(task_id, reason=reason)
    except TaskStateError as exc:
        _print_json({"ok": False, "error": _error_message(exc)})
        raise typer.Exit(code=1)
    _print_json({"ok": True, "task_id": spec["task_id"], "status": spec["status"], "reason": spec["block_reason"]})


# ---------------------------------------------------------------------------
# aiwf task unblock
# ---------------------------------------------------------------------------

@task_app.command("unblock")
def task_unblock(
    task_id: str = typer.Argument(..., help="Task ID to unblock"),
) -> None:
    """Return a blocked task to in_progress."""
    ws = AIWorkspace(_repo_root())
    ws.ensure_layout()
    engine = _make_engine(ws)
    try:
        spec = engine.unblock_task(task_id)
    except TaskStateError as exc:
        _print_json({"ok": False, "error": _error_message(exc)})
        raise typer.Exit(code=1)
    _print_json({"ok": True, "task_id": spec["task_id"], "status": spec["status"]})


# ---------------------------------------------------------------------------
# aiwf task retry
# ---------------------------------------------------------------------------

@task_app.command("retry")
def task_retry(
    task_id: Optional[str] = typer.Argument(None, help="Task ID to retry (default: most recently failed)"),
) -> None:
    """Retry a failed task, returning it to in_progress."""
    ws = AIWorkspace(_repo_root())
    ws.ensure_layout()
    engine = _make_engine(ws)
    try:
        spec = engine.retry_task(task_id)
    except (TaskStateError, ValueError) as exc:
        _print_json({"ok": False, "error": _error_message(exc)})
        raise typer.Exit(code=1)
    _print_json({"ok": True, "task_id": spec["task_id"], "status": spec["status"]})


# ---------------------------------------------------------------------------
# aiwf task current
# ---------------------------------------------------------------------------

@task_app.command("current")
def task_current() -> None:
    """Print the currently in_progress task spec."""
    ws = AIWorkspace(_repo_root())
    ws.ensure_layout()
    from aiwf.storage.task_store import find_current_task
    spec = find_current_task(ws, _repo_root())
    if spec is None:
        _print_json({"ok": False, "error": "No task is currently in_progress"})
        raise typer.Exit(code=1)
    _print_json(spec)


# ---------------------------------------------------------------------------
# aiwf task list
# ---------------------------------------------------------------------------

@task_app.command("list")
def task_list(
    status: Optional[str] = typer.Option(None, "--status", help="Filter by status"),
) -> None:
    """List all tasks."""
    ws = AIWorkspace(_repo_root())
    ws.ensure_layout()
    tasks = list_tasks(ws, _repo_root())
    if status:
        tasks = [t for t in tasks if t.get("status") == status]
    _print_json({"tasks": tasks, "count": len(tasks)})


# ---------------------------------------------------------------------------
# aiwf verify (standalone — no task context)
# ---------------------------------------------------------------------------

@app.command("verify")
def verify_standalone() -> None:
    """Run configured gates without task context (ad-hoc gate check)."""
    import datetime as _dt
    ws = AIWorkspace(_repo_root())
    ws.ensure_layout()
    cfg = ws.read_config()
    gates_cfg = cfg.get("gates") or {}
    if not gates_cfg:
        _print_json({"ok": False, "error": "No gates configured in .ai/config.yaml"})
        raise typer.Exit(code=1)

    run_id = _dt.datetime.now(_dt.timezone.utc).strftime("run_%Y%m%d_%H%M%S")
    reports_dir = ws.ai_dir / "runs" / run_id
    gate_engine = GateEngine(reports_dir=reports_dir)
    results = {}
    all_passed = True
    for name, cmd in gates_cfg.items():
        res = gate_engine.run(GateSpec(name=name, command=str(cmd)), run_id=run_id)
        results[name] = {"status": res.status, "exit_code": res.exit_code, "duration_seconds": res.duration_seconds}
        if res.status != "pass":
            all_passed = False

    out = {"ok": all_passed, "run_id": run_id, "all_passed": all_passed, "gates": results}
    _print_json(out)
    if not all_passed:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
