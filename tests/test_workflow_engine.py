from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from jsonschema import validate

from aiwf.orchestrator.workflow_engine import WorkflowEngine
from aiwf.storage.dispatch_artifacts import (
    add_handoff,
    add_transition,
    add_work_item,
    initialize_dispatch_record,
    load_dispatch_record,
)
from aiwf.storage.ai_workspace import AIWorkspace
from aiwf.telemetry.sink import TelemetrySink


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=cwd, text=True, check=True, capture_output=True)


def _read_events(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


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
    gate_report = _load_json(ws.ai_dir / "artifacts" / "reports" / run_id / "smoke.json")
    validate(gate_report, gate_schema)

    run_schema = _load_json(repo_root / "schemas" / "run_record.schema.json")
    run_record = _load_json(ws.ai_dir / "runs" / run_id / "run.json")
    validate(run_record, run_schema)


def test_verify_policy_denied_blocks_gates_and_marks_failure(tmp_path: Path) -> None:
    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    (tmp_path / "src").mkdir(parents=True, exist_ok=True)
    (tmp_path / "src" / "demo.py").write_text("print('ok')\n", encoding="utf-8")

    _git(tmp_path, "init", "-b", "main")
    _git(tmp_path, "config", "user.name", "tester")
    _git(tmp_path, "config", "user.email", "tester@example.com")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "init")

    (tmp_path / ".ai" / "notes.txt").write_text("deny\n", encoding="utf-8")
    (ws.ai_dir / "config.yaml").write_text(
        'workflow_version: "0.1"\n'
        'gates:\n'
        '  smoke: "python3 -c \\"print(123)\\""\n'
        "paths:\n"
        "  allow:\n"
        '    - "src/**"\n'
        "  deny:\n"
        '    - ".git/**"\n'
        '    - ".ai/**"\n',
        encoding="utf-8",
    )
    telemetry_path = ws.ai_dir / "telemetry" / "events.jsonl"
    engine = WorkflowEngine(repo_root=tmp_path, ws=ws, telemetry=TelemetrySink(telemetry_path))

    out = engine.verify()

    assert out["ok"] is False
    assert out["results"] == {}
    run_record = _load_json(ws.ai_dir / "runs" / out["run_id"] / "run.json")
    assert run_record["result"] == "failure"
    assert run_record["results"] == {}
    assert not (ws.ai_dir / "artifacts" / "reports" / "smoke.json").exists()

    events = _read_events(telemetry_path)
    policy_events = [e for e in events if e["type"] == "policy_check"]
    assert policy_events
    assert policy_events[-1]["payload"]["allowed"] is False


def test_verify_policy_allowed_runs_gates(tmp_path: Path) -> None:
    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    (tmp_path / "src").mkdir(parents=True, exist_ok=True)
    src_file = tmp_path / "src" / "demo.py"
    src_file.write_text("print('ok')\n", encoding="utf-8")

    _git(tmp_path, "init", "-b", "main")
    _git(tmp_path, "config", "user.name", "tester")
    _git(tmp_path, "config", "user.email", "tester@example.com")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "init")

    src_file.write_text("print('changed')\n", encoding="utf-8")
    (ws.ai_dir / "config.yaml").write_text(
        'workflow_version: "0.1"\ngates:\n  smoke: "python3 -c \\"print(123)\\""\n',
        encoding="utf-8",
    )
    telemetry_path = ws.ai_dir / "telemetry" / "events.jsonl"
    engine = WorkflowEngine(repo_root=tmp_path, ws=ws, telemetry=TelemetrySink(telemetry_path))

    out = engine.verify()

    assert out["ok"] is True
    assert out["results"]["smoke"]["status"] == "pass"
    assert (ws.ai_dir / "artifacts" / "reports" / out["run_id"] / "smoke.json").exists()

    events = _read_events(telemetry_path)
    policy_events = [e for e in events if e["type"] == "policy_check"]
    assert policy_events
    assert policy_events[-1]["payload"]["allowed"] is True


