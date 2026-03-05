from __future__ import annotations

import json
from pathlib import Path

import typer
from rich import print

from aiwf.policy.policy_engine import PolicyEngine
from aiwf.schema.json_validator import load_schema, validate_payload
from aiwf.storage.ai_workspace import AIWorkspace
from aiwf.telemetry.sink import TelemetrySink
from aiwf.orchestrator.workflow_engine import WorkflowEngine

app = typer.Typer(add_completion=False)

def _repo_root() -> Path:
    return Path.cwd()


def _print_json(payload: dict) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False))


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
    paths: list[str] = typer.Argument(..., help="Changed paths to evaluate against policy"),
):
    """Evaluate changed paths against configured policy."""
    ws = AIWorkspace(_repo_root())
    ws.ensure_layout()
    cfg = ws.read_config()
    decision = PolicyEngine(cfg).decide(paths)
    out = {
        "allowed": decision.allowed,
        "requires_approval": decision.requires_approval,
        "requires_adr": decision.requires_adr,
        "reason": decision.reason,
        "paths": paths,
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

@app.command()
def help_codex():
    """Print Codex CLI quick tips."""
    print("Install: npm i -g @openai/codex")
    print("Run: codex")
    print("Docs: https://developers.openai.com/codex/cli/")

if __name__ == "__main__":
    app()
