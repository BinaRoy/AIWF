from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from aiwf.schema.json_validator import load_schema, validate_payload
from aiwf.storage.ai_workspace import AIWorkspace


def risk_register_path(ws: AIWorkspace) -> Path:
    return ws.ai_dir / "risk_register.json"


def default_risk_register(*, now: Optional[datetime] = None) -> dict:
    now = now or datetime.now(timezone.utc)
    return {
        "version": 1,
        "updated_at": now.isoformat(),
        "risks": [],
    }


def parse_risk_date(value: str) -> datetime:
    value = value.strip()
    if len(value) == 10:
        return datetime.fromisoformat(value + "T00:00:00+00:00")
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def read_risk_register(ws: AIWorkspace, repo_root: Path, *, create: bool = True) -> Dict[str, Any]:
    path = risk_register_path(ws)
    if not path.exists():
        if not create:
            raise FileNotFoundError("Missing .ai/risk_register.json")
        payload = default_risk_register()
        write_risk_register(ws, payload)
        return payload
    payload = json.loads(path.read_text(encoding="utf-8"))
    validate_payload(payload, load_schema(repo_root, "risk_register.schema.json"))
    return payload


def write_risk_register(ws: AIWorkspace, payload: Dict[str, Any]) -> None:
    risk_register_path(ws).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def waiver_counts(reg: dict, *, now: Optional[datetime] = None) -> dict:
    now = now or datetime.now(timezone.utc)
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
            expires = parse_risk_date(expires_raw)
        except Exception:
            continue
        if expires >= now:
            active += 1
        else:
            expired += 1
    return {"open": open_count, "active_waivers": active, "expired_waivers": expired}


def risk_snapshot(ws: AIWorkspace, repo_root: Path) -> dict:
    path = risk_register_path(ws)
    if not path.exists():
        return {"present": False, "counts": {"open": 0, "active_waivers": 0, "expired_waivers": 0}}
    reg = read_risk_register(ws, repo_root, create=False)
    return {"present": True, "counts": waiver_counts(reg)}


def apply_risk_waiver(
    payload: Dict[str, Any],
    *,
    risk_id: str,
    reason: str,
    expires_at: str,
    approved_by: Optional[str] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    parse_risk_date(expires_at)

    risks = payload.get("risks") or []
    target = None
    for item in risks:
        if isinstance(item, dict) and str(item.get("id")) == risk_id:
            target = item
            break
    if target is None:
        target = {"id": risk_id, "title": f"Risk {risk_id}", "status": "open"}
        risks.append(target)
        payload["risks"] = risks

    target["waiver"] = {
        "reason": reason,
        "issued_at": now.isoformat(),
        "expires_at": expires_at,
    }
    if approved_by:
        target["waiver"]["approved_by"] = approved_by
    payload["updated_at"] = now.isoformat()
    return payload