def test_verify_pr_required_blocks_main_branch(tmp_path: Path) -> None:
    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    (tmp_path / "src").mkdir(parents=True, exist_ok=True)
    (tmp_path / "src" / "demo.py").write_text("print('ok')\n", encoding="utf-8")

    _git(tmp_path, "init", "-b", "main")
    _git(tmp_path, "config", "user.name", "tester")
    _git(tmp_path, "config", "user.email", "tester@example.com")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "init")
    _git(tmp_path, "remote", "add", "origin", "https://example.com/repo.git")

    (ws.ai_dir / "config.yaml").write_text(
        'workflow_version: "0.1"\n'
        'gates:\n'
        '  smoke: "python3 -c \\"print(123)\\""\n'
        "git:\n"
        "  remote: origin\n"
        "  default_branch: main\n"
        "  require_pr: true\n",
        encoding="utf-8",
    )
    telemetry_path = ws.ai_dir / "telemetry" / "events.jsonl"
    engine = WorkflowEngine(repo_root=tmp_path, ws=ws, telemetry=TelemetrySink(telemetry_path))

    out = engine.verify()

    assert out["ok"] is False
    assert out["results"] == {}
    assert not (ws.ai_dir / "artifacts" / "reports" / "smoke.json").exists()
    events = _read_events(telemetry_path)
    pr_events = [e for e in events if e["type"] == "pr_check"]
    assert pr_events
    assert pr_events[-1]["payload"]["ok"] is False


def test_verify_fails_when_no_gates_configured(tmp_path: Path) -> None:
    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    (ws.ai_dir / "config.yaml").write_text('workflow_version: "0.1"\ngates: {}\n', encoding="utf-8")
    telemetry_path = ws.ai_dir / "telemetry" / "events.jsonl"
    engine = WorkflowEngine(repo_root=tmp_path, ws=ws, telemetry=TelemetrySink(telemetry_path))

    out = engine.verify()

    assert out["ok"] is False
    assert out["results"] == {}
    run_record = _load_json(ws.ai_dir / "runs" / out["run_id"] / "run.json")
    assert run_record["result"] == "failure"
    assert not list((ws.ai_dir / "artifacts" / "reports").glob("*.json"))
    events = _read_events(telemetry_path)
    no_gate_events = [e for e in events if e["type"] == "no_gates_configured"]
    assert no_gate_events


def test_develop_writes_unified_run_and_develop_record(tmp_path: Path) -> None:
    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    ws.write_plan({"project_id": "p1", "version": 1, "tasks": []})
    (ws.ai_dir / "config.yaml").write_text(
        'workflow_version: "0.1"\n'
        'gates:\n'
        '  smoke: "python3 -c \\"print(123)\\""\n',
        encoding="utf-8",
    )

    repo_root = Path(__file__).resolve().parents[1]
    engine = WorkflowEngine(
        repo_root=repo_root,
        ws=ws,
        telemetry=TelemetrySink(ws.ai_dir / "telemetry" / "events.jsonl"),
    )
    out = engine.develop(
        run_verify=True,
        sync_roles=True,
        strict_plan=True,
        roles_sync=lambda _rid: {"ok": True},
    )

    assert out["ok"] is True
    assert out["verified"] is True
    run_id = out["run_id"]
    run_record = _load_json(ws.ai_dir / "runs" / run_id / "run.json")
    assert run_record["stage"] == "DEVELOP"
    assert run_record["run_type"] == "develop"
    assert run_record["result"] == "success"
    assert run_record["verified"] is True
    assert "verify" in run_record["steps"]

    develop_record = _load_json(ws.ai_dir / "runs" / run_id / "develop.json")
    assert develop_record["run_id"] == run_id
    assert develop_record["artifacts"]["run_record"] == f".ai/runs/{run_id}/run.json"
    assert f".ai/artifacts/reports/{run_id}/smoke.json" in develop_record["artifacts"]["gate_reports"]


def test_develop_preflight_mode_sets_verified_false_and_partial_result(tmp_path: Path) -> None:
    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    ws.write_plan({"project_id": "p1", "version": 1, "tasks": []})
    repo_root = Path(__file__).resolve().parents[1]
    engine = WorkflowEngine(
        repo_root=repo_root,
        ws=ws,
        telemetry=TelemetrySink(ws.ai_dir / "telemetry" / "events.jsonl"),
    )

    out = engine.develop(
        run_verify=False,
        sync_roles=True,
        strict_plan=True,
        roles_sync=lambda _rid: {"ok": True},
    )

    assert out["ok"] is True
    assert out["verified"] is False
    assert out["mode"] == "preflight"
    run_record = _load_json(ws.ai_dir / "runs" / out["run_id"] / "run.json")
    assert run_record["result"] == "partial"
    assert run_record["verified"] is False


def test_develop_keeps_global_stage_when_verify_runs_as_nested_step(tmp_path: Path) -> None:
    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    ws.write_plan({"project_id": "p1", "version": 1, "tasks": []})
    state = ws.read_state()
    state["stage"] = "DEV"
    ws.write_state(state)
    (ws.ai_dir / "config.yaml").write_text(
        'workflow_version: "0.1"\n'
        'gates:\n'
        '  smoke: "python3 -c \\"print(123)\\""\n',
        encoding="utf-8",
    )

    repo_root = Path(__file__).resolve().parents[1]
    engine = WorkflowEngine(
        repo_root=repo_root,
        ws=ws,
        telemetry=TelemetrySink(ws.ai_dir / "telemetry" / "events.jsonl"),
    )

    out = engine.develop(
        run_verify=True,
        sync_roles=True,
        strict_plan=True,
        roles_sync=lambda _rid: {"ok": True},
    )

    assert out["ok"] is True
    state = ws.read_state()
    assert state["stage"] == "DEV"
    assert state["last_run_id"] == out["run_id"]


