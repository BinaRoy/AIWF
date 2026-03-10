from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from aiwf.schema.json_validator import load_schema, validate_payload
from aiwf.storage.ai_workspace import AIWorkspace
from aiwf.storage.run_artifacts import validate_run_artifacts
from aiwf.vcs.pr_workflow import evaluate_pr_workflow


def _error_message(exc: Exception) -> str:
    msg = str(exc).splitlines()[0].strip()
    return msg[:300]


def fixed_loop_policy(cfg: dict) -> dict:
    policy = (((cfg.get("process_policy") or {}).get("fixed_loop")) or {})
    required_gates = policy.get("required_gates")
    if not isinstance(required_gates, list):
        required_gates = ["unit_tests"]
    return {
        "enabled": bool(policy.get("enabled", True)),
        "required_stage": str(policy.get("required_stage", "DEV")),
        "required_gates": [str(item) for item in required_gates],
    }


def required_gates_status(run_payload: dict, required_gates: list[str]) -> dict:
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


def evaluate_self_check(repo_root: Path, ws: AIWorkspace, cfg: dict, state: dict) -> Dict[str, Any]:
    checks: dict[str, dict] = {}
    pr = evaluate_pr_workflow(repo_root, cfg).to_dict()
    checks["pr_workflow"] = {"ok": bool(pr.get("ok")), "details": pr}
    try:
        validate_payload(state, load_schema(repo_root, "state.schema.json"))
        checks["state_schema"] = {"ok": True}
    except Exception as exc:
        checks["state_schema"] = {"ok": False, "error": _error_message(exc)}

    run_result = None
    run_payload = None
    try:
        art = validate_run_artifacts(ws, repo_root)
        run_payload = art.get("run_payload") or {}
        run_result = run_payload.get("result")
        checks["artifacts"] = {"ok": True, "run_id": art["run_id"], "gate_reports": art["gate_reports"]}
    except Exception as exc:
        checks["artifacts"] = {"ok": False, "error": _error_message(exc)}
    checks["last_run_success"] = {"ok": run_result == "success", "result": run_result}
    ok = all(bool(item.get("ok")) for item in checks.values())
    return {"ok": ok, "checks": checks, "run_payload": run_payload}


def evaluate_loop_check(cfg: dict, state: dict, self_eval: dict) -> Dict[str, Any]:
    checks: dict[str, dict] = {}
    policy = fixed_loop_policy(cfg)
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
    checks["required_gates"] = required_gates_status(run_payload, policy["required_gates"])
    ok = all(bool(item.get("ok")) for item in checks.values())
    return {"ok": ok, "checks": checks}
