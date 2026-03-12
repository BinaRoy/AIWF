from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import typer
from rich import print

from aiwf.policy.policy_engine import PolicyEngine
from aiwf.runtime.checks import evaluate_loop_check, evaluate_self_check
from aiwf.runtime.plan_view import build_plan_progress, load_valid_plan
from aiwf.runtime.risk_view import (
    apply_risk_waiver,
    parse_risk_date,
    read_risk_register,
    risk_snapshot,
    waiver_counts,
    write_risk_register,
)
from aiwf.runtime.roles_runtime import run_roles_autopilot, sync_roles_for_develop_run
from aiwf.runtime.roles_view import (
    default_roles_workflow,
    load_roles_workflow_status,
    read_roles_workflow,
    roles_check_issues,
    roles_path,
    update_role_entry,
    write_roles_workflow,
)
from aiwf.runtime.state_view import allowed_stages, build_audit_summary, evaluate_stage_transition
from aiwf.schema.json_validator import load_schema, validate_payload
from aiwf.storage.ai_workspace import AIWorkspace
from aiwf.storage.dispatch_artifacts import (
    add_handoff,
    add_transition,
    add_work_item,
    initialize_dispatch_record,
    load_dispatch_record,
)
from aiwf.storage.run_artifacts import load_run_record, validate_run_artifacts
from aiwf.telemetry.sink import TelemetrySink
from aiwf.orchestrator.workflow_engine import ContractError, WorkflowEngine
from aiwf.vcs.pr_workflow import evaluate_pr_workflow

app = typer.Typer(add_completion=False)
stage_app = typer.Typer(add_completion=False)
plan_app = typer.Typer(add_completion=False)
risk_app = typer.Typer(add_completion=False)
roles_app = typer.Typer(add_completion=False)
dispatch_app = typer.Typer(add_completion=False)
app.add_typer(stage_app, name="stage")
app.add_typer(plan_app, name="plan")
app.add_typer(risk_app, name="risk")
app.add_typer(roles_app, name="roles")
app.add_typer(dispatch_app, name="dispatch")

def _repo_root() -> Path:
    return Path.cwd()


def _print_json(payload: dict) -> None:
    typer.echo(json.dumps(payload, indent=2, ensure_ascii=False))


def _error_message(exc: Exception) -> str:
    msg = str(exc).splitlines()[0].strip()
    return msg[:300]


def _validate_latest_artifacts(ws: AIWorkspace, repo_root: Path) -> dict:
    return validate_run_artifacts(ws, repo_root)


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
def init(
    self_hosted: bool = typer.Option(
        False,
        "--self-hosted",
        help="Write self-hosting defaults (gates + fixed loop policy).",
    ),
):
    """Initialize .ai workspace layout in current directory."""
    ws = AIWorkspace(_repo_root())
    ws.ensure_layout()
    if self_hosted:
        ws.write_self_hosted_config()
    print("[green]Initialized .ai workspace[/green]")

@app.command()
def verify():
    """Run configured gates as the low-level gate executor for the current workspace."""
    ws = AIWorkspace(_repo_root())
    ws.ensure_layout()
    telemetry = TelemetrySink(ws.ai_dir / "telemetry" / "events.jsonl")
    engine = WorkflowEngine(repo_root=_repo_root(), ws=ws, telemetry=telemetry)
    out = engine.verify()
    _print_json(out)


@app.command()
def develop(
    verify: bool = typer.Option(True, "--verify/--no-verify", help="Run verify step in this develop run."),
    sync_roles: bool = typer.Option(
        True,
        "--sync-roles/--no-sync-roles",
        help="Run role sync pre-step before verify.",
    ),
    strict_plan: bool = typer.Option(
        True,
        "--strict-plan/--no-strict-plan",
        help="Require valid .ai/plan.json for this run.",
    ),
    run_id: Optional[str] = typer.Option(None, "--run-id", help="Optional run id override."),
):
    """Run one controlled development unit and emit run-linked evidence."""
    ws = AIWorkspace(_repo_root())
    ws.ensure_layout()
    telemetry = TelemetrySink(ws.ai_dir / "telemetry" / "events.jsonl")
    engine = WorkflowEngine(repo_root=_repo_root(), ws=ws, telemetry=telemetry)
    try:
        out = engine.develop(
            run_verify=verify,
            sync_roles=sync_roles,
            strict_plan=strict_plan,
            run_id=run_id,
            roles_sync=lambda rid: sync_roles_for_develop_run(ws, _repo_root(), run_id=rid),
        )
    except ContractError as exc:
        _print_json(
            {
                "ok": False,
                "error": _error_message(exc),
                "type": "contract_error",
                "verified": False,
                "mode": "full" if verify else "preflight",
            }
        )
        raise typer.Exit(code=2)

    _print_json(out)
    if not out.get("ok"):
        raise typer.Exit(code=1)


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
    try:
        out = _validate_latest_artifacts(ws, _repo_root())
    except Exception as exc:
        _print_json({"valid": False, "error": _error_message(exc)})
        raise typer.Exit(code=1)

    _print_json({"valid": True, "run_id": out["run_id"], "gate_reports": out["gate_reports"]})


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
    summary = build_audit_summary(ws, _repo_root())
    summary["risk"] = risk_snapshot(ws, _repo_root())
    _print_json(summary)