def test_verify_writes_gate_reports_under_run_scoped_directory(tmp_path: Path) -> None:
    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    (ws.ai_dir / "config.yaml").write_text(
        'workflow_version: "0.1"\n'
        'gates:\n'
        '  smoke: "python3 -c \\"print(123)\\""\n',
        encoding="utf-8",
    )

    repo_root = Path(__file__).resolve().parents[1]
    engine = WorkflowEngine(
        repo_root=repo_root,
        ws=ws,
        telemetry=TelemetrySink(ws.ai_dir / "telemetry" / "events.jsonl"),
    )

    out = engine.verify()

    report_path = ws.ai_dir / "artifacts" / "reports" / out["run_id"] / "smoke.json"
    assert report_path.exists()
    assert not (ws.ai_dir / "artifacts" / "reports" / "smoke.json").exists()


def test_verify_keeps_previous_run_artifacts_when_run_twice(tmp_path: Path) -> None:
    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    (ws.ai_dir / "config.yaml").write_text(
        'workflow_version: "0.1"\n'
        'gates:\n'
        '  smoke: "python3 -c \\"print(123)\\""\n',
        encoding="utf-8",
    )

    repo_root = Path(__file__).resolve().parents[1]
    engine = WorkflowEngine(
        repo_root=repo_root,
        ws=ws,
        telemetry=TelemetrySink(ws.ai_dir / "telemetry" / "events.jsonl"),
    )

    first = engine.verify(run_id="run_first")
    second = engine.verify(run_id="run_second")

    assert first["run_id"] == "run_first"
    assert second["run_id"] == "run_second"
    assert (ws.ai_dir / "artifacts" / "reports" / "run_first" / "smoke.json").exists()
    assert (ws.ai_dir / "artifacts" / "reports" / "run_second" / "smoke.json").exists()


def test_develop_contract_error_writes_failure_records(tmp_path: Path) -> None:
    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    repo_root = Path(__file__).resolve().parents[1]
    engine = WorkflowEngine(
        repo_root=repo_root,
        ws=ws,
        telemetry=TelemetrySink(ws.ai_dir / "telemetry" / "events.jsonl"),
    )

    try:
        engine.develop(run_verify=False, sync_roles=False, strict_plan=True)
        assert False, "Expected contract error"
    except ValueError as exc:
        assert "Missing .ai/plan.json" in str(exc)

    state = ws.read_state()
    run_id = state["last_run_id"]
    assert run_id
    run_record = _load_json(ws.ai_dir / "runs" / run_id / "run.json")
    assert run_record["result"] == "failure"
    develop_record = _load_json(ws.ai_dir / "runs" / run_id / "develop.json")
    assert develop_record["error"]["type"] == "ContractError"


def test_develop_initializes_dispatch_record_and_links_artifact(tmp_path: Path) -> None:
    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    ws.write_plan({"project_id": "p1", "version": 1, "tasks": []})
    (ws.ai_dir / "config.yaml").write_text(
        'workflow_version: "0.1"\n'
        'gates:\n'
        '  smoke: "python3 -c \\"print(123)\\""\n',
        encoding="utf-8",
    )

    repo_root = Path(__file__).resolve().parents[1]
    engine = WorkflowEngine(
        repo_root=repo_root,
        ws=ws,
        telemetry=TelemetrySink(ws.ai_dir / "telemetry" / "events.jsonl"),
    )

    out = engine.develop(
        run_verify=True,
        sync_roles=True,
        strict_plan=True,
        roles_sync=lambda _rid: {"ok": True},
    )

    dispatch_path = ws.ai_dir / "runs" / out["run_id"] / "dispatch.json"
    assert dispatch_path.exists()
    run_record = _load_json(ws.ai_dir / "runs" / out["run_id"] / "run.json")
    assert run_record["artifacts"]["dispatch_record"] == f".ai/runs/{out['run_id']}/dispatch.json"
    develop_record = _load_json(ws.ai_dir / "runs" / out["run_id"] / "develop.json")
    assert develop_record["artifacts"]["dispatch_record"] == f".ai/runs/{out['run_id']}/dispatch.json"


