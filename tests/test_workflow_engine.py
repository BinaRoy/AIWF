from __future__ import annotations

import json
from pathlib import Path

from jsonschema import validate

from aiwf.orchestrator.workflow_engine import WorkflowEngine
from aiwf.storage.ai_workspace import AIWorkspace
from aiwf.telemetry.sink import TelemetrySink


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_verify_writes_run_record_and_updates_state(tmp_path: Path) -> None:
    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()

    config_path = ws.ai_dir / "config.yaml"
    config_path.write_text('workflow_version: "0.1"\ngates:\n  smoke: "python3 -c \\"print(123)\\""\n')

    engine = WorkflowEngine(
        repo_root=tmp_path,
        ws=ws,
        telemetry=TelemetrySink(ws.ai_dir / "telemetry" / "events.jsonl"),
    )
    out = engine.verify()

    run_id = out["run_id"]
    run_record_path = ws.ai_dir / "runs" / run_id / "run.json"
    assert run_record_path.exists()

    state = ws.read_state()
    assert state["last_run_id"] == run_id
    assert state["gates"]["smoke"]["status"] == "pass"


def test_verify_artifacts_follow_json_schemas(tmp_path: Path) -> None:
    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()

    config_path = ws.ai_dir / "config.yaml"
    config_path.write_text('workflow_version: "0.1"\ngates:\n  smoke: "python3 -c \\"print(123)\\""\n')

    repo_root = Path(__file__).resolve().parents[1]
    engine = WorkflowEngine(
        repo_root=repo_root,
        ws=ws,
        telemetry=TelemetrySink(ws.ai_dir / "telemetry" / "events.jsonl"),
    )
    out = engine.verify()
    run_id = out["run_id"]

    gate_schema = _load_json(repo_root / "schemas" / "gate_result.schema.json")
    gate_report = _load_json(ws.ai_dir / "artifacts" / "reports" / "smoke.json")
    validate(gate_report, gate_schema)

    run_schema = _load_json(repo_root / "schemas" / "run_record.schema.json")
    run_record = _load_json(ws.ai_dir / "runs" / run_id / "run.json")
    validate(run_record, run_schema)
