from __future__ import annotations

import json
import shutil
from pathlib import Path

from aiwf.storage.ai_workspace import AIWorkspace


def _copy_schemas(repo_root: Path) -> None:
    src_schemas = Path(__file__).resolve().parents[1] / "schemas"
    shutil.copytree(src_schemas, repo_root / "schemas")


def test_build_audit_summary_reads_last_run_result_from_run_record(tmp_path: Path) -> None:
    from aiwf.runtime.state_view import build_audit_summary

    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    _copy_schemas(tmp_path)

    run_id = "run_1"
    (ws.ai_dir / "runs" / run_id).mkdir(parents=True, exist_ok=True)
    (ws.ai_dir / "runs" / run_id / "run.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "timestamp": "2026-03-10T00:00:00+00:00",
                "stage": "VERIFY",
                "run_type": "verify",
                "result": "success",
                "ok": True,
                "results": {
                    "smoke": {"status": "pass"},
                    "lint": {"status": "fail"},
                },
                "artifacts": {
                    "run_record": f".ai/runs/{run_id}/run.json",
                    "gate_reports": [],
                    "telemetry": ".ai/telemetry/events.jsonl",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    state = ws.read_state()
    state["stage"] = "DEV"
    state["last_run_id"] = run_id
    state["gates"] = {
        "smoke": {"status": "pass"},
        "lint": {"status": "fail"},
    }
    ws.write_state(state)

    out = build_audit_summary(ws, tmp_path)

    assert out["stage"] == "DEV"
    assert out["last_run_id"] == run_id
    assert out["last_run_result"] == "success"
    assert out["gate_counts"] == {"total": 2, "pass": 1, "fail": 1, "skip": 0}


def test_evaluate_stage_transition_allows_successful_verified_develop_for_ship(tmp_path: Path) -> None:
    from aiwf.runtime.state_view import evaluate_stage_transition

    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    _copy_schemas(tmp_path)

    state = ws.read_state()
    state["stage"] = "DEV"
    state["last_run_id"] = "run_1"
    ws.write_state(state)
    (ws.ai_dir / "runs" / "run_1").mkdir(parents=True, exist_ok=True)
    (ws.ai_dir / "runs" / "run_1" / "run.json").write_text(
        json.dumps(
            {
                "run_id": "run_1",
                "timestamp": "2026-03-10T00:00:00+00:00",
                "stage": "DEVELOP",
                "run_type": "develop",
                "result": "success",
                "ok": True,
                "verified": True,
                "mode": "full",
                "steps": {
                    "plan": {"ok": True},
                    "roles_sync": {"ok": True},
                    "verify": {"ok": True},
                },
                "artifacts": {
                    "run_record": ".ai/runs/run_1/run.json",
                    "develop_record": ".ai/runs/run_1/develop.json",
                    "gate_reports": [],
                    "telemetry": ".ai/telemetry/events.jsonl",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    out = evaluate_stage_transition(ws, tmp_path, current_stage="DEV", target_stage="SHIP")

    assert out["ok"] is True
    assert out["stage"] == "SHIP"


def test_evaluate_stage_transition_rejects_preflight_develop_for_ship(tmp_path: Path) -> None:
    from aiwf.runtime.state_view import evaluate_stage_transition

    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    _copy_schemas(tmp_path)

    state = ws.read_state()
    state["stage"] = "DEV"
    state["last_run_id"] = "run_1"
    ws.write_state(state)
    (ws.ai_dir / "runs" / "run_1").mkdir(parents=True, exist_ok=True)
    (ws.ai_dir / "runs" / "run_1" / "run.json").write_text(
        json.dumps(
            {
                "run_id": "run_1",
                "timestamp": "2026-03-10T00:00:00+00:00",
                "stage": "DEVELOP",
                "run_type": "develop",
                "result": "partial",
                "ok": True,
                "verified": False,
                "mode": "preflight",
                "steps": {
                    "plan": {"ok": True},
                    "roles_sync": {"ok": True},
                    "verify": {"ok": True, "skipped": True, "verified": False},
                },
                "artifacts": {
                    "run_record": ".ai/runs/run_1/run.json",
                    "develop_record": ".ai/runs/run_1/develop.json",
                    "gate_reports": [],
                    "telemetry": ".ai/telemetry/events.jsonl",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    out = evaluate_stage_transition(ws, tmp_path, current_stage="DEV", target_stage="SHIP")

    assert out["ok"] is False
    assert "verified" in out["error"]


def test_evaluate_stage_transition_allows_done_only_from_ship(tmp_path: Path) -> None:
    from aiwf.runtime.state_view import evaluate_stage_transition

    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    _copy_schemas(tmp_path)

    out = evaluate_stage_transition(ws, tmp_path, current_stage="SHIP", target_stage="DONE")

    assert out["ok"] is True
