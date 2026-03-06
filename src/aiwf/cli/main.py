from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
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
plan_app = typer.Typer(add_completion=False)
risk_app = typer.Typer(add_completion=False)
roles_app = typer.Typer(add_completion=False)
app.add_typer(stage_app, name="stage")
app.add_typer(plan_app, name="plan")
app.add_typer(risk_app, name="risk")
app.add_typer(roles_app, name="roles")

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


def _validate_latest_artifacts(ws: AIWorkspace, repo_root: Path) -> dict:
    state = ws.read_state()
    run_id = state.get("last_run_id")
    if not run_id:
        raise ValueError("No last_run_id in state")

    run_schema = load_schema(repo_root, "run_record.schema.json")
    gate_schema = load_schema(repo_root, "gate_result.schema.json")
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
    return {"run_id": run_id, "gate_reports": len(report_paths), "run_payload": run_payload}


def _fixed_loop_policy(cfg: dict) -> dict:
    policy = (((cfg.get("process_policy") or {}).get("fixed_loop")) or {})
    required_gates = policy.get("required_gates")
    if not isinstance(required_gates, list):
        required_gates = ["unit_tests"]
    return {
        "enabled": bool(policy.get("enabled", True)),
        "required_stage": str(policy.get("required_stage", "VERIFY")),
        "required_gates": [str(item) for item in required_gates],
    }


def _required_gates_status(run_payload: dict, required_gates: list[str]) -> dict:
    results = run_payload.get("results") or {}
    missing: list[str] = []
    failing: list[str] = []
    for gate in required_gates:
        gate_payload = results.get(gate)
        if not isinstance(gate_payload, dict):
            missing.append(gate)
            continue
        if str(gate_payload.get("status", "")).lower() != "pass":
            failing.append(gate)
    return {"ok": not missing and not failing, "missing": missing, "failing": failing}


def _plan_counts(tasks: list[dict]) -> dict:
    counts = {"total": len(tasks), "completed": 0, "in_progress": 0, "pending": 0}
    for task in tasks:
        status = str((task or {}).get("status", "")).lower()
        if status in counts:
            counts[status] += 1
    return counts


def _risk_register_path(ws: AIWorkspace) -> Path:
    return ws.ai_dir / "risk_register.json"


def _default_risk_register() -> dict:
    return {
        "version": 1,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "risks": [],
    }


