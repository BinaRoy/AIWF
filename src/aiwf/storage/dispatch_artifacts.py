from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from aiwf.schema.json_validator import load_schema, validate_payload
from aiwf.storage.ai_workspace import AIWorkspace

WORK_ITEM_STATUSES = ("pending", "in_progress", "handoff", "review", "done", "blocked")
_ALLOWED_TRANSITIONS = {
    "pending": {"in_progress", "blocked", "handoff"},
    "in_progress": {"handoff", "review", "blocked"},
    "handoff": {"in_progress", "review", "blocked"},
    "review": {"done", "in_progress", "blocked"},
    "blocked": {"pending", "in_progress", "handoff"},
    "done": set(),
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dispatch_path(ws: AIWorkspace, run_id: str) -> Path:
    return ws.ai_dir / "runs" / run_id / "dispatch.json"


def _summary(work_items: list[Dict[str, Any]], handoffs: list[Dict[str, Any]], transitions: list[Dict[str, Any]]) -> Dict[str, int]:
    counts = {
        "total_work_items": len(work_items),
        "pending": 0,
        "in_progress": 0,
        "handoff": 0,
        "review": 0,
        "done": 0,
        "blocked": 0,
        "handoff_count": len(handoffs),
        "transition_count": len(transitions),
    }
    for item in work_items:
        status = str(item.get("status") or "")
        if status in counts:
            counts[status] += 1
    return counts


def _validate(ws: AIWorkspace, repo_root: Path, payload: Dict[str, Any]) -> Dict[str, Any]:
    validate_payload(payload, load_schema(repo_root, "dispatch_record.schema.json"))
    return payload


def _write(ws: AIWorkspace, repo_root: Path, payload: Dict[str, Any]) -> Dict[str, Any]:
    path = _dispatch_path(ws, str(payload["run_id"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    _validate(ws, repo_root, payload)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


def initialize_dispatch_record(ws: AIWorkspace, repo_root: Path, run_id: str) -> Dict[str, Any]:
    payload = {
        "run_id": run_id,
        "timestamp": _now(),
        "work_items": [],
        "handoffs": [],
        "transitions": [],
        "summary": _summary([], [], []),
    }
    return _write(ws, repo_root, payload)


def ensure_dispatch_record(ws: AIWorkspace, repo_root: Path, run_id: str) -> Dict[str, Any]:
    path = _dispatch_path(ws, run_id)
    if path.exists():
        return load_dispatch_record(ws, repo_root, run_id)
    return initialize_dispatch_record(ws, repo_root, run_id)


def load_dispatch_record(ws: AIWorkspace, repo_root: Path, run_id: str) -> Dict[str, Any]:
    path = _dispatch_path(ws, run_id)
    if not path.exists():
        raise FileNotFoundError(f"Missing dispatch record: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    return _validate(ws, repo_root, payload)


def _save_dispatch_record(ws: AIWorkspace, repo_root: Path, payload: Dict[str, Any]) -> Dict[str, Any]:
    payload["summary"] = _summary(payload["work_items"], payload["handoffs"], payload["transitions"])
    return _write(ws, repo_root, payload)


def add_work_item(
    ws: AIWorkspace,
    repo_root: Path,
    run_id: str,
    *,
    item_id: str,
    title: str,
    owner_role: str,
    acceptance_refs: list[str],
) -> Dict[str, Any]:
    payload = load_dispatch_record(ws, repo_root, run_id)
    if any(str(item.get("id")) == item_id for item in payload["work_items"]):
        raise ValueError(f"Duplicate work item id: {item_id}")
    ts = _now()
    payload["work_items"].append(
        {
            "id": item_id,
            "title": title,
            "status": "pending",
            "owner_role": owner_role,
            "created_at": ts,
            "updated_at": ts,
            "acceptance_refs": acceptance_refs,
        }
    )
    return _save_dispatch_record(ws, repo_root, payload)


def add_handoff(
    ws: AIWorkspace,
    repo_root: Path,
    run_id: str,
    *,
    work_item_id: str,
    from_role: str,
    to_role: str,
    reason: str | None = None,
    evidence_refs: list[str] | None = None,
) -> Dict[str, Any]:
    payload = load_dispatch_record(ws, repo_root, run_id)
    matched = next((item for item in payload["work_items"] if str(item.get("id")) == work_item_id), None)
    if matched is None:
        raise ValueError(f"Unknown work item id: {work_item_id}")
    matched["owner_role"] = to_role
    matched["updated_at"] = _now()
    payload["handoffs"].append(
        {
            "work_item_id": work_item_id,
            "from_role": from_role,
            "to_role": to_role,
            "reason": reason,
            "evidence_refs": list(evidence_refs or []),
            "timestamp": _now(),
        }
    )
    return _save_dispatch_record(ws, repo_root, payload)


def add_transition(
    ws: AIWorkspace,
    repo_root: Path,
    run_id: str,
    *,
    work_item_id: str,
    to_status: str,
    reason: str | None = None,
) -> Dict[str, Any]:
    if to_status not in WORK_ITEM_STATUSES:
        raise ValueError(f"Invalid work item status: {to_status}")

    payload = load_dispatch_record(ws, repo_root, run_id)
    matched = next((item for item in payload["work_items"] if str(item.get("id")) == work_item_id), None)
    if matched is None:
        raise ValueError(f"Unknown work item id: {work_item_id}")

    from_status = str(matched.get("status") or "")
    if to_status not in _ALLOWED_TRANSITIONS.get(from_status, set()):
        raise ValueError(f"Invalid transition: {from_status} -> {to_status}")

    matched["status"] = to_status
    matched["updated_at"] = _now()
    payload["transitions"].append(
        {
            "work_item_id": work_item_id,
            "from_status": from_status,
            "to_status": to_status,
            "reason": reason,
            "timestamp": _now(),
        }
    )
    return _save_dispatch_record(ws, repo_root, payload)


def has_unresolved_blocked_items(ws: AIWorkspace, repo_root: Path, run_id: str) -> bool:
    payload = load_dispatch_record(ws, repo_root, run_id)
    return any(str(item.get("status") or "") == "blocked" for item in payload["work_items"])