def test_develop_fails_when_dispatch_record_has_unresolved_blocked_items(tmp_path: Path) -> None:
    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    ws.write_plan({"project_id": "p1", "version": 1, "tasks": []})
    (ws.ai_dir / "config.yaml").write_text(
        'workflow_version: "0.1"\n'
        'gates:\n'
        '  smoke: "python3 -c \\"print(123)\\""\n',
        encoding="utf-8",
    )

    repo_root = Path(__file__).resolve().parents[1]
    initialize_dispatch_record(ws, repo_root, "run_blocked")
    add_work_item(
        ws,
        repo_root,
        "run_blocked",
        item_id="item_blocked",
        title="Blocked work",
        owner_role="implementer",
        acceptance_refs=[],
    )
    add_transition(
        ws,
        repo_root,
        "run_blocked",
        work_item_id="item_blocked",
        to_status="blocked",
        reason="Missing dependency",
    )

    engine = WorkflowEngine(
        repo_root=repo_root,
        ws=ws,
        telemetry=TelemetrySink(ws.ai_dir / "telemetry" / "events.jsonl"),
    )

    out = engine.develop(
        run_verify=True,
        sync_roles=True,
        strict_plan=True,
        run_id="run_blocked",
        roles_sync=lambda _rid: {"ok": True},
    )

    assert out["ok"] is False
    assert out["verified"] is True
    run_record = _load_json(ws.ai_dir / "runs" / "run_blocked" / "run.json")
    assert run_record["result"] == "failure"


def test_dispatch_initialize_creates_empty_record(tmp_path: Path) -> None:
    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    repo_root = Path(__file__).resolve().parents[1]

    record = initialize_dispatch_record(ws, repo_root, "run_dispatch_1")

    assert record["run_id"] == "run_dispatch_1"
    assert record["work_items"] == []
    assert record["handoffs"] == []
    assert record["transitions"] == []
    assert record["summary"]["total_work_items"] == 0
    assert (ws.ai_dir / "runs" / "run_dispatch_1" / "dispatch.json").exists()


def test_dispatch_add_work_item_persists_and_updates_summary(tmp_path: Path) -> None:
    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    repo_root = Path(__file__).resolve().parents[1]
    initialize_dispatch_record(ws, repo_root, "run_dispatch_2")

    add_work_item(
        ws,
        repo_root,
        "run_dispatch_2",
        item_id="item_1",
        title="Write dispatch helpers",
        owner_role="manager",
        acceptance_refs=[".ai/plan.json"],
    )

    record = load_dispatch_record(ws, repo_root, "run_dispatch_2")
    assert len(record["work_items"]) == 1
    assert record["work_items"][0]["id"] == "item_1"
    assert record["work_items"][0]["status"] == "pending"
    assert record["summary"]["total_work_items"] == 1
    assert record["summary"]["pending"] == 1


def test_dispatch_add_handoff_records_role_change_for_existing_item(tmp_path: Path) -> None:
    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    repo_root = Path(__file__).resolve().parents[1]
    initialize_dispatch_record(ws, repo_root, "run_dispatch_3")
    add_work_item(
        ws,
        repo_root,
        "run_dispatch_3",
        item_id="item_1",
        title="Review dispatch contract",
        owner_role="manager",
        acceptance_refs=[],
    )

    add_handoff(
        ws,
        repo_root,
        "run_dispatch_3",
        work_item_id="item_1",
        from_role="manager",
        to_role="implementer",
        reason="Ready for implementation",
        evidence_refs=[".ai/runs/run_dispatch_3/run.json"],
    )

    record = load_dispatch_record(ws, repo_root, "run_dispatch_3")
    assert len(record["handoffs"]) == 1
    assert record["handoffs"][0]["to_role"] == "implementer"
    assert record["summary"]["handoff_count"] == 1


def test_dispatch_transition_allows_pending_to_in_progress_and_rejects_pending_to_done(
    tmp_path: Path,
) -> None:
    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    repo_root = Path(__file__).resolve().parents[1]
    initialize_dispatch_record(ws, repo_root, "run_dispatch_4")
    add_work_item(
        ws,
        repo_root,
        "run_dispatch_4",
        item_id="item_1",
        title="Implement transition guard",
        owner_role="implementer",
        acceptance_refs=[],
    )

    add_transition(
        ws,
        repo_root,
        "run_dispatch_4",
        work_item_id="item_1",
        to_status="in_progress",
        reason="Started work",
    )
    record = load_dispatch_record(ws, repo_root, "run_dispatch_4")
    assert record["work_items"][0]["status"] == "in_progress"
    assert record["summary"]["in_progress"] == 1

    with pytest.raises(ValueError):
        add_transition(
            ws,
            repo_root,
            "run_dispatch_4",
            work_item_id="item_1",
            to_status="done",
            reason="Skip review",
        )
