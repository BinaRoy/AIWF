from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from typer.testing import CliRunner

from aiwf.cli.main import app
from aiwf.storage.ai_workspace import AIWorkspace


runner = CliRunner()


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=cwd, text=True, check=True, capture_output=True)


def _copy_schemas(repo_root: Path) -> None:
    src_schemas = Path(__file__).resolve().parents[1] / "schemas"
    shutil.copytree(src_schemas, repo_root / "schemas")


def test_status_prints_current_state(tmp_path: Path, monkeypatch) -> None:
    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    state = ws.read_state()
    state["stage"] = "DEV"
    ws.write_state(state)
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0
    out = json.loads(result.output)
    assert out["stage"] == "DEV"


def test_policy_check_denied_returns_nonzero(tmp_path: Path, monkeypatch) -> None:
    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["policy-check", ".ai/state.json"])

    assert result.exit_code == 1
    out = json.loads(result.output)
    assert out["allowed"] is False


def test_validate_state_succeeds_with_default_state(tmp_path: Path, monkeypatch) -> None:
    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["validate-state"])

    assert result.exit_code == 0
    out = json.loads(result.output)
    assert out["valid"] is True


def test_policy_check_git_allows_src_change(tmp_path: Path, monkeypatch) -> None:
    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    src_file = tmp_path / "src" / "demo.py"
    src_file.parent.mkdir(parents=True, exist_ok=True)
    src_file.write_text("print('v1')\n", encoding="utf-8")

    _git(tmp_path, "init", "-b", "main")
    _git(tmp_path, "config", "user.name", "tester")
    _git(tmp_path, "config", "user.email", "tester@example.com")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "init")

    src_file.write_text("print('v2')\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["policy-check", "--git"])

    assert result.exit_code == 0
    out = json.loads(result.output)
    assert out["allowed"] is True
    assert "src/demo.py" in out["paths"]


def test_policy_check_git_denies_ai_change(tmp_path: Path, monkeypatch) -> None:
    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    src_file = tmp_path / "src" / "demo.py"
    src_file.parent.mkdir(parents=True, exist_ok=True)
    src_file.write_text("print('v1')\n", encoding="utf-8")

    _git(tmp_path, "init", "-b", "main")
    _git(tmp_path, "config", "user.name", "tester")
    _git(tmp_path, "config", "user.email", "tester@example.com")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "init")

    (tmp_path / ".ai" / "notes.txt").write_text("note\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["policy-check", "--git"])

    assert result.exit_code == 1
    out = json.loads(result.output)
    assert out["allowed"] is False


def test_pr_check_fails_on_default_branch(tmp_path: Path, monkeypatch) -> None:
    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    src_file = tmp_path / "src" / "demo.py"
    src_file.parent.mkdir(parents=True, exist_ok=True)
    src_file.write_text("print('v1')\n", encoding="utf-8")

    _git(tmp_path, "init", "-b", "main")
    _git(tmp_path, "config", "user.name", "tester")
    _git(tmp_path, "config", "user.email", "tester@example.com")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "init")
    _git(tmp_path, "remote", "add", "origin", "https://example.com/repo.git")

    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["pr-check"])

    assert result.exit_code == 1
    out = json.loads(result.output)
    assert out["ok"] is False


def test_pr_check_passes_on_feature_branch_with_remote(tmp_path: Path, monkeypatch) -> None:
    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    src_file = tmp_path / "src" / "demo.py"
    src_file.parent.mkdir(parents=True, exist_ok=True)
    src_file.write_text("print('v1')\n", encoding="utf-8")

    _git(tmp_path, "init", "-b", "main")
    _git(tmp_path, "config", "user.name", "tester")
    _git(tmp_path, "config", "user.email", "tester@example.com")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "init")
    _git(tmp_path, "remote", "add", "origin", "https://example.com/repo.git")
    _git(tmp_path, "checkout", "-b", "feat/pr-flow")

    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["pr-check"])

    assert result.exit_code == 0
    out = json.loads(result.output)
    assert out["ok"] is True


