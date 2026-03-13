from __future__ import annotations

import json
from pathlib import Path

import pytest

from aiwf.schema.json_validator import validate_payload


def _schema(name: str) -> dict:
    repo_root = Path(__file__).resolve().parents[1]
    return json.loads((repo_root / "schemas" / name).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# task_spec.schema.json
# ---------------------------------------------------------------------------

def _valid_spec() -> dict:
    return {
        "task_id": "task-001",
        "title": "Implement login",
        "status": "defined",
        "created_at": "2026-03-12T10:00:00Z",
        "updated_at": "2026-03-12T10:00:00Z",
        "scope": "Add /login endpoint",
        "acceptance": "POST /login returns 200",
        "affected_files": ["src/auth.py"],
        "verify_results": None,
        "block_reason": None,
        "closed_at": None,
    }


def test_task_spec_schema_accepts_valid_spec() -> None:
    validate_payload(_valid_spec(), _schema("task_spec.schema.json"))


def test_task_spec_schema_rejects_missing_title() -> None:
    p = _valid_spec()
    del p["title"]
    with pytest.raises(Exception):
        validate_payload(p, _schema("task_spec.schema.json"))


def test_task_spec_schema_rejects_invalid_status() -> None:
    p = _valid_spec()
    p["status"] = "unknown"
    with pytest.raises(Exception):
        validate_payload(p, _schema("task_spec.schema.json"))


def test_task_spec_schema_allows_null_optional_fields() -> None:
    p = _valid_spec()
    p["scope"] = None
    p["acceptance"] = None
    p["affected_files"] = []
    validate_payload(p, _schema("task_spec.schema.json"))


def test_task_spec_schema_rejects_unknown_field() -> None:
    p = _valid_spec()
    p["unexpected"] = True
    with pytest.raises(Exception):
        validate_payload(p, _schema("task_spec.schema.json"))


# ---------------------------------------------------------------------------
# task_record.schema.json
# ---------------------------------------------------------------------------

def _valid_record() -> dict:
    return {
        "task_id": "task-001",
        "title": "Implement login",
        "status": "done",
        "closed_at": "2026-03-12T11:00:00Z",
        "last_run_id": "run_20260312_110000",
        "gates_passed": ["tests", "lint"],
    }


def test_task_record_schema_accepts_valid_record() -> None:
    validate_payload(_valid_record(), _schema("task_record.schema.json"))


def test_task_record_schema_rejects_non_done_status() -> None:
    p = _valid_record()
    p["status"] = "in_progress"
    with pytest.raises(Exception):
        validate_payload(p, _schema("task_record.schema.json"))


def test_task_record_schema_rejects_missing_task_id() -> None:
    p = _valid_record()
    del p["task_id"]
    with pytest.raises(Exception):
        validate_payload(p, _schema("task_record.schema.json"))


# ---------------------------------------------------------------------------
# task_verify.schema.json
# ---------------------------------------------------------------------------

def _valid_verify() -> dict:
    return {
        "task_id": "task-001",
        "run_id": "run_20260312_110000",
        "timestamp": "2026-03-12T11:00:00Z",
        "gates": {
            "tests": {"status": "pass", "exit_code": 0, "duration_seconds": 1.5}
        },
        "all_passed": True,
    }


def test_task_verify_schema_accepts_valid_verify() -> None:
    validate_payload(_valid_verify(), _schema("task_verify.schema.json"))


def test_task_verify_schema_rejects_missing_run_id() -> None:
    p = _valid_verify()
    del p["run_id"]
    with pytest.raises(Exception):
        validate_payload(p, _schema("task_verify.schema.json"))


def test_task_verify_schema_rejects_missing_all_passed() -> None:
    p = _valid_verify()
    del p["all_passed"]
    with pytest.raises(Exception):
        validate_payload(p, _schema("task_verify.schema.json"))


# ---------------------------------------------------------------------------
# state.schema.json (v2)
# ---------------------------------------------------------------------------

def _valid_state() -> dict:
    return {
        "version": "0.2",
        "current_task": None,
        "last_run_id": None,
        "last_run_result": None,
        "task_counts": {
            "total": 0,
            "defined": 0,
            "in_progress": 0,
            "done": 0,
            "failed": 0,
            "blocked": 0,
        },
    }


def test_state_schema_accepts_valid_state() -> None:
    validate_payload(_valid_state(), _schema("state.schema.json"))


def test_state_schema_accepts_state_with_active_task() -> None:
    p = _valid_state()
    p["current_task"] = "task-001"
    p["last_run_id"] = "run_20260312_110000"
    p["last_run_result"] = "pass"
    p["task_counts"]["total"] = 1
    p["task_counts"]["in_progress"] = 1
    validate_payload(p, _schema("state.schema.json"))


def test_state_schema_rejects_missing_task_counts() -> None:
    p = _valid_state()
    del p["task_counts"]
    with pytest.raises(Exception):
        validate_payload(p, _schema("state.schema.json"))


def test_state_schema_rejects_unknown_field() -> None:
    p = _valid_state()
    p["unexpected"] = True
    with pytest.raises(Exception):
        validate_payload(p, _schema("state.schema.json"))


def test_state_schema_rejects_invalid_last_run_result() -> None:
    p = _valid_state()
    p["last_run_result"] = "success"  # old v1 value, not valid in v2
    with pytest.raises(Exception):
        validate_payload(p, _schema("state.schema.json"))


# ---------------------------------------------------------------------------
# run_record.schema.json (v2 simplified)
# ---------------------------------------------------------------------------

def _valid_run_record() -> dict:
    return {
        "run_id": "run_20260312_110000",
        "timestamp": "2026-03-12T11:00:00Z",
        "task_id": "task-001",
        "result": "pass",
        "ok": True,
        "gates": {
            "tests": {"status": "pass", "exit_code": 0, "duration_seconds": 1.5}
        },
    }


def test_run_record_schema_accepts_valid_run() -> None:
    validate_payload(_valid_run_record(), _schema("run_record.schema.json"))


def test_run_record_schema_accepts_null_task_id() -> None:
    p = _valid_run_record()
    p["task_id"] = None
    validate_payload(p, _schema("run_record.schema.json"))


def test_run_record_schema_rejects_unknown_field() -> None:
    p = _valid_run_record()
    p["unexpected"] = True
    with pytest.raises(Exception):
        validate_payload(p, _schema("run_record.schema.json"))


# ---------------------------------------------------------------------------
# gate_result.schema.json (unchanged)
# ---------------------------------------------------------------------------

def _valid_gate_result() -> dict:
    return {
        "run_id": "run_1",
        "name": "tests",
        "status": "pass",
        "command": "pytest -q",
        "exit_code": 0,
        "ts_start": "2026-03-12T10:00:00Z",
        "ts_end": "2026-03-12T10:00:02Z",
        "duration_seconds": 2.0,
        "evidence": {"stdout_tail": "1 passed\n", "stderr_tail": ""},
        "metrics": {},
        "environment": {"platform": "Linux", "python": "3.10.12"},
    }


def test_gate_result_schema_unchanged() -> None:
    validate_payload(_valid_gate_result(), _schema("gate_result.schema.json"))


def test_gate_result_schema_rejects_missing_environment() -> None:
    p = _valid_gate_result()
    del p["environment"]
    with pytest.raises(Exception):
        validate_payload(p, _schema("gate_result.schema.json"))


# ---------------------------------------------------------------------------
# project_map.schema.json
# ---------------------------------------------------------------------------

def _valid_project_map() -> dict:
    return {
        "version": "0.1",
        "modules": [
            {
                "module_id": "core",
                "title": "Core module",
                "description": None,
                "task_ids": ["task-001", "task-002"],
            }
        ],
    }


def test_project_map_schema_accepts_valid_payload() -> None:
    validate_payload(_valid_project_map(), _schema("project_map.schema.json"))


def test_project_map_schema_rejects_missing_module_id() -> None:
    payload = _valid_project_map()
    del payload["modules"][0]["module_id"]
    with pytest.raises(Exception):
        validate_payload(payload, _schema("project_map.schema.json"))
