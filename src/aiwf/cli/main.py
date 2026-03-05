from __future__ import annotations

import json
from pathlib import Path

import typer
from rich import print

from aiwf.storage.ai_workspace import AIWorkspace
from aiwf.telemetry.sink import TelemetrySink
from aiwf.orchestrator.workflow_engine import WorkflowEngine

app = typer.Typer(add_completion=False)

def _repo_root() -> Path:
    return Path.cwd()

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
    print(json.dumps(out, indent=2, ensure_ascii=False))

@app.command()
def help_codex():
    """Print Codex CLI quick tips."""
    print("Install: npm i -g @openai/codex")
    print("Run: codex")
    print("Docs: https://developers.openai.com/codex/cli/")

if __name__ == "__main__":
    app()
