from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from aiwf.schema.json_validator import load_schema
from aiwf.storage.ai_workspace import AIWorkspace
from aiwf.storage.dispatch_artifacts import load_dispatch_record
from aiwf.storage.run_artifacts import load_run_record


def allowed_stages(repo_root: Path) -> list[str]:
    schema = load_schema(repo_root, "state.schema.json") or {}
    enum = ((schema.get("properties") or {}).get("stage") or {}).get("enum")
    if isinstance(enum, list) and all(isinstance(item, str) for item in enum):
        return enum
    return ["INIT", "SPEC", "PLAN", "DEV", "VERIFY", "SHIP", "DONE", "FAILED"]


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


def _latest_policy_event(telemetry_path: Path, run_id: Optional[str] = None) -> Optional[dict]:
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
        if evt.get("type") != "policy_check":
            continue
        if run_id is not None and str(evt.get("run_id") or "") != run_id:
            continue
        if run_id is not None and str((evt.get("payload") or {}).get("run_id") or "") not in ("", run_id):
            continue
        if evt.get("type") == "policy_check":
            latest = evt
    return latest


def build_audit_summary(ws: AIWorkspace, repo_root: Path) -> Dict[str, Any]:
    state = ws.read_state()
    run_id = state.get("last_run_id")
    run_result = None
    dispatch = {"present": False, "summary": None}
    if run_id:
        try:
            _, run_payload = load_run_record(ws, repo_root, str(run_id))
            run_result = run_payload.get("result")
            artifacts = run_payload.get("artifacts") or {}
            if artifacts.get("dispatch_record"):
                try:
                    dispatch_payload = load_dispatch_record(ws, repo_root, str(run_id))
                    dispatch = {
                        "present": True,
                        "summary": dispatch_payload.get("summary"),
                    }
                except FileNotFoundError:
                    dispatch = {"present": False, "summary": None}
        except FileNotFoundError:
            run_result = None

    policy_event = _latest_policy_event(ws.ai_dir / "telemetry" / "events.jsonl", str(run_id) if run_id else None)
    policy_payload = (policy_event or {}).get("payload") if policy_event else {}
    policy = {
        "present": bool(policy_event),
        "allowed": policy_payload.get("allowed") if policy_event else None,
        "reason": policy_payload.get("reason") if policy_event else None,
    }
    return {
        "stage": state.get("stage"),
        "last_run_id": run_id,
        "last_run_result": run_result,
        "gate_counts": _gate_counts(state.get("gates") or {}),
        "dispatch": dispatch,
        "policy": policy,
    }


def evaluate_stage_transition(
    ws: AIWorkspace,
    repo_root: Path,
    *,
    current_stage: str,
    target_stage: str,
) -> Dict[str, Any]:
    allowed = allowed_stages(repo_root)
    if target_stage not in allowed:
        return {
            "ok": False,
            "error": f"Invalid stage: {target_stage}",
            "allowed_stages": allowed,
            "current_stage": current_stage,
        }

    state = ws.read_state()
    run_id = state.get("last_run_id")
    if target_stage == "SHIP":
        if not run_id:
            return {"ok": False, "error": "Cannot set SHIP: missing last_run_id", "current_stage": current_stage}
        try:
            _, run_payload = load_run_record(ws, repo_root, str(run_id))
        except FileNotFoundError:
            return {
                "ok": False,
                "error": f"Cannot set SHIP: missing run record for {run_id}",
                "current_stage": current_stage,
            }
        run_type = str(run_payload.get("run_type") or "").lower()
        run_stage = str(run_payload.get("stage") or "")
        run_result = run_payload.get("result")
        if run_type == "verify":
            if run_result != "success":
                return {
                    "ok": False,
                    "error": f"Cannot set SHIP: last run result is {run_result}",
                    "current_stage": current_stage,
                }
            if run_stage != "VERIFY":
                return {
                    "ok": False,
                    "error": f"Cannot set SHIP: last verify stage is {run_stage}",
                    "current_stage": current_stage,
                }
        elif run_type == "develop":
            if not bool(run_payload.get("verified")):
                return {
                    "ok": False,
                    "error": "Cannot set SHIP: last develop run is not verified",
                    "current_stage": current_stage,
                }
            if run_result != "success":
                return {
                    "ok": False,
                    "error": f"Cannot set SHIP: last run result is {run_result}",
                    "current_stage": current_stage,
                }
        else:
            return {
                "ok": False,
                "error": f"Cannot set SHIP: unsupported last run type {run_type or 'unknown'}",
                "current_stage": current_stage,
            }

    if target_stage == "DONE" and current_stage != "SHIP":
        return {
            "ok": False,
            "error": "Cannot set DONE unless current stage is SHIP",
            "current_stage": current_stage,
        }

    return {"ok": True, "stage": target_stage, "previous_stage": current_stage}
