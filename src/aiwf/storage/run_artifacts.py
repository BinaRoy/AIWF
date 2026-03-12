from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from aiwf.schema.json_validator import load_schema, validate_payload
from aiwf.storage.ai_workspace import AIWorkspace


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_run_id(ws: AIWorkspace, run_id: Optional[str] = None) -> str:
    if run_id:
        return str(run_id)
    state = ws.read_state()
    resolved = state.get("last_run_id")
    if not resolved:
        raise ValueError("No last_run_id in state")
    return str(resolved)


def load_run_record(ws: AIWorkspace, repo_root: Path, run_id: Optional[str] = None) -> tuple[str, Dict[str, Any]]:
    resolved_run_id = resolve_run_id(ws, run_id)
    run_path = ws.ai_dir / "runs" / resolved_run_id / "run.json"
    if not run_path.exists():
        raise FileNotFoundError(f"Missing run record: {run_path}")
    run_payload = _read_json(run_path)
    validate_payload(run_payload, load_schema(repo_root, "run_record.schema.json"))
    return resolved_run_id, run_payload


def gate_report_paths(ws: AIWorkspace, run_payload: Dict[str, Any], run_id: str) -> list[Path]:
    artifacts = run_payload.get("artifacts") or {}
    gate_report_refs = artifacts.get("gate_reports")
    if isinstance(gate_report_refs, list) and gate_report_refs:
        return [ws.root / str(ref) for ref in gate_report_refs]

    reports_dir = ws.ai_dir / "artifacts" / "reports" / run_id
    return sorted(reports_dir.glob("*.json"))


def validate_run_artifacts(
    ws: AIWorkspace,
    repo_root: Path,
    run_id: Optional[str] = None,
) -> Dict[str, Any]:
    resolved_run_id, run_payload = load_run_record(ws, repo_root, run_id)
    report_paths = gate_report_paths(ws, run_payload, resolved_run_id)
    if not report_paths:
        raise FileNotFoundError(f"No gate reports found for run {resolved_run_id}")

    gate_schema = load_schema(repo_root, "gate_result.schema.json")
    for report_path in report_paths:
        validate_payload(_read_json(report_path), gate_schema)

    artifacts = run_payload.get("artifacts") or {}
    dispatch_ref = artifacts.get("dispatch_record")
    dispatch_present = False
    if isinstance(dispatch_ref, str) and dispatch_ref:
        dispatch_path = ws.root / dispatch_ref
        if not dispatch_path.exists():
            raise FileNotFoundError(f"Missing dispatch record: {dispatch_path}")
        validate_payload(_read_json(dispatch_path), load_schema(repo_root, "dispatch_record.schema.json"))
        dispatch_present = True

    return {
        "run_id": resolved_run_id,
        "gate_reports": len(report_paths),
        "dispatch_present": dispatch_present,
        "run_payload": run_payload,
        "report_paths": report_paths,
    }