@dispatch_app.command("init")
def dispatch_init(
    run_id: str = typer.Option(..., "--run-id", help="Run id for the dispatch record."),
):
    """Initialize a run-scoped dispatch record."""
    ws = AIWorkspace(_repo_root())
    ws.ensure_layout()
    _print_json(initialize_dispatch_record(ws, _repo_root(), run_id))


@dispatch_app.command("add-item")
def dispatch_add_item(
    run_id: str = typer.Option(..., "--run-id", help="Run id for the dispatch record."),
    id: str = typer.Option(..., "--id", help="Work item id."),
    title: str = typer.Option(..., "--title", help="Work item title."),
    owner_role: str = typer.Option(..., "--owner-role", help="Owning role."),
    acceptance_ref: Optional[list[str]] = typer.Option(None, "--acceptance-ref", help="Acceptance evidence reference."),
):
    """Append a work item to the run dispatch record."""
    ws = AIWorkspace(_repo_root())
    ws.ensure_layout()
    _print_json(
        add_work_item(
            ws,
            _repo_root(),
            run_id,
            item_id=id,
            title=title,
            owner_role=owner_role,
            acceptance_refs=list(acceptance_ref or []),
        )
    )


@dispatch_app.command("handoff")
def dispatch_handoff(
    run_id: str = typer.Option(..., "--run-id", help="Run id for the dispatch record."),
    work_item_id: str = typer.Option(..., "--work-item-id", help="Work item id."),
    from_role: str = typer.Option(..., "--from-role", help="Current owning role."),
    to_role: str = typer.Option(..., "--to-role", help="Next owning role."),
    reason: Optional[str] = typer.Option(None, "--reason", help="Handoff reason."),
    evidence_ref: Optional[list[str]] = typer.Option(None, "--evidence-ref", help="Evidence reference."),
):
    """Record a handoff for a run work item."""
    ws = AIWorkspace(_repo_root())
    ws.ensure_layout()
    _print_json(
        add_handoff(
            ws,
            _repo_root(),
            run_id,
            work_item_id=work_item_id,
            from_role=from_role,
            to_role=to_role,
            reason=reason,
            evidence_refs=list(evidence_ref or []),
        )
    )


@dispatch_app.command("transition")
def dispatch_transition(
    run_id: str = typer.Option(..., "--run-id", help="Run id for the dispatch record."),
    work_item_id: str = typer.Option(..., "--work-item-id", help="Work item id."),
    to_status: str = typer.Option(..., "--to-status", help="Next work item status."),
    reason: Optional[str] = typer.Option(None, "--reason", help="Transition reason."),
):
    """Record a state transition for a run work item."""
    ws = AIWorkspace(_repo_root())
    ws.ensure_layout()
    try:
        out = add_transition(
            ws,
            _repo_root(),
            run_id,
            work_item_id=work_item_id,
            to_status=to_status,
            reason=reason,
        )
    except ValueError as exc:
        _print_json({"ok": False, "error": _error_message(exc)})
        raise typer.Exit(code=1)
    _print_json(out)


@dispatch_app.command("status")
def dispatch_status(
    run_id: str = typer.Option(..., "--run-id", help="Run id for the dispatch record."),
):
    """Show current dispatch record for a run."""
    ws = AIWorkspace(_repo_root())
    ws.ensure_layout()
    _print_json(load_dispatch_record(ws, _repo_root(), run_id))


