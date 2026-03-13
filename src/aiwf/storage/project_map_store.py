"""Project map storage and summary helpers."""

from __future__ import annotations

from typing import Any, Dict

from aiwf.schema.json_validator import load_schema, validate_payload
from aiwf.storage.ai_workspace import AIWorkspace
from aiwf.storage.task_store import load_task


def _map_path(ws: AIWorkspace):
    return ws.ai_dir / "project_map.json"


def _read_json(path):
    import json

    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path, data: Dict[str, Any]) -> None:
    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def init_project_map(ws: AIWorkspace, repo_root) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"version": "0.1", "modules": []}
    validate_payload(payload, load_schema(repo_root, "project_map.schema.json"))
    _write_json(_map_path(ws), payload)
    return payload


def load_project_map(ws: AIWorkspace, repo_root) -> Dict[str, Any]:
    path = _map_path(ws)
    if not path.exists():
        raise FileNotFoundError("Project map not initialized")
    payload = _read_json(path)
    validate_payload(payload, load_schema(repo_root, "project_map.schema.json"))
    return payload


def add_module(
    ws: AIWorkspace,
    repo_root,
    *,
    module_id: str,
    title: str,
    description: str | None = None,
) -> Dict[str, Any]:
    payload = load_project_map(ws, repo_root)
    if any(module["module_id"] == module_id for module in payload["modules"]):
        raise ValueError(f"Module already exists: {module_id}")
    module = {
        "module_id": module_id,
        "title": title,
        "description": description,
        "task_ids": [],
    }
    payload["modules"].append(module)
    validate_payload(payload, load_schema(repo_root, "project_map.schema.json"))
    _write_json(_map_path(ws), payload)
    return module


def link_task(ws: AIWorkspace, repo_root, *, module_id: str, task_id: str) -> Dict[str, Any]:
    payload = load_project_map(ws, repo_root)
    load_task(ws, repo_root, task_id)
    for module in payload["modules"]:
        if module["module_id"] != module_id:
            continue
        if task_id not in module["task_ids"]:
            module["task_ids"].append(task_id)
        validate_payload(payload, load_schema(repo_root, "project_map.schema.json"))
        _write_json(_map_path(ws), payload)
        return module
    raise ValueError(f"Module not found: {module_id}")


def summarize_project_map(ws: AIWorkspace, repo_root) -> Dict[str, Any]:
    payload = load_project_map(ws, repo_root)
    modules = []
    for module in payload["modules"]:
        counts = {
            "total": len(module["task_ids"]),
            "defined": 0,
            "in_progress": 0,
            "done": 0,
            "failed": 0,
            "blocked": 0,
        }
        for task_id in module["task_ids"]:
            spec = load_task(ws, repo_root, task_id)
            status = spec["status"]
            counts[status] += 1
        modules.append(
            {
                "module_id": module["module_id"],
                "title": module["title"],
                "description": module["description"],
                "task_ids": list(module["task_ids"]),
                "task_counts": counts,
                "completion": {"done": counts["done"], "total": counts["total"]},
            }
        )
    return {"modules": modules, "count": len(modules)}
