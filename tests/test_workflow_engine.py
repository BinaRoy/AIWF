from __future__ import annotations

import json
import subprocess
from pathlib import Path

from jsonschema import validate

from aiwf.orchestrator.workflow_engine import WorkflowEngine
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
    gate_report = _load_json(ws.ai_dir / "artifacts" / "reports" / "smoke.json")
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
    assert (ws.ai_dir / "artifacts" / "reports" / "smoke.json").exists()

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
