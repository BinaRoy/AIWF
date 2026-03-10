from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from aiwf.storage.ai_workspace import AIWorkspace


def _copy_schemas(repo_root: Path) -> None:
    src_schemas = Path(__file__).resolve().parents[1] / "schemas"
    shutil.copytree(src_schemas, repo_root / "schemas")


def test_load_roles_workflow_returns_counts_and_active_role(tmp_path: Path) -> None:
    from aiwf.runtime.roles_view import load_roles_workflow_status

    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    _copy_schemas(tmp_path)
    (ws.ai_dir / "roles_workflow.json").write_text(
        json.dumps(
            {
                "version": 1,
                "updated_at": "2026-03-10T00:00:00+00:00",
                "roles": [
                    {"name": "planner", "status": "completed", "owner": None, "notes": None, "evidence": ["a"]},
                    {"name": "implementer", "status": "in_progress", "owner": None, "notes": None, "evidence": []},
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    out = load_roles_workflow_status(ws, tmp_path)

    assert out["counts"]["completed"] == 1
    assert out["counts"]["in_progress"] == 1
    assert out["active_role"] == "implementer"


def test_update_role_entry_applies_status_owner_notes_and_deduped_evidence(tmp_path: Path) -> None:
    from aiwf.runtime.roles_view import update_role_entry

    payload = {
        "version": 1,
        "updated_at": "2026-03-10T00:00:00+00:00",
        "roles": [
            {"name": "planner", "status": "pending", "owner": None, "notes": None, "evidence": ["a"]},
        ],
    }

    out = update_role_entry(
        payload,
        role_name="planner",
        status="completed",
        evidence=["a", "b"],
        owner="alice",
        notes="done",
    )

    role = out["roles"][0]
    assert role["status"] == "completed"
    assert role["owner"] == "alice"
    assert role["notes"] == "done"
    assert role["evidence"] == ["a", "b"]


def test_update_role_entry_rejects_missing_role(tmp_path: Path) -> None:
    from aiwf.runtime.roles_view import update_role_entry

    payload = {
        "version": 1,
        "updated_at": "2026-03-10T00:00:00+00:00",
        "roles": [],
    }

    with pytest.raises(ValueError):
        update_role_entry(payload, role_name="planner", status=None, evidence=None, owner=None, notes=None)


def test_sync_roles_for_develop_run_marks_first_pending_in_progress(tmp_path: Path) -> None:
    from aiwf.runtime.roles_runtime import sync_roles_for_develop_run

    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    _copy_schemas(tmp_path)
    (ws.ai_dir / "roles_workflow.json").write_text(
        json.dumps(
            {
                "version": 1,
                "updated_at": "2026-03-10T00:00:00+00:00",
                "roles": [
                    {"name": "planner", "status": "pending", "owner": None, "notes": None, "evidence": []},
                    {"name": "implementer", "status": "pending", "owner": None, "notes": None, "evidence": []},
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    out = sync_roles_for_develop_run(ws, tmp_path, run_id="run_1")

    assert out["ok"] is True
    assert out["active_role"] == "planner"
    assert out["counts"]["in_progress"] == 1
    payload = json.loads((ws.ai_dir / "roles_workflow.json").read_text(encoding="utf-8"))
    assert payload["roles"][0]["status"] == "in_progress"


def test_sync_roles_for_develop_run_rejects_multiple_in_progress(tmp_path: Path) -> None:
    from aiwf.runtime.roles_runtime import sync_roles_for_develop_run

    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    _copy_schemas(tmp_path)
    (ws.ai_dir / "roles_workflow.json").write_text(
        json.dumps(
            {
                "version": 1,
                "updated_at": "2026-03-10T00:00:00+00:00",
                "roles": [
                    {"name": "planner", "status": "in_progress", "owner": None, "notes": None, "evidence": []},
                    {"name": "implementer", "status": "in_progress", "owner": None, "notes": None, "evidence": []},
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    out = sync_roles_for_develop_run(ws, tmp_path, run_id="run_1")

    assert out["ok"] is False
    assert "in_progress" in out["error"]


def test_apply_roles_autopilot_results_marks_completion_chain(tmp_path: Path) -> None:
    from aiwf.runtime.roles_runtime import apply_roles_autopilot_results

    payload = {
        "version": 1,
        "updated_at": "2026-03-10T00:00:00+00:00",
        "roles": [
            {"name": "planner", "status": "pending", "owner": None, "notes": None, "evidence": []},
            {"name": "implementer", "status": "pending", "owner": None, "notes": None, "evidence": []},
            {"name": "reviewer", "status": "pending", "owner": None, "notes": None, "evidence": []},
            {"name": "tester", "status": "pending", "owner": None, "notes": None, "evidence": []},
            {"name": "supervisor", "status": "pending", "owner": None, "notes": None, "evidence": []},
        ],
    }

    out = apply_roles_autopilot_results(
        payload,
        plan_ok=True,
        self_ok=True,
        loop_ok=True,
        run_id="run_1",
    )

    statuses = {role["name"]: role["status"] for role in out["roles"]}
    assert statuses == {
        "planner": "completed",
        "implementer": "completed",
        "reviewer": "completed",
        "tester": "completed",
        "supervisor": "completed",
    }
    assert out["roles"][1]["evidence"] == [".ai/runs/run_1/run.json"]
