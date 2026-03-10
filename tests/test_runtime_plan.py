from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from aiwf.storage.ai_workspace import AIWorkspace


def _copy_schemas(repo_root: Path) -> None:
    src_schemas = Path(__file__).resolve().parents[1] / "schemas"
    shutil.copytree(src_schemas, repo_root / "schemas")


def test_load_valid_plan_reads_and_validates_plan_json(tmp_path: Path) -> None:
    from aiwf.runtime.plan_view import load_valid_plan

    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    _copy_schemas(tmp_path)
    ws.write_plan({"project_id": "aiwf", "version": 1, "tasks": [{"id": "T1", "status": "pending"}]})

    plan = load_valid_plan(ws, tmp_path)

    assert plan["project_id"] == "aiwf"
    assert plan["tasks"][0]["status"] == "pending"


def test_load_valid_plan_raises_when_plan_missing(tmp_path: Path) -> None:
    from aiwf.runtime.plan_view import load_valid_plan

    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    _copy_schemas(tmp_path)

    with pytest.raises(FileNotFoundError):
        load_valid_plan(ws, tmp_path)


def test_build_plan_progress_counts_tasks() -> None:
    from aiwf.runtime.plan_view import build_plan_progress

    out = build_plan_progress(
        {
            "project_id": "aiwf",
            "version": 1,
            "tasks": [
                {"id": "T1", "status": "completed"},
                {"id": "T2", "status": "in_progress"},
                {"id": "T3", "status": "pending"},
            ],
        },
        now_iso="2026-03-10T00:00:00+00:00",
    )

    assert out == {
        "project_id": "aiwf",
        "version": 1,
        "counts": {"total": 3, "completed": 1, "in_progress": 1, "pending": 1},
        "updated_at": "2026-03-10T00:00:00+00:00",
    }