@app.command("self-check")
def self_check():
    """Aggregate readiness checks for AIWF self-hosted development."""
    ws = AIWorkspace(_repo_root())
    ws.ensure_layout()
    cfg = ws.read_config()
    state = ws.read_state()

    out = evaluate_self_check(_repo_root(), ws, cfg, state)
    _print_json({"ok": out["ok"], "stage": state.get("stage"), "checks": out["checks"]})
    if not out["ok"]:
        raise typer.Exit(code=1)


@app.command("loop-check")
def loop_check():
    """Machine-decidable check for fixed development loop completion."""
    ws = AIWorkspace(_repo_root())
    ws.ensure_layout()
    cfg = ws.read_config()
    state = ws.read_state()
    out = evaluate_loop_check(cfg, state, evaluate_self_check(_repo_root(), ws, cfg, state))
    if not out["checks"]["policy_enabled"]["ok"]:
        _print_json({"ok": True, "checks": out["checks"]})
        return
    _print_json({"ok": out["ok"], "checks": out["checks"]})
    if not out["ok"]:
        raise typer.Exit(code=1)


@plan_app.command("validate")
def plan_validate():
    """Validate .ai/plan.json against schemas/plan.schema.json."""
    ws = AIWorkspace(_repo_root())
    ws.ensure_layout()
    try:
        load_valid_plan(ws, _repo_root())
    except FileNotFoundError as exc:
        _print_json({"valid": False, "error": str(exc)})
        raise typer.Exit(code=1)
    except Exception as exc:
        _print_json({"valid": False, "error": _error_message(exc)})
        raise typer.Exit(code=1)
    _print_json({"valid": True})


@plan_app.command("progress")
def plan_progress():
    """Summarize task progress from .ai/plan.json and persist summary to state."""
    ws = AIWorkspace(_repo_root())
    ws.ensure_layout()
    try:
        plan = load_valid_plan(ws, _repo_root())
    except FileNotFoundError as exc:
        _print_json({"ok": False, "error": str(exc)})
        raise typer.Exit(code=1)
    except Exception as exc:
        _print_json({"ok": False, "error": _error_message(exc)})
        raise typer.Exit(code=1)

    progress = build_plan_progress(plan)
    state = ws.read_state()
    state["plan_progress"] = progress
    ws.write_state(state)
    _print_json({"ok": True, "counts": progress["counts"], "project_id": plan.get("project_id")})


@risk_app.command("status")
def risk_status():
    """Show risk registry status and waiver expiry counts."""
    ws = AIWorkspace(_repo_root())
    ws.ensure_layout()
    try:
        reg = read_risk_register(ws, _repo_root(), create=True)
    except Exception as exc:
        _print_json({"ok": False, "error": _error_message(exc)})
        raise typer.Exit(code=1)
    _print_json({"ok": True, "counts": waiver_counts(reg), "total_risks": len(reg.get("risks") or [])})


@risk_app.command("waive")
def risk_waive(
    risk_id: str = typer.Argument(..., help="Risk identifier"),
    reason: str = typer.Option(..., "--reason", help="Reason for temporary waiver"),
    expires_at: str = typer.Option(..., "--expires-at", help="Expiry date/time (ISO)"),
    approved_by: Optional[str] = typer.Option(None, "--approved-by", help="Approver identifier"),
):
    """Apply or update a temporary waiver on a risk entry."""
    ws = AIWorkspace(_repo_root())
    ws.ensure_layout()
    try:
        parse_risk_date(expires_at)
    except Exception:
        _print_json({"ok": False, "error": "Invalid --expires-at format"})
        raise typer.Exit(code=1)

    try:
        reg = read_risk_register(ws, _repo_root(), create=True)
        reg = apply_risk_waiver(
            reg,
            risk_id=risk_id,
            reason=reason,
            expires_at=expires_at,
            approved_by=approved_by,
        )
        validate_payload(reg, load_schema(_repo_root(), "risk_register.schema.json"))
    except Exception as exc:
        _print_json({"ok": False, "error": _error_message(exc)})
        raise typer.Exit(code=1)

    write_risk_register(ws, reg)
    _print_json({"ok": True, "risk_id": risk_id, "expires_at": expires_at})


@roles_app.command("init")
def roles_init():
    """Initialize default multi-role workflow contract."""
    ws = AIWorkspace(_repo_root())
    ws.ensure_layout()
    payload = default_roles_workflow()
    write_roles_workflow(ws, payload)
    _print_json({"ok": True, "path": str(roles_path(ws)), "roles": len(payload["roles"])})


