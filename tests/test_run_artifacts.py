from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from aiwf.storage.ai_workspace import AIWorkspace


def _copy_schemas(repo_root: Path) -> None:
    src_schemas = Path(__file__).resolve().parents[1] / "schemas"
    shutil.copytree(src_schemas, repo_root / "schemas")


def test_validate_run_artifacts_uses_last_run_id_scoped_reports(tmp_path: Path) -> None:
    from aiwf.storage.run_artifacts import validate_run_artifacts

    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    _copy_schemas(tmp_path)

    run_id = "run_valid"
    other_run_id = "run_other"
    for current in [run_id, other_run_id]:
        (ws.ai_dir / "runs" / current).mkdir(parents=True, exist_ok=True)

    (ws.ai_dir / "runs" / run_id / "run.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "timestamp": "2026-03-09T00:00:00+00:00",
                "stage": "VERIFY",
                "run_type": "verify",
                "result": "success",
                "ok": True,
                "results": {"smoke": {"status": "pass"}},
                "artifacts": {
                    "run_record": f".ai/runs/{run_id}/run.json",
                    "gate_reports": [f".ai/artifacts/reports/{run_id}/smoke.json"],
                    "telemetry": ".ai/telemetry/events.jsonl",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (ws.ai_dir / "runs" / other_run_id / "run.json").write_text(
        json.dumps(
            {
                "run_id": other_run_id,
                "timestamp": "2026-03-08T00:00:00+00:00",
                "stage": "VERIFY",
                "run_type": "verify",
                "result": "failure",
                "ok": False,
                "results": {},
                "artifacts": {
                    "run_record": f".ai/runs/{other_run_id}/run.json",
                    "gate_reports": [f".ai/artifacts/reports/{other_run_id}/smoke.json"],
                    "telemetry": ".ai/telemetry/events.jsonl",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    (ws.ai_dir / "artifacts" / "reports" / run_id).mkdir(parents=True, exist_ok=True)
    (ws.ai_dir / "artifacts" / "reports" / run_id / "smoke.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "name": "smoke",
                "status": "pass",
                "command": "echo ok",
                "exit_code": 0,
                "ts_start": "2026-03-09T00:00:00+00:00",
                "ts_end": "2026-03-09T00:00:01+00:00",
                "duration_seconds": 1.0,
                "evidence": {},
                "metrics": {},
                "environment": {},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (ws.ai_dir / "artifacts" / "reports" / other_run_id).mkdir(parents=True, exist_ok=True)
    (ws.ai_dir / "artifacts" / "reports" / other_run_id / "smoke.json").write_text("{}\n", encoding="utf-8")

    state = ws.read_state()
    state["last_run_id"] = run_id
    ws.write_state(state)

    out = validate_run_artifacts(ws, tmp_path)

    assert out["run_id"] == run_id
    assert out["gate_reports"] == 1
    assert out["run_payload"]["run_id"] == run_id


def test_validate_run_artifacts_fails_without_last_run_id(tmp_path: Path) -> None:
    from aiwf.storage.run_artifacts import validate_run_artifacts

    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    _copy_schemas(tmp_path)

    with pytest.raises(ValueError):
        validate_run_artifacts(ws, tmp_path)
