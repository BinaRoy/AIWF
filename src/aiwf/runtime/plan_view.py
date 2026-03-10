from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from aiwf.schema.json_validator import load_schema, validate_payload
from aiwf.storage.ai_workspace import AIWorkspace


def _plan_counts(tasks: list[dict]) -> dict:
    counts = {"total": len(tasks), "completed": 0, "in_progress": 0, "pending": 0}
    for task in tasks:
        status = str((task or {}).get("status", "")).lower()
        if status in counts:
            counts[status] += 1
    return counts


def load_valid_plan(ws: AIWorkspace, repo_root: Path) -> Dict[str, Any]:
    plan = ws.read_plan()
    if plan is None:
        raise FileNotFoundError("Missing .ai/plan.json")
    validate_payload(plan, load_schema(repo_root, "plan.schema.json"))
    return plan


def build_plan_progress(plan: Dict[str, Any], *, now_iso: str | None = None) -> Dict[str, Any]:
    tasks = plan.get("tasks") or []
    return {
        "project_id": plan.get("project_id"),
        "version": plan.get("version"),
        "counts": _plan_counts([task for task in tasks if isinstance(task, dict)]),
        "updated_at": now_iso or datetime.now(timezone.utc).isoformat(),
    }
