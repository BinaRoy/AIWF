from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Optional

import typer
from rich import print

from aiwf.policy.policy_engine import PolicyEngine
from aiwf.schema.json_validator import load_schema, validate_payload
from aiwf.storage.ai_workspace import AIWorkspace
from aiwf.telemetry.sink import TelemetrySink
from aiwf.orchestrator.workflow_engine import WorkflowEngine
from aiwf.vcs.pr_workflow import evaluate_pr_workflow

app = typer.Typer(add_completion=False)

def _repo_root() -> Path:
    return Path.cwd()


def _print_json(payload: dict) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def _git_changed_paths(repo_root: Path) -> list[str]:
    proc = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        return []

    paths: list[str] = []
    for line in proc.stdout.splitlines():
        if len(line) < 4:
            continue
        raw = line[3:]
        if " -> " in raw:
            raw = raw.split(" -> ", 1)[1]
        paths.append(raw)
    return paths


@app.command()
def init():
    """Initialize .ai workspace layout in current directory."""
    ws = AIWorkspace(_repo_root())
    ws.ensure_layout()
    print("[green]Initialized .ai workspace[/green]")

@app.command()
def verify():
    """Run configured gates and write reports to .ai/artifacts/reports."""
    ws = AIWorkspace(_repo_root())
    ws.ensure_layout()
    telemetry = TelemetrySink(ws.ai_dir / "telemetry" / "events.jsonl")
    engine = WorkflowEngine(repo_root=_repo_root(), ws=ws, telemetry=telemetry)
    out = engine.verify()
    _print_json(out)


@app.command("status")
def status_cmd():
    """Print current workflow state from .ai/state.json."""
    ws = AIWorkspace(_repo_root())
    ws.ensure_layout()
    _print_json(ws.read_state())


@app.command("policy-check")
def policy_check(
    paths: Optional[list[str]] = typer.Argument(
        None,
        help="Changed paths to evaluate against policy",
    ),
    use_git: bool = typer.Option(False, "--git", help="Use git working tree changes as input paths"),
):
    """Evaluate changed paths against configured policy."""
    ws = AIWorkspace(_repo_root())
    ws.ensure_layout()
    cfg = ws.read_config()
    input_paths: list[str] = list(paths or [])
    if use_git:
        input_paths = _git_changed_paths(_repo_root())
    if not input_paths:
        _print_json({"allowed": False, "reason": "No input paths"})
        raise typer.Exit(code=1)

    decision = PolicyEngine(cfg).decide(input_paths)
    out = {
        "allowed": decision.allowed,
        "requires_approval": decision.requires_approval,
        "requires_adr": decision.requires_adr,
        "reason": decision.reason,
        "paths": input_paths,
    }
    _print_json(out)
    if not decision.allowed:
        raise typer.Exit(code=1)


@app.command("validate-state")
def validate_state():
    """Validate .ai/state.json against schemas/state.schema.json."""
    ws = AIWorkspace(_repo_root())
    ws.ensure_layout()
    schema = load_schema(_repo_root(), "state.schema.json")
    state = ws.read_state()
    try:
        validate_payload(state, schema)
    except Exception as exc:
        _print_json({"valid": False, "error": str(exc)})
        raise typer.Exit(code=1)
    _print_json({"valid": True})


@app.command("pr-status")
def pr_status():
    """Show PR workflow readiness against git/default-branch policy."""
    ws = AIWorkspace(_repo_root())
    ws.ensure_layout()
    cfg = ws.read_config()
    _print_json(evaluate_pr_workflow(_repo_root(), cfg).to_dict())


@app.command("pr-check")
def pr_check():
    """Fail if current branch/repo is not ready for PR-based development."""
    ws = AIWorkspace(_repo_root())
    ws.ensure_layout()
    cfg = ws.read_config()
    out = evaluate_pr_workflow(_repo_root(), cfg).to_dict()
    _print_json(out)
    if not out["ok"]:
        raise typer.Exit(code=1)


@app.command()
def help_codex():
    """Print Codex CLI quick tips."""
    print("Install: npm i -g @openai/codex")
    print("Run: codex")
    print("Docs: https://developers.openai.com/codex/cli/")

if __name__ == "__main__":
    app()
