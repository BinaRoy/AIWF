from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from aiwf.schema.json_validator import validate_payload


def _schema(name: str) -> dict:
    repo_root = Path(__file__).resolve().parents[1]
    return json.loads((repo_root / "schemas" / name).read_text(encoding="utf-8"))


def test_plan_schema_rejects_task_without_status() -> None:
    payload = {
        "project_id": "aiwf",
        "version": 1,
        "tasks": [{"id": "PR-CHECK"}],
    }

    with pytest.raises(Exception):
        validate_payload(payload, _schema("plan.schema.json"))


def test_state_schema_rejects_unknown_top_level_field() -> None:
    payload = {
        "workflow_version": "0.1",
        "stage": "DEV",
        "current_task": None,
        "branch": None,
        "last_run_id": "run_1",
        "last_run_type": "develop",
        "last_run_result": "success",
        "retry_count": 0,
        "gates": {},
        "plan_progress": None,
        "unexpected": True,
    }

    with pytest.raises(Exception):
        validate_payload(payload, _schema("state.schema.json"))


def test_run_record_schema_rejects_unknown_top_level_field() -> None:
    payload = {
        "run_id": "run_1",
        "timestamp": "2026-03-09T00:00:00+00:00",
        "stage": "VERIFY",
        "run_type": "verify",
        "result": "success",
        "ok": True,
        "results": {},
        "artifacts": {
            "run_record": ".ai/runs/run_1/run.json",
            "gate_reports": [".ai/artifacts/reports/run_1/smoke.json"],
            "telemetry": ".ai/telemetry/events.jsonl",
        },
        "unexpected": True,
    }

    with pytest.raises(Exception):
        validate_payload(payload, _schema("run_record.schema.json"))


def test_develop_record_schema_rejects_unknown_top_level_field() -> None:
    payload = {
        "run_id": "run_1",
        "timestamp": "2026-03-09T00:00:00+00:00",
        "mode": "full",
        "verified": True,
        "ok": True,
        "steps": {
            "plan": {"ok": True},
            "roles_sync": {"ok": True},
        "verify": {"ok": True},
    },
        "artifacts": {
            "run_record": ".ai/runs/run_1/run.json",
            "develop_record": ".ai/runs/run_1/develop.json",
            "gate_reports": [".ai/artifacts/reports/run_1/smoke.json"],
            "telemetry": ".ai/telemetry/events.jsonl",
        },
        "unexpected": True,
    }

    with pytest.raises(Exception):
        validate_payload(payload, _schema("develop_record.schema.json"))


def test_gate_result_schema_rejects_missing_environment() -> None:
    payload = {
        "run_id": "run_1",
        "name": "smoke",
        "status": "pass",
        "command": "echo ok",
        "exit_code": 0,
        "ts_start": "2026-03-09T00:00:00+00:00",
        "ts_end": "2026-03-09T00:00:01+00:00",
        "duration_seconds": 1.0,
        "evidence": {},
        "metrics": {},
    }

    with pytest.raises(Exception):
        validate_payload(payload, _schema("gate_result.schema.json"))


def test_current_contract_examples_still_validate() -> None:
    state_payload = {
        "workflow_version": "0.1",
        "stage": "DEV",
        "current_task": None,
        "branch": None,
        "last_run_id": "run_1",
        "last_run_type": "develop",
        "last_run_result": "success",
        "retry_count": 0,
        "gates": {"smoke": {"status": "pass"}},
        "plan_progress": {
            "project_id": "aiwf",
            "version": 1,
            "counts": {"total": 1, "completed": 1, "in_progress": 0, "pending": 0},
            "updated_at": "2026-03-09T00:00:00+00:00",
        },
    }
    run_payload = {
        "run_id": "run_1",
        "timestamp": "2026-03-09T00:00:00+00:00",
        "stage": "DEVELOP",
        "run_type": "develop",
        "mode": "full",
        "verified": True,
        "result": "success",
        "ok": True,
        "steps": {
            "plan": {"ok": True},
            "roles_sync": {"ok": True},
            "verify": {"ok": True, "results": {"smoke": {"status": "pass"}}},
        },
        "artifacts": {
            "run_record": ".ai/runs/run_1/run.json",
            "develop_record": ".ai/runs/run_1/develop.json",
            "gate_reports": [".ai/artifacts/reports/run_1/smoke.json"],
            "telemetry": ".ai/telemetry/events.jsonl",
        },
    }
    develop_payload = {
        "run_id": "run_1",
        "timestamp": "2026-03-09T00:00:00+00:00",
        "mode": "full",
        "verified": True,
        "ok": True,
        "steps": copy.deepcopy(run_payload["steps"]),
        "artifacts": copy.deepcopy(run_payload["artifacts"]),
    }
    gate_payload = {
        "run_id": "run_1",
        "name": "smoke",
        "status": "pass",
        "command": "echo ok",
        "exit_code": 0,
        "ts_start": "2026-03-09T00:00:00+00:00",
        "ts_end": "2026-03-09T00:00:01+00:00",
        "duration_seconds": 1.0,
        "evidence": {"stdout_tail": "ok\n", "stderr_tail": ""},
        "metrics": {},
        "environment": {"platform": "Linux", "python": "3.10.12"},
    }
    plan_payload = {
        "project_id": "aiwf",
        "version": 1,
        "tasks": [{"id": "PR-CHECK", "status": "completed"}],
    }

    validate_payload(plan_payload, _schema("plan.schema.json"))
    validate_payload(state_payload, _schema("state.schema.json"))
    validate_payload(run_payload, _schema("run_record.schema.json"))
    validate_payload(develop_payload, _schema("develop_record.schema.json"))
    validate_payload(gate_payload, _schema("gate_result.schema.json"))