def test_validate_artifacts_succeeds_with_valid_run_and_gate_reports(
    tmp_path: Path, monkeypatch
) -> None:
    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    _copy_schemas(tmp_path)

    run_id = "run_20260306_000001"
    (ws.ai_dir / "runs" / run_id).mkdir(parents=True, exist_ok=True)
    (ws.ai_dir / "runs" / run_id / "run.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "timestamp": "2026-03-06T00:00:00+00:00",
                "stage": "VERIFY",
                "result": "success",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (ws.ai_dir / "artifacts" / "reports" / "smoke.json").write_text(
        json.dumps(
            {
                "name": "smoke",
                "status": "pass",
                "command": "echo ok",
                "exit_code": 0,
                "ts_start": "2026-03-06T00:00:00+00:00",
                "ts_end": "2026-03-06T00:00:01+00:00",
                "duration_seconds": 1.0,
                "evidence": {},
                "metrics": {},
                "environment": {},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    state = ws.read_state()
    state["last_run_id"] = run_id
    ws.write_state(state)

    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["validate-artifacts"])

    assert result.exit_code == 0
    out = json.loads(result.output)
    assert out["valid"] is True


def test_validate_artifacts_fails_when_run_record_missing(tmp_path: Path, monkeypatch) -> None:
    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    _copy_schemas(tmp_path)
    state = ws.read_state()
    state["last_run_id"] = "run_20260306_000001"
    ws.write_state(state)

    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["validate-artifacts"])

    assert result.exit_code == 1
    out = json.loads(result.output)
    assert out["valid"] is False


def test_validate_artifacts_fails_when_gate_report_invalid(tmp_path: Path, monkeypatch) -> None:
    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    _copy_schemas(tmp_path)

    run_id = "run_20260306_000001"
    (ws.ai_dir / "runs" / run_id).mkdir(parents=True, exist_ok=True)
    (ws.ai_dir / "runs" / run_id / "run.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "timestamp": "2026-03-06T00:00:00+00:00",
                "stage": "VERIFY",
                "result": "success",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (ws.ai_dir / "artifacts" / "reports" / "smoke.json").write_text("{}\n", encoding="utf-8")
    state = ws.read_state()
    state["last_run_id"] = run_id
    ws.write_state(state)

    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["validate-artifacts"])

    assert result.exit_code == 1
    out = json.loads(result.output)
    assert out["valid"] is False


def test_stage_set_updates_state_for_valid_stage(tmp_path: Path, monkeypatch) -> None:
    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    _copy_schemas(tmp_path)
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["stage", "set", "DEV"])

    assert result.exit_code == 0
    out = json.loads(result.output)
    assert out["ok"] is True
    assert out["stage"] == "DEV"
    assert ws.read_state()["stage"] == "DEV"


def test_stage_set_rejects_unknown_stage(tmp_path: Path, monkeypatch) -> None:
    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    _copy_schemas(tmp_path)
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["stage", "set", "RANDOM"])

    assert result.exit_code == 1
    out = json.loads(result.output)
    assert out["ok"] is False


def test_stage_set_ship_requires_successful_verify_run(tmp_path: Path, monkeypatch) -> None:
    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    _copy_schemas(tmp_path)
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["stage", "set", "SHIP"])

    assert result.exit_code == 1
    out = json.loads(result.output)
    assert out["ok"] is False
    assert ws.read_state()["stage"] != "SHIP"


def test_stage_set_done_requires_current_stage_ship(tmp_path: Path, monkeypatch) -> None:
    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    _copy_schemas(tmp_path)
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["stage", "set", "DONE"])

    assert result.exit_code == 1
    out = json.loads(result.output)
    assert out["ok"] is False


def test_stage_set_done_allowed_when_current_stage_is_ship(tmp_path: Path, monkeypatch) -> None:
    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    _copy_schemas(tmp_path)
    state = ws.read_state()
    state["stage"] = "SHIP"
    ws.write_state(state)
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["stage", "set", "DONE"])

    assert result.exit_code == 0
    out = json.loads(result.output)
    assert out["ok"] is True
    assert ws.read_state()["stage"] == "DONE"


def test_audit_summary_reports_stage_run_and_gate_counts(tmp_path: Path, monkeypatch) -> None:
    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    run_id = "run_20260306_101010"
    (ws.ai_dir / "runs" / run_id).mkdir(parents=True, exist_ok=True)
    (ws.ai_dir / "runs" / run_id / "run.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "timestamp": "2026-03-06T10:10:10+00:00",
                "stage": "VERIFY",
                "result": "success",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    state = ws.read_state()
    state["stage"] = "VERIFY"
    state["last_run_id"] = run_id
    state["gates"] = {
        "g1": {"status": "pass"},
        "g2": {"status": "fail"},
        "g3": {"status": "skip"},
    }
    ws.write_state(state)
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["audit-summary"])

    assert result.exit_code == 0
    out = json.loads(result.output)
    assert out["stage"] == "VERIFY"
    assert out["last_run_id"] == run_id
    assert out["last_run_result"] == "success"
    assert out["gate_counts"] == {"total": 3, "pass": 1, "fail": 1, "skip": 1}
    assert out["policy"]["present"] is False


def test_audit_summary_reads_latest_policy_check_event(tmp_path: Path, monkeypatch) -> None:
    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    telemetry_path = ws.ai_dir / "telemetry" / "events.jsonl"
    telemetry_path.write_text(
        json.dumps({"type": "policy_check", "payload": {"allowed": False, "reason": "old"}}) + "\n"
        + json.dumps({"type": "run_started", "payload": {"stage": "VERIFY"}}) + "\n"
        + json.dumps({"type": "policy_check", "payload": {"allowed": True, "reason": "latest"}})
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["audit-summary"])

    assert result.exit_code == 0
    out = json.loads(result.output)
    assert out["policy"]["present"] is True
    assert out["policy"]["allowed"] is True
    assert out["policy"]["reason"] == "latest"