def _load_risk_register(ws: AIWorkspace, create: bool = True) -> dict:
    path = _risk_register_path(ws)
    if not path.exists():
        if not create:
            raise FileNotFoundError("Missing .ai/risk_register.json")
        reg = _default_risk_register()
        path.write_text(json.dumps(reg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return reg
    return _read_json(path)


def _validate_risk_register_or_raise(reg: dict) -> None:
    validate_payload(reg, load_schema(_repo_root(), "risk_register.schema.json"))


def _parse_date(value: str) -> datetime:
    value = value.strip()
    if len(value) == 10:
        return datetime.fromisoformat(value + "T00:00:00+00:00")
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _waiver_counts(reg: dict) -> dict:
    now = datetime.now(timezone.utc)
    active = 0
    expired = 0
    open_count = 0
    for risk in reg.get("risks") or []:
        if str(risk.get("status")) == "open":
            open_count += 1
        waiver = risk.get("waiver")
        if not isinstance(waiver, dict):
            continue
        expires_raw = str(waiver.get("expires_at") or "")
        if not expires_raw:
            continue
        try:
            expires = _parse_date(expires_raw)
        except Exception:
            continue
        if expires >= now:
            active += 1
        else:
            expired += 1
    return {"open": open_count, "active_waivers": active, "expired_waivers": expired}


def _risk_snapshot(ws: AIWorkspace) -> dict:
    path = _risk_register_path(ws)
    if not path.exists():
        return {"present": False, "counts": {"open": 0, "active_waivers": 0, "expired_waivers": 0}}
    reg = _load_risk_register(ws, create=False)
    _validate_risk_register_or_raise(reg)
    return {"present": True, "counts": _waiver_counts(reg)}


def _roles_path(ws: AIWorkspace) -> Path:
    return ws.ai_dir / "roles_workflow.json"


def _default_roles_workflow() -> dict:
    return {
        "version": 1,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "roles": [
            {"name": "planner", "status": "pending", "owner": None, "notes": None, "evidence": []},
            {"name": "implementer", "status": "pending", "owner": None, "notes": None, "evidence": []},
            {"name": "reviewer", "status": "pending", "owner": None, "notes": None, "evidence": []},
            {"name": "tester", "status": "pending", "owner": None, "notes": None, "evidence": []},
            {"name": "supervisor", "status": "pending", "owner": None, "notes": None, "evidence": []},
        ],
    }


def _load_roles_workflow(ws: AIWorkspace, create: bool = True) -> dict:
    path = _roles_path(ws)
    if not path.exists():
        if not create:
            raise FileNotFoundError("Missing .ai/roles_workflow.json")
        payload = _default_roles_workflow()
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return payload
    return _read_json(path)


def _validate_roles_workflow(payload: dict) -> None:
    validate_payload(payload, load_schema(_repo_root(), "role_workflow.schema.json"))


def _roles_counts(payload: dict) -> dict:
    roles = payload.get("roles") or []
    counts = {"total": len(roles), "completed": 0, "in_progress": 0, "pending": 0, "blocked": 0}
    for role in roles:
        status = str((role or {}).get("status", "")).lower()
        if status in counts:
            counts[status] += 1
    return counts


def _roles_check_issues(payload: dict) -> list[str]:
    issues: list[str] = []
    roles = payload.get("roles") or []
    in_progress_count = 0
    seen_incomplete = False
    for idx, role in enumerate(roles):
        status = str((role or {}).get("status", "")).lower()
        evidence = (role or {}).get("evidence") or []
        name = str((role or {}).get("name", f"role_{idx}"))
        if status == "in_progress":
            in_progress_count += 1
        if status == "completed" and not evidence:
            issues.append(f"Completed role missing evidence: {name}")
        if status != "completed":
            seen_incomplete = True
        elif seen_incomplete:
            issues.append(f"Out-of-order completion: {name}")
    if in_progress_count > 1:
        issues.append("More than one role is in_progress")
    return issues


def _run_self_check_eval(ws: AIWorkspace, cfg: dict, state: dict) -> dict:
    checks: dict[str, dict] = {}
    pr = evaluate_pr_workflow(_repo_root(), cfg).to_dict()
    checks["pr_workflow"] = {"ok": bool(pr.get("ok")), "details": pr}
    try:
        validate_payload(state, load_schema(_repo_root(), "state.schema.json"))
        checks["state_schema"] = {"ok": True}
    except Exception as exc:
        checks["state_schema"] = {"ok": False, "error": _error_message(exc)}

    run_result = None
    run_payload = None
    try:
        art = _validate_latest_artifacts(ws, _repo_root())
        run_payload = art.get("run_payload") or {}
        run_result = run_payload.get("result")
        checks["artifacts"] = {"ok": True, "run_id": art["run_id"], "gate_reports": art["gate_reports"]}
    except Exception as exc:
        checks["artifacts"] = {"ok": False, "error": _error_message(exc)}
    checks["last_run_success"] = {"ok": run_result == "success", "result": run_result}
    ok = all(bool(item.get("ok")) for item in checks.values())
    return {"ok": ok, "checks": checks, "run_payload": run_payload}


def _run_loop_check_eval(cfg: dict, state: dict, self_eval: dict) -> dict:
    checks: dict[str, dict] = {}
    policy = _fixed_loop_policy(cfg)
    checks["policy_enabled"] = {"ok": bool(policy["enabled"]), "policy": policy}
    if not policy["enabled"]:
        return {"ok": True, "checks": checks}
    checks["pr_workflow"] = self_eval["checks"].get("pr_workflow") or {"ok": False}
    checks["state_schema"] = self_eval["checks"].get("state_schema") or {"ok": False}
    checks["artifacts"] = self_eval["checks"].get("artifacts") or {"ok": False}
    checks["last_run_success"] = self_eval["checks"].get("last_run_success") or {"ok": False}
    run_payload = self_eval.get("run_payload") or {}
    required_stage = policy["required_stage"]
    checks["required_stage"] = {
        "ok": str(state.get("stage")) == required_stage,
        "current": state.get("stage"),
        "required": required_stage,
    }
    checks["required_gates"] = _required_gates_status(run_payload, policy["required_gates"])
    ok = all(bool(item.get("ok")) for item in checks.values())
    return {"ok": ok, "checks": checks}


def _sync_roles_from_checks(
    payload: dict, plan_ok: bool, self_ok: bool, loop_ok: bool, run_id: Optional[str]
) -> dict:
    roles = payload.get("roles") or []
    role_map = {str((r or {}).get("name")): r for r in roles if isinstance(r, dict)}

    planner_done = plan_ok
    implementer_done = planner_done and self_ok
    reviewer_done = implementer_done and self_ok
    tester_done = reviewer_done and loop_ok
    supervisor_done = tester_done and loop_ok
    status_targets = {
        "planner": planner_done,
        "implementer": implementer_done,
        "reviewer": reviewer_done,
        "tester": tester_done,
        "supervisor": supervisor_done,
    }
    for name in ["planner", "implementer", "reviewer", "tester", "supervisor"]:
        role = role_map.get(name)
        if not role:
            continue
        role["status"] = "completed" if status_targets[name] else "pending"
        evidence = role.get("evidence")
        if not isinstance(evidence, list):
            role["evidence"] = []
        if role["status"] == "completed" and not role["evidence"]:
            if name == "planner":
                role["evidence"] = [".ai/plan.json"]
            elif name == "implementer":
                role["evidence"] = [f".ai/runs/{run_id}/run.json"] if run_id else [".ai/runs"]
            elif name == "reviewer":
                role["evidence"] = [".ai/telemetry/events.jsonl"]
            elif name == "tester":
                role["evidence"] = [".ai/artifacts/reports"]
            elif name == "supervisor":
                role["evidence"] = [".ai/state.json"]
    if not supervisor_done:
        for name in ["planner", "implementer", "reviewer", "tester", "supervisor"]:
            role = role_map.get(name)
            if role and role.get("status") == "pending":
                role["status"] = "in_progress"
                break
    return payload


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
            "risk": _risk_snapshot(ws),
        }
    )


