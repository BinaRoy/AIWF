from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from aiwf.runtime.checks import evaluate_loop_check, evaluate_self_check
from aiwf.runtime.plan_view import load_valid_plan
from aiwf.runtime.roles_view import (
    active_role_name,
    read_roles_workflow,
    roles_check_issues,
    roles_counts,
    write_roles_workflow,
)
from aiwf.schema.json_validator import load_schema, validate_payload
from aiwf.storage.ai_workspace import AIWorkspace


def apply_roles_autopilot_results(
    payload: dict,
    *,
    plan_ok: bool,
    self_ok: bool,
    loop_ok: bool,
    run_id: Optional[str],
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


def sync_roles_for_develop_run(ws: AIWorkspace, repo_root: Path, *, run_id: str) -> Dict[str, Any]:
    try:
        payload = read_roles_workflow(ws, repo_root, create=True)
    except Exception as exc:
        return {"ok": False, "error": str(exc).splitlines()[0].strip()[:300]}

    roles = payload.get("roles") or []
    in_progress = [r for r in roles if str((r or {}).get("status")) == "in_progress"]
    if len(in_progress) == 0:
        for role in roles:
            if str((role or {}).get("status")) == "pending":
                role["status"] = "in_progress"
                break
    elif len(in_progress) > 1:
        return {"ok": False, "error": "More than one role is in_progress"}

    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    try:
        validate_payload(payload, load_schema(repo_root, "role_workflow.schema.json"))
    except Exception as exc:
        return {"ok": False, "error": str(exc).splitlines()[0].strip()[:300]}
    write_roles_workflow(ws, payload)
    return {
        "ok": True,
        "active_role": active_role_name(payload),
        "counts": roles_counts(payload),
        "evidence_anchor": f".ai/runs/{run_id}/run.json",
    }


def run_roles_autopilot(ws: AIWorkspace, repo_root: Path, cfg: dict, state: dict) -> Dict[str, Any]:
    payload = read_roles_workflow(ws, repo_root, create=True)

    plan_ok = False
    try:
        load_valid_plan(ws, repo_root)
        plan_ok = True
    except FileNotFoundError:
        plan_ok = False
    except Exception:
        plan_ok = False

    self_eval = evaluate_self_check(repo_root, ws, cfg, state)
    loop_eval = evaluate_loop_check(cfg, state, self_eval)
    run_id = None
    art = self_eval["checks"].get("artifacts") or {}
    if isinstance(art, dict):
        run_id = art.get("run_id")
    payload = apply_roles_autopilot_results(
        payload,
        plan_ok=plan_ok,
        self_ok=self_eval["ok"],
        loop_ok=loop_eval["ok"],
        run_id=str(run_id) if run_id else None,
    )
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    validate_payload(payload, load_schema(repo_root, "role_workflow.schema.json"))
    write_roles_workflow(ws, payload)

    roles_ok = len(roles_check_issues(payload)) == 0
    overall_ok = plan_ok and self_eval["ok"] and loop_eval["ok"] and roles_ok
    return {
        "ok": overall_ok,
        "checks": {
            "plan": {"ok": plan_ok},
            "self": {"ok": self_eval["ok"]},
            "loop": {"ok": loop_eval["ok"]},
            "roles_contract": {"ok": roles_ok},
        },
        "roles": payload.get("roles") or [],
    }
