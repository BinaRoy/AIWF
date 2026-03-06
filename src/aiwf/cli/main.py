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
stage_app = typer.Typer(add_completion=False)
app.add_typer(stage_app, name="stage")

def _repo_root() -> Path:
    return Path.cwd()


def _print_json(payload: dict) -> None:
    typer.echo(json.dumps(payload, indent=2, ensure_ascii=False))


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _error_message(exc: Exception) -> str:
    msg = str(exc).splitlines()[0].strip()
    return msg[:300]


def _allowed_stages(repo_root: Path) -> list[str]:
    schema = load_schema(repo_root, "state.schema.json") or {}
    enum = ((schema.get("properties") or {}).get("stage") or {}).get("enum")
    if isinstance(enum, list) and all(isinstance(item, str) for item in enum):
        return enum
    return ["INIT", "SPEC", "PLAN", "DEV", "VERIFY", "SHIP", "DONE", "FAILED"]


def _last_verify_success(ws: AIWorkspace, run_id: Optional[str]) -> tuple[bool, str]:
    if not run_id:
        return False, "Cannot set SHIP: missing last_run_id"
    run_path = ws.ai_dir / "runs" / str(run_id) / "run.json"
    if not run_path.exists():
        return False, f"Cannot set SHIP: missing run record for {run_id}"
    run_payload = _read_json(run_path)
    if run_payload.get("stage") != "VERIFY":
        return False, f"Cannot set SHIP: last run stage is {run_payload.get('stage')}"
    if run_payload.get("result") != "success":
        return False, f"Cannot set SHIP: last verify result is {run_payload.get('result')}"
    return True, "OK"


def _gate_counts(gates: dict) -> dict:
    counts = {"total": 0, "pass": 0, "fail": 0, "skip": 0}
    for payload in gates.values():
        if not isinstance(payload, dict):
            continue
        status = str(payload.get("status") or "").lower()
        counts["total"] += 1
        if status in ("pass", "fail", "skip"):
            counts[status] += 1
    return counts


def _latest_policy_event(telemetry_path: Path) -> Optional[dict]:
    if not telemetry_path.exists():
        return None
    latest: Optional[dict] = None
    for line in telemetry_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            evt = json.loads(line)
        except json.JSONDecodeError:
            continue
        if evt.get("type") == "policy_check":
            latest = evt
    return latest


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
        _print_json({"valid": False, "error": _error_message(exc)})
        raise typer.Exit(code=1)
    _print_json({"valid": True})


@app.command("validate-artifacts")
def validate_artifacts():
    """Validate latest run record and gate reports against JSON schemas."""
    ws = AIWorkspace(_repo_root())
    ws.ensure_layout()
    state = ws.read_state()
    run_id = state.get("last_run_id")
    if not run_id:
        _print_json({"valid": False, "error": "No last_run_id in state"})
        raise typer.Exit(code=1)

    run_schema = load_schema(_repo_root(), "run_record.schema.json")
    gate_schema = load_schema(_repo_root(), "gate_result.schema.json")

    try:
        run_path = ws.ai_dir / "runs" / str(run_id) / "run.json"
        if not run_path.exists():
            raise FileNotFoundError(f"Missing run record: {run_path}")
        run_payload = _read_json(run_path)
        validate_payload(run_payload, run_schema)

        reports_dir = ws.ai_dir / "artifacts" / "reports"
        report_paths = sorted(reports_dir.glob("*.json"))
        if not report_paths:
            raise FileNotFoundError(f"No gate reports found in {reports_dir}")

        for report_path in report_paths:
            validate_payload(_read_json(report_path), gate_schema)
    except Exception as exc:
        _print_json({"valid": False, "error": _error_message(exc), "run_id": run_id})
        raise typer.Exit(code=1)

    _print_json({"valid": True, "run_id": run_id, "gate_reports": len(report_paths)})


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


@app.command("audit-summary")
def audit_summary():
    """Show stage, latest run status, gate counts, and latest policy decision."""
    ws = AIWorkspace(_repo_root())
    ws.ensure_layout()
    state = ws.read_state()
    run_id = state.get("last_run_id")
    run_result = None
    if run_id:
        run_path = ws.ai_dir / "runs" / str(run_id) / "run.json"
        if run_path.exists():
            run_result = _read_json(run_path).get("result")

    policy_event = _latest_policy_event(ws.ai_dir / "telemetry" / "events.jsonl")
    policy_payload = (policy_event or {}).get("payload") if policy_event else {}
    policy = {
        "present": bool(policy_event),
        "allowed": policy_payload.get("allowed") if policy_event else None,
        "reason": policy_payload.get("reason") if policy_event else None,
    }

    _print_json(
        {
            "stage": state.get("stage"),
            "last_run_id": run_id,
            "last_run_result": run_result,
            "gate_counts": _gate_counts(state.get("gates") or {}),
            "policy": policy,
        }
    )


@stage_app.command("set")
def stage_set(stage: str = typer.Argument(..., help="Target stage name")):
    """Set workflow stage with transition guardrails."""
    ws = AIWorkspace(_repo_root())
    ws.ensure_layout()
    state = ws.read_state()
    current_stage = str(state.get("stage") or "")
    target_stage = stage.strip().upper()
    allowed = _allowed_stages(_repo_root())

    if target_stage not in allowed:
        _print_json(
            {
                "ok": False,
                "error": f"Invalid stage: {target_stage}",
                "allowed_stages": allowed,
                "current_stage": current_stage,
            }
        )
        raise typer.Exit(code=1)

    if target_stage == "SHIP":
        ok, reason = _last_verify_success(ws, state.get("last_run_id"))
        if not ok:
            _print_json({"ok": False, "error": reason, "current_stage": current_stage})
            raise typer.Exit(code=1)

    if target_stage == "DONE" and current_stage != "SHIP":
        _print_json(
            {
                "ok": False,
                "error": "Cannot set DONE unless current stage is SHIP",
                "current_stage": current_stage,
            }
        )
        raise typer.Exit(code=1)

    state["stage"] = target_stage
    ws.write_state(state)
    _print_json({"ok": True, "previous_stage": current_stage, "stage": target_stage})


@app.command()
def help_codex():
    """Print Codex CLI quick tips."""
    print("Install: npm i -g @openai/codex")
    print("Run: codex")
    print("Docs: https://developers.openai.com/codex/cli/")

if __name__ == "__main__":
    app()