@app.command("self-check")
def self_check():
    """Aggregate readiness checks for AIWF self-hosted development."""
    ws = AIWorkspace(_repo_root())
    ws.ensure_layout()
    cfg = ws.read_config()
    state = ws.read_state()

    checks: dict[str, dict] = {}
    pr = evaluate_pr_workflow(_repo_root(), cfg).to_dict()
    checks["pr_workflow"] = {"ok": bool(pr.get("ok")), "details": pr}

    try:
        validate_payload(state, load_schema(_repo_root(), "state.schema.json"))
        checks["state_schema"] = {"ok": True}
    except Exception as exc:
        checks["state_schema"] = {"ok": False, "error": _error_message(exc)}

    run_result = None
    try:
        art = _validate_latest_artifacts(ws, _repo_root())
        run_result = (art.get("run_payload") or {}).get("result")
        checks["artifacts"] = {"ok": True, "run_id": art["run_id"], "gate_reports": art["gate_reports"]}
    except Exception as exc:
        checks["artifacts"] = {"ok": False, "error": _error_message(exc)}

    checks["last_run_success"] = {"ok": run_result == "success", "result": run_result}

    ok = all(bool(item.get("ok")) for item in checks.values())
    _print_json({"ok": ok, "stage": state.get("stage"), "checks": checks})
    if not ok:
        raise typer.Exit(code=1)


@app.command("loop-check")
def loop_check():
    """Machine-decidable check for fixed development loop completion."""
    ws = AIWorkspace(_repo_root())
    ws.ensure_layout()
    cfg = ws.read_config()
    state = ws.read_state()
    checks: dict[str, dict] = {}

    policy = _fixed_loop_policy(cfg)
    checks["policy_enabled"] = {"ok": bool(policy["enabled"]), "policy": policy}
    if not policy["enabled"]:
        _print_json({"ok": True, "checks": checks})
        return

    pr = evaluate_pr_workflow(_repo_root(), cfg).to_dict()
    checks["pr_workflow"] = {"ok": bool(pr.get("ok")), "details": pr}

    try:
        validate_payload(state, load_schema(_repo_root(), "state.schema.json"))
        checks["state_schema"] = {"ok": True}
    except Exception as exc:
        checks["state_schema"] = {"ok": False, "error": _error_message(exc)}

    try:
        art = _validate_latest_artifacts(ws, _repo_root())
        run_payload = art.get("run_payload") or {}
        checks["artifacts"] = {
            "ok": True,
            "run_id": art["run_id"],
            "gate_reports": art["gate_reports"],
        }
        checks["last_run_success"] = {
            "ok": run_payload.get("result") == "success",
            "result": run_payload.get("result"),
        }
        required_stage = policy["required_stage"]
        checks["required_stage"] = {
            "ok": str(state.get("stage")) == required_stage,
            "current": state.get("stage"),
            "required": required_stage,
        }
        gate_status = _required_gates_status(run_payload, policy["required_gates"])
        checks["required_gates"] = gate_status
    except Exception as exc:
        checks["artifacts"] = {"ok": False, "error": _error_message(exc)}
        checks["last_run_success"] = {"ok": False, "result": None}
        checks["required_stage"] = {"ok": False, "current": state.get("stage")}
        checks["required_gates"] = {"ok": False, "missing": policy["required_gates"], "failing": []}

    ok = all(bool(item.get("ok")) for item in checks.values())
    _print_json({"ok": ok, "checks": checks})
    if not ok:
        raise typer.Exit(code=1)


