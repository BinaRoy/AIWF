from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from aiwf.schema.json_validator import load_schema, validate_payload
from aiwf.storage.ai_workspace import AIWorkspace


def roles_path(ws: AIWorkspace) -> Path:
    return ws.ai_dir / "roles_workflow.json"


def default_roles_workflow() -> dict:
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


def read_roles_workflow(ws: AIWorkspace, repo_root: Path, *, create: bool = True) -> Dict[str, Any]:
    path = roles_path(ws)
    if not path.exists():
        if not create:
            raise FileNotFoundError("Missing .ai/roles_workflow.json")
        payload = default_roles_workflow()
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return payload
    payload = json.loads(path.read_text(encoding="utf-8"))
    validate_payload(payload, load_schema(repo_root, "role_workflow.schema.json"))
    return payload


def write_roles_workflow(ws: AIWorkspace, payload: Dict[str, Any]) -> None:
    roles_path(ws).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def roles_counts(payload: dict) -> dict:
    roles = payload.get("roles") or []
    counts = {"total": len(roles), "completed": 0, "in_progress": 0, "pending": 0, "blocked": 0}
    for role in roles:
        status = str((role or {}).get("status", "")).lower()
        if status in counts:
            counts[status] += 1
    return counts


def roles_check_issues(payload: dict) -> list[str]:
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


def active_role_name(payload: dict) -> Optional[str]:
    for role in payload.get("roles") or []:
        if str((role or {}).get("status")) == "in_progress":
            return role.get("name")
    return None


def load_roles_workflow_status(ws: AIWorkspace, repo_root: Path) -> Dict[str, Any]:
    payload = read_roles_workflow(ws, repo_root, create=True)
    return {"payload": payload, "counts": roles_counts(payload), "active_role": active_role_name(payload)}


def update_role_entry(
    payload: Dict[str, Any],
    *,
    role_name: str,
    status: Optional[str],
    evidence: Optional[list[str]],
    owner: Optional[str],
    notes: Optional[str],
) -> Dict[str, Any]:
    target = None
    for role in payload.get("roles") or []:
        if str((role or {}).get("name")) == role_name:
            target = role
            break
    if target is None:
        raise ValueError(f"Role not found: {role_name}")

    if status:
        target["status"] = status
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
    return payload