@roles_app.command("status")
def roles_status():
    """Show current role workflow counts and active role."""
    ws = AIWorkspace(_repo_root())
    ws.ensure_layout()
    try:
        out = load_roles_workflow_status(ws, _repo_root())
    except Exception as exc:
        _print_json({"ok": False, "error": _error_message(exc)})
        raise typer.Exit(code=1)
    _print_json({"ok": True, "counts": out["counts"], "active_role": out["active_role"]})


@roles_app.command("check")
def roles_check():
    """Machine-check role handoff validity and evidence completeness."""
    ws = AIWorkspace(_repo_root())
    ws.ensure_layout()
    try:
        out = load_roles_workflow_status(ws, _repo_root())
    except Exception as exc:
        _print_json({"ok": False, "error": _error_message(exc)})
        raise typer.Exit(code=1)
    payload = out["payload"]
    issues = roles_check_issues(payload)
    ok = len(issues) == 0
    _print_json({"ok": ok, "issues": issues, "counts": out["counts"]})
    if not ok:
        raise typer.Exit(code=1)


@roles_app.command("update")
def roles_update(
    role_name: str = typer.Argument(..., help="Role name to update"),
    status: Optional[str] = typer.Option(
        None, "--status", help="One of: pending, in_progress, completed, blocked"
    ),
    evidence: Optional[list[str]] = typer.Option(
        None, "--evidence", help="Evidence path(s) to append", show_default=False
    ),
    owner: Optional[str] = typer.Option(None, "--owner", help="Role owner"),
    notes: Optional[str] = typer.Option(None, "--notes", help="Role notes"),
):
    """Update a role status and evidence in .ai/roles_workflow.json."""
    ws = AIWorkspace(_repo_root())
    ws.ensure_layout()
    try:
        payload = read_roles_workflow(ws, _repo_root(), create=True)
    except Exception as exc:
        _print_json({"ok": False, "error": _error_message(exc)})
        raise typer.Exit(code=1)

    valid_statuses = {"pending", "in_progress", "completed", "blocked"}
    normalized_status = status.lower().strip() if status else None
    if normalized_status and normalized_status not in valid_statuses:
        _print_json({"ok": False, "error": f"Invalid status: {status}"})
        raise typer.Exit(code=1)

    try:
        payload = update_role_entry(
            payload,
            role_name=role_name,
            status=normalized_status,
            evidence=evidence,
            owner=owner,
            notes=notes,
        )
    except ValueError as exc:
        _print_json({"ok": False, "error": str(exc)})
        raise typer.Exit(code=1)

    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    try:
        validate_payload(payload, load_schema(_repo_root(), "role_workflow.schema.json"))
    except Exception as exc:
        _print_json({"ok": False, "error": _error_message(exc)})
        raise typer.Exit(code=1)
    write_roles_workflow(ws, payload)

    target = None
    for role in payload.get("roles") or []:
        if str((role or {}).get("name")) == role_name:
            target = role
            break

    _print_json(
        {
            "ok": True,
            "role": role_name,
            "status": target.get("status"),
            "evidence_count": len(target.get("evidence") or []),
        }
    )


@roles_app.command("autopilot")
def roles_autopilot(
    run_verify: bool = typer.Option(
        False,
        "--verify",
        help="Run aiwf verify before role auto-sync; helper flow only, not the primary release gate.",
    ),
):
    """Advance role-state evidence from machine checks; not the primary closed-loop entry."""
    ws = AIWorkspace(_repo_root())
    ws.ensure_layout()
    cfg = ws.read_config()
    if run_verify:
        telemetry = TelemetrySink(ws.ai_dir / "telemetry" / "events.jsonl")
        WorkflowEngine(repo_root=_repo_root(), ws=ws, telemetry=telemetry).verify()

    try:
        out = run_roles_autopilot(ws, _repo_root(), cfg, ws.read_state())
    except Exception as exc:
        _print_json({"ok": False, "error": _error_message(exc)})
        raise typer.Exit(code=1)
    _print_json(out)
    if not out["ok"]:
        raise typer.Exit(code=1)


@stage_app.command("set")
def stage_set(stage: str = typer.Argument(..., help="Target stage name")):
    """Set workflow stage with transition guardrails."""
    ws = AIWorkspace(_repo_root())
    ws.ensure_layout()
    state = ws.read_state()
    current_stage = str(state.get("stage") or "")
    target_stage = stage.strip().upper()
    decision = evaluate_stage_transition(
        ws,
        _repo_root(),
        current_stage=current_stage,
        target_stage=target_stage,
    )
    if not decision.get("ok"):
        _print_json(decision)
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