@plan_app.command("validate")
def plan_validate():
    """Validate .ai/plan.json against schemas/plan.schema.json."""
    ws = AIWorkspace(_repo_root())
    ws.ensure_layout()
    plan = ws.read_plan()
    if plan is None:
        _print_json({"valid": False, "error": "Missing .ai/plan.json"})
        raise typer.Exit(code=1)

    schema = load_schema(_repo_root(), "plan.schema.json")
    try:
        validate_payload(plan, schema)
    except Exception as exc:
        _print_json({"valid": False, "error": _error_message(exc)})
        raise typer.Exit(code=1)
    _print_json({"valid": True})


@plan_app.command("progress")
def plan_progress():
    """Summarize task progress from .ai/plan.json and persist summary to state."""
    ws = AIWorkspace(_repo_root())
    ws.ensure_layout()
    plan = ws.read_plan()
    if plan is None:
        _print_json({"ok": False, "error": "Missing .ai/plan.json"})
        raise typer.Exit(code=1)

    schema = load_schema(_repo_root(), "plan.schema.json")
    try:
        validate_payload(plan, schema)
    except Exception as exc:
        _print_json({"ok": False, "error": _error_message(exc)})
        raise typer.Exit(code=1)

    tasks = plan.get("tasks") or []
    counts = _plan_counts([task for task in tasks if isinstance(task, dict)])
    progress = {
        "project_id": plan.get("project_id"),
        "version": plan.get("version"),
        "counts": counts,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    state = ws.read_state()
    state["plan_progress"] = progress
    ws.write_state(state)
    _print_json({"ok": True, "counts": counts, "project_id": plan.get("project_id")})


@risk_app.command("status")
def risk_status():
    """Show risk registry status and waiver expiry counts."""
    ws = AIWorkspace(_repo_root())
    ws.ensure_layout()
    try:
        reg = _load_risk_register(ws, create=True)
        _validate_risk_register_or_raise(reg)
    except Exception as exc:
        _print_json({"ok": False, "error": _error_message(exc)})
        raise typer.Exit(code=1)
    _print_json({"ok": True, "counts": _waiver_counts(reg), "total_risks": len(reg.get("risks") or [])})


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
        _parse_date(expires_at)
    except Exception:
        _print_json({"ok": False, "error": "Invalid --expires-at format"})
        raise typer.Exit(code=1)

    reg = _load_risk_register(ws, create=True)
    risks = reg.get("risks") or []
    target = None
    for item in risks:
        if isinstance(item, dict) and str(item.get("id")) == risk_id:
            target = item
            break
    if target is None:
        target = {"id": risk_id, "title": f"Risk {risk_id}", "status": "open"}
        risks.append(target)
        reg["risks"] = risks

    target["waiver"] = {
        "reason": reason,
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": expires_at,
    }
    if approved_by:
        target["waiver"]["approved_by"] = approved_by
    reg["updated_at"] = datetime.now(timezone.utc).isoformat()

    try:
        _validate_risk_register_or_raise(reg)
    except Exception as exc:
        _print_json({"ok": False, "error": _error_message(exc)})
        raise typer.Exit(code=1)

    _risk_register_path(ws).write_text(json.dumps(reg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _print_json({"ok": True, "risk_id": risk_id, "expires_at": expires_at})


@roles_app.command("init")
def roles_init():
    """Initialize default multi-role workflow contract."""
    ws = AIWorkspace(_repo_root())
    ws.ensure_layout()
    payload = _default_roles_workflow()
    _roles_path(ws).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _print_json({"ok": True, "path": str(_roles_path(ws)), "roles": len(payload["roles"])})


@roles_app.command("status")
def roles_status():
    """Show current role workflow counts and active role."""
    ws = AIWorkspace(_repo_root())
    ws.ensure_layout()
    try:
        payload = _load_roles_workflow(ws, create=True)
        _validate_roles_workflow(payload)
    except Exception as exc:
        _print_json({"ok": False, "error": _error_message(exc)})
        raise typer.Exit(code=1)
    active = None
    for role in payload.get("roles") or []:
        if str((role or {}).get("status")) == "in_progress":
            active = role.get("name")
            break
    _print_json({"ok": True, "counts": _roles_counts(payload), "active_role": active})


@roles_app.command("check")
def roles_check():
    """Machine-check role handoff validity and evidence completeness."""
    ws = AIWorkspace(_repo_root())
    ws.ensure_layout()
    try:
        payload = _load_roles_workflow(ws, create=True)
        _validate_roles_workflow(payload)
    except Exception as exc:
        _print_json({"ok": False, "error": _error_message(exc)})
        raise typer.Exit(code=1)
    issues = _roles_check_issues(payload)
    ok = len(issues) == 0
    _print_json({"ok": ok, "issues": issues, "counts": _roles_counts(payload)})
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
        payload = _load_roles_workflow(ws, create=True)
        _validate_roles_workflow(payload)
    except Exception as exc:
        _print_json({"ok": False, "error": _error_message(exc)})
        raise typer.Exit(code=1)

    valid_statuses = {"pending", "in_progress", "completed", "blocked"}
    normalized_status = status.lower().strip() if status else None
    if normalized_status and normalized_status not in valid_statuses:
        _print_json({"ok": False, "error": f"Invalid status: {status}"})
        raise typer.Exit(code=1)

    target = None
    for role in payload.get("roles") or []:
        if str((role or {}).get("name")) == role_name:
            target = role
            break
    if target is None:
        _print_json({"ok": False, "error": f"Role not found: {role_name}"})
        raise typer.Exit(code=1)

    if normalized_status:
        target["status"] = normalized_status
    if owner is not None:
        target["owner"] = owner
    if notes is not None:
        target["notes"] = notes
    if evidence:
        existing = target.get("evidence") or []
        if not isinstance(existing, list):
            existing = []
        for item in evidence:
            if item not in existing:
                existing.append(item)
        target["evidence"] = existing

    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    try:
        _validate_roles_workflow(payload)
    except Exception as exc:
        _print_json({"ok": False, "error": _error_message(exc)})
        raise typer.Exit(code=1)
    _roles_path(ws).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

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
    run_verify: bool = typer.Option(False, "--verify", help="Run aiwf verify before role auto-sync"),
):
    """Automatically advance role statuses from machine checks."""
    ws = AIWorkspace(_repo_root())
    ws.ensure_layout()
    cfg = ws.read_config()
    if run_verify:
        telemetry = TelemetrySink(ws.ai_dir / "telemetry" / "events.jsonl")
        WorkflowEngine(repo_root=_repo_root(), ws=ws, telemetry=telemetry).verify()

    payload = _load_roles_workflow(ws, create=True)
    _validate_roles_workflow(payload)
    state = ws.read_state()

    plan_ok = False
    plan = ws.read_plan()
    if plan is not None:
        try:
            validate_payload(plan, load_schema(_repo_root(), "plan.schema.json"))
            plan_ok = True
        except Exception:
            plan_ok = False

    self_eval = _run_self_check_eval(ws, cfg, state)
    loop_eval = _run_loop_check_eval(cfg, state, self_eval)
    run_id = None
    art = self_eval["checks"].get("artifacts") or {}
    if isinstance(art, dict):
        run_id = art.get("run_id")
    payload = _sync_roles_from_checks(
        payload,
        plan_ok=plan_ok,
        self_ok=self_eval["ok"],
        loop_ok=loop_eval["ok"],
        run_id=str(run_id) if run_id else None,
    )
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    _validate_roles_workflow(payload)
    _roles_path(ws).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    roles_ok = len(_roles_check_issues(payload)) == 0
    overall_ok = plan_ok and self_eval["ok"] and loop_eval["ok"] and roles_ok
    _print_json(
        {
            "ok": overall_ok,
            "checks": {
                "plan": {"ok": plan_ok},
                "self": {"ok": self_eval["ok"]},
                "loop": {"ok": loop_eval["ok"]},
                "roles_contract": {"ok": roles_ok},
            },
            "roles": payload.get("roles") or [],
        }
    )
    if not overall_ok:
        raise typer.Exit(code=1)


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
