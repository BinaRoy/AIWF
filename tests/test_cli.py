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


def test_pr_check_fails_on_protected_dev_branch(tmp_path: Path, monkeypatch) -> None:
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
    _git(tmp_path, "checkout", "-b", "dev")
    (ws.ai_dir / "config.yaml").write_text(
        'workflow_version: "0.1"\n'
        "git:\n"
        "  remote: origin\n"
        "  default_branch: dev\n"
        "  protected_branches:\n"
        "    - main\n"
        "    - dev\n"
        "  require_pr: true\n",
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["pr-check"])

    assert result.exit_code == 1
    out = json.loads(result.output)
    assert out["ok"] is False


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


def test_self_check_passes_when_pr_state_and_artifacts_are_valid(tmp_path: Path, monkeypatch) -> None:
    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    _copy_schemas(tmp_path)

    src_file = tmp_path / "src" / "demo.py"
    src_file.parent.mkdir(parents=True, exist_ok=True)
    src_file.write_text("print('v1')\n", encoding="utf-8")
    _git(tmp_path, "init", "-b", "main")
    _git(tmp_path, "config", "user.name", "tester")
    _git(tmp_path, "config", "user.email", "tester@example.com")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "init")
    _git(tmp_path, "remote", "add", "origin", "https://example.com/repo.git")
    _git(tmp_path, "checkout", "-b", "feat/self-check")

    run_id = "run_20260306_121212"
    (ws.ai_dir / "runs" / run_id).mkdir(parents=True, exist_ok=True)
    (ws.ai_dir / "runs" / run_id / "run.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "timestamp": "2026-03-06T12:12:12+00:00",
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
                "ts_start": "2026-03-06T12:12:12+00:00",
                "ts_end": "2026-03-06T12:12:13+00:00",
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

    result = runner.invoke(app, ["self-check"])

    assert result.exit_code == 0
    out = json.loads(result.output)
    assert out["ok"] is True
    assert out["checks"]["pr_workflow"]["ok"] is True
    assert out["checks"]["state_schema"]["ok"] is True
    assert out["checks"]["artifacts"]["ok"] is True
    assert out["checks"]["last_run_success"]["ok"] is True


def test_self_check_fails_when_last_run_missing(tmp_path: Path, monkeypatch) -> None:
    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    _copy_schemas(tmp_path)
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["self-check"])

    assert result.exit_code == 1
    out = json.loads(result.output)
    assert out["ok"] is False
    assert out["checks"]["last_run_success"]["ok"] is False


def test_loop_check_passes_when_required_gates_and_stage_match(tmp_path: Path, monkeypatch) -> None:
    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    _copy_schemas(tmp_path)
    (ws.ai_dir / "config.yaml").write_text(
        'workflow_version: "0.1"\n'
        "process_policy:\n"
        "  fixed_loop:\n"
        "    enabled: true\n"
        "    required_stage: VERIFY\n"
        "    required_gates:\n"
        '      - "unit_tests"\n'
        '      - "self_check"\n'
        "git:\n"
        "  remote: origin\n"
        "  default_branch: main\n"
        "  require_pr: true\n",
        encoding="utf-8",
    )

    src_file = tmp_path / "src" / "demo.py"
    src_file.parent.mkdir(parents=True, exist_ok=True)
    src_file.write_text("print('v1')\n", encoding="utf-8")
    _git(tmp_path, "init", "-b", "main")
    _git(tmp_path, "config", "user.name", "tester")
    _git(tmp_path, "config", "user.email", "tester@example.com")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "init")
    _git(tmp_path, "remote", "add", "origin", "https://example.com/repo.git")
    _git(tmp_path, "checkout", "-b", "feat/loop-ok")

    run_id = "run_20260306_131313"
    run_payload = {
        "run_id": run_id,
        "timestamp": "2026-03-06T13:13:13+00:00",
        "stage": "VERIFY",
        "result": "success",
        "results": {
            "unit_tests": {"status": "pass"},
            "self_check": {"status": "pass"},
        },
    }
    (ws.ai_dir / "runs" / run_id).mkdir(parents=True, exist_ok=True)
    (ws.ai_dir / "runs" / run_id / "run.json").write_text(
        json.dumps(run_payload) + "\n", encoding="utf-8"
    )
    (ws.ai_dir / "artifacts" / "reports" / "unit_tests.json").write_text(
        json.dumps(
            {
                "name": "unit_tests",
                "status": "pass",
                "command": "pytest -q",
                "exit_code": 0,
                "ts_start": "2026-03-06T13:13:13+00:00",
                "ts_end": "2026-03-06T13:13:14+00:00",
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
    state["stage"] = "VERIFY"
    state["last_run_id"] = run_id
    ws.write_state(state)
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["loop-check"])

    assert result.exit_code == 0
    out = json.loads(result.output)
    assert out["ok"] is True
    assert out["checks"]["required_stage"]["ok"] is True
    assert out["checks"]["required_gates"]["ok"] is True


def test_loop_check_fails_when_required_gate_missing(tmp_path: Path, monkeypatch) -> None:
    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    _copy_schemas(tmp_path)
    (ws.ai_dir / "config.yaml").write_text(
        'workflow_version: "0.1"\n'
        "process_policy:\n"
        "  fixed_loop:\n"
        "    enabled: true\n"
        "    required_stage: VERIFY\n"
        "    required_gates:\n"
        '      - "unit_tests"\n'
        '      - "self_check"\n',
        encoding="utf-8",
    )
    run_id = "run_20260306_141414"
    (ws.ai_dir / "runs" / run_id).mkdir(parents=True, exist_ok=True)
    (ws.ai_dir / "runs" / run_id / "run.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "timestamp": "2026-03-06T14:14:14+00:00",
                "stage": "VERIFY",
                "result": "success",
                "results": {"unit_tests": {"status": "pass"}},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    state = ws.read_state()
    state["stage"] = "VERIFY"
    state["last_run_id"] = run_id
    ws.write_state(state)
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["loop-check"])

    assert result.exit_code == 1
    out = json.loads(result.output)
    assert out["ok"] is False
    assert out["checks"]["required_gates"]["ok"] is False


def test_init_self_hosted_writes_safe_default_gates_and_loop_policy(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init", "--self-hosted"])

    assert result.exit_code == 0
    cfg = (tmp_path / ".ai" / "config.yaml").read_text(encoding="utf-8")
    assert "unit_tests" in cfg
    assert "self_check:" not in cfg
    assert "loop_check:" not in cfg
    assert "fixed_loop" in cfg


def test_init_default_does_not_force_self_hosted_gates(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init"])

    assert result.exit_code == 0
    cfg = (tmp_path / ".ai" / "config.yaml").read_text(encoding="utf-8")
    assert "loop_check" not in cfg


def test_plan_validate_passes_with_schema_valid_plan(tmp_path: Path, monkeypatch) -> None:
    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    _copy_schemas(tmp_path)
    ws.write_plan({"project_id": "aiwf", "version": 1, "tasks": [{"id": "T1"}]})
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["plan", "validate"])

    assert result.exit_code == 0
    out = json.loads(result.output)
    assert out["valid"] is True


def test_plan_validate_fails_when_plan_missing(tmp_path: Path, monkeypatch) -> None:
    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    _copy_schemas(tmp_path)
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["plan", "validate"])

    assert result.exit_code == 1
    out = json.loads(result.output)
    assert out["valid"] is False


def test_plan_progress_reports_counts_and_updates_state(tmp_path: Path, monkeypatch) -> None:
    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    _copy_schemas(tmp_path)
    ws.write_plan(
        {
            "project_id": "aiwf",
            "version": 1,
            "tasks": [
                {"id": "T1", "status": "completed"},
                {"id": "T2", "status": "in_progress"},
                {"id": "T3", "status": "pending"},
            ],
        }
    )
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["plan", "progress"])

    assert result.exit_code == 0
    out = json.loads(result.output)
    assert out["ok"] is True
    assert out["counts"] == {"total": 3, "completed": 1, "in_progress": 1, "pending": 1}
    state = ws.read_state()
    assert state["plan_progress"]["counts"]["total"] == 3


def test_plan_progress_fails_when_plan_invalid(tmp_path: Path, monkeypatch) -> None:
    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    _copy_schemas(tmp_path)
    ws.write_plan({"project_id": "aiwf", "version": 1})
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["plan", "progress"])

    assert result.exit_code == 1
    out = json.loads(result.output)
    assert out["ok"] is False


def test_risk_status_initializes_empty_registry(tmp_path: Path, monkeypatch) -> None:
    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    _copy_schemas(tmp_path)
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["risk", "status"])

    assert result.exit_code == 0
    out = json.loads(result.output)
    assert out["ok"] is True
    assert out["counts"]["open"] == 0
    assert out["counts"]["active_waivers"] == 0
    assert (tmp_path / ".ai" / "risk_register.json").exists()


def test_risk_waive_adds_expiry_aware_waiver(tmp_path: Path, monkeypatch) -> None:
    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    _copy_schemas(tmp_path)
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(
        app,
        ["risk", "waive", "RISK-1", "--reason", "temporary exception", "--expires-at", "2099-01-01"],
    )

    assert result.exit_code == 0
    out = json.loads(result.output)
    assert out["ok"] is True
    status_result = runner.invoke(app, ["risk", "status"])
    status_out = json.loads(status_result.output)
    assert status_out["counts"]["active_waivers"] == 1


def test_risk_status_marks_expired_waiver(tmp_path: Path, monkeypatch) -> None:
    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    _copy_schemas(tmp_path)
    risk_path = tmp_path / ".ai" / "risk_register.json"
    risk_path.write_text(
        json.dumps(
            {
                "version": 1,
                "updated_at": "2026-03-06T00:00:00+00:00",
                "risks": [
                    {
                        "id": "RISK-1",
                        "title": "demo",
                        "status": "open",
                        "waiver": {
                            "reason": "temporary",
                            "issued_at": "2026-03-01T00:00:00+00:00",
                            "expires_at": "2026-03-02T00:00:00+00:00",
                        },
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["risk", "status"])

    assert result.exit_code == 0
    out = json.loads(result.output)
    assert out["counts"]["expired_waivers"] == 1
    assert out["counts"]["active_waivers"] == 0


def test_audit_summary_includes_risk_snapshot(tmp_path: Path, monkeypatch) -> None:
    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    _copy_schemas(tmp_path)
    (tmp_path / ".ai" / "risk_register.json").write_text(
        json.dumps(
            {
                "version": 1,
                "updated_at": "2026-03-06T00:00:00+00:00",
                "risks": [{"id": "R1", "title": "risk", "status": "open"}],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["audit-summary"])

    assert result.exit_code == 0
    out = json.loads(result.output)
    assert out["risk"]["present"] is True
    assert out["risk"]["counts"]["open"] == 1


def test_roles_init_creates_default_multi_role_workflow(tmp_path: Path, monkeypatch) -> None:
    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    _copy_schemas(tmp_path)
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["roles", "init"])

    assert result.exit_code == 0
    out = json.loads(result.output)
    assert out["ok"] is True
    assert (tmp_path / ".ai" / "roles_workflow.json").exists()


def test_roles_status_reports_role_counts(tmp_path: Path, monkeypatch) -> None:
    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    _copy_schemas(tmp_path)
    (tmp_path / ".ai" / "roles_workflow.json").write_text(
        json.dumps(
            {
                "version": 1,
                "updated_at": "2026-03-06T00:00:00+00:00",
                "roles": [
                    {"name": "planner", "status": "completed", "evidence": ["docs/plans/x.md"]},
                    {"name": "implementer", "status": "in_progress", "evidence": []},
                    {"name": "reviewer", "status": "pending", "evidence": []},
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["roles", "status"])

    assert result.exit_code == 0
    out = json.loads(result.output)
    assert out["counts"]["total"] == 3
    assert out["counts"]["completed"] == 1
    assert out["counts"]["in_progress"] == 1
    assert out["counts"]["pending"] == 1


def test_roles_check_fails_when_completed_role_lacks_evidence(tmp_path: Path, monkeypatch) -> None:
    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    _copy_schemas(tmp_path)
    (tmp_path / ".ai" / "roles_workflow.json").write_text(
        json.dumps(
            {
                "version": 1,
                "updated_at": "2026-03-06T00:00:00+00:00",
                "roles": [
                    {"name": "planner", "status": "completed", "evidence": []},
                    {"name": "implementer", "status": "pending", "evidence": []},
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["roles", "check"])

    assert result.exit_code == 1
    out = json.loads(result.output)
    assert out["ok"] is False


def test_roles_update_sets_status_and_appends_evidence(tmp_path: Path, monkeypatch) -> None:
    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    _copy_schemas(tmp_path)
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["roles", "init"])

    result = runner.invoke(
        app,
        [
            "roles",
            "update",
            "planner",
            "--status",
            "completed",
            "--evidence",
            "docs/plans/2026-03-06-aiwf-self-hosting-direction-plan.md",
        ],
    )

    assert result.exit_code == 0
    out = json.loads(result.output)
    assert out["ok"] is True
    status = runner.invoke(app, ["roles", "status"])
    status_out = json.loads(status.output)
    assert status_out["counts"]["completed"] >= 1


def test_roles_update_rejects_invalid_status(tmp_path: Path, monkeypatch) -> None:
    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    _copy_schemas(tmp_path)
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["roles", "init"])

    result = runner.invoke(app, ["roles", "update", "planner", "--status", "done"])

    assert result.exit_code == 1
    out = json.loads(result.output)
    assert out["ok"] is False


def test_roles_update_then_roles_check_supports_closed_loop(tmp_path: Path, monkeypatch) -> None:
    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    _copy_schemas(tmp_path)
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["roles", "init"])

    runner.invoke(
        app,
        [
            "roles",
            "update",
            "planner",
            "--status",
            "completed",
            "--evidence",
            "docs/plans/x.md",
        ],
    )
    runner.invoke(app, ["roles", "update", "implementer", "--status", "in_progress"])

    result = runner.invoke(app, ["roles", "check"])

    assert result.exit_code == 0
    out = json.loads(result.output)
    assert out["ok"] is True


def test_roles_autopilot_advances_roles_from_checks(tmp_path: Path, monkeypatch) -> None:
    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    _copy_schemas(tmp_path)
    monkeypatch.chdir(tmp_path)

    src_file = tmp_path / "src" / "demo.py"
    src_file.parent.mkdir(parents=True, exist_ok=True)
    src_file.write_text("print('v1')\n", encoding="utf-8")
    _git(tmp_path, "init", "-b", "main")
    _git(tmp_path, "config", "user.name", "tester")
    _git(tmp_path, "config", "user.email", "tester@example.com")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "init")
    _git(tmp_path, "remote", "add", "origin", "https://example.com/repo.git")
    _git(tmp_path, "checkout", "-b", "feat/auto")

    (tmp_path / ".ai" / "config.yaml").write_text(
        'workflow_version: "0.1"\n'
        "gates:\n"
        '  smoke: "python3 -c \\"print(123)\\""\n'
        "git:\n"
        "  remote: origin\n"
        "  default_branch: main\n"
        "  require_pr: true\n"
        "process_policy:\n"
        "  fixed_loop:\n"
        "    enabled: true\n"
        "    required_stage: VERIFY\n"
        "    required_gates:\n"
        '      - "smoke"\n',
        encoding="utf-8",
    )
    ws.write_plan({"project_id": "aiwf", "version": 1, "tasks": [{"id": "T1"}]})
    runner.invoke(app, ["roles", "init"])

    result = runner.invoke(app, ["roles", "autopilot", "--verify"])

    assert result.exit_code == 0
    out = json.loads(result.output)
    assert out["ok"] is True
    roles_status = {r["name"]: r["status"] for r in out["roles"]}
    assert roles_status["planner"] == "completed"
    assert roles_status["implementer"] == "completed"
    assert roles_status["reviewer"] == "completed"
    assert roles_status["tester"] == "completed"
    assert roles_status["supervisor"] == "completed"


def test_roles_autopilot_sets_first_incomplete_role_in_progress(tmp_path: Path, monkeypatch) -> None:
    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    _copy_schemas(tmp_path)
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["roles", "init"])

    result = runner.invoke(app, ["roles", "autopilot"])

    assert result.exit_code == 1
    out = json.loads(result.output)
    roles_status = {r["name"]: r["status"] for r in out["roles"]}
    assert roles_status["planner"] == "in_progress"


def test_develop_preflight_mode_returns_verified_false(tmp_path: Path, monkeypatch) -> None:
    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    _copy_schemas(tmp_path)
    ws.write_plan({"project_id": "aiwf", "version": 1, "tasks": []})
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["develop", "--no-verify"])

    assert result.exit_code == 0
    out = json.loads(result.output)
    assert out["ok"] is True
    assert out["verified"] is False
    assert out["mode"] == "preflight"


def test_develop_returns_exit_2_for_contract_error(tmp_path: Path, monkeypatch) -> None:
    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    _copy_schemas(tmp_path)
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["develop", "--no-verify", "--no-sync-roles"])

    assert result.exit_code == 2
    out = json.loads(result.output)
    assert out["ok"] is False
    assert out["type"] == "contract_error"


def test_develop_returns_exit_1_when_verify_fails(tmp_path: Path, monkeypatch) -> None:
    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    _copy_schemas(tmp_path)
    ws.write_plan({"project_id": "aiwf", "version": 1, "tasks": []})
    (ws.ai_dir / "config.yaml").write_text(
        'workflow_version: "0.1"\n'
        "gates:\n"
        '  unit_tests: "python3 -c \\"import sys; sys.exit(1)\\""\n'
        "git:\n"
        "  require_pr: false\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["develop"])

    assert result.exit_code == 1
    out = json.loads(result.output)
    assert out["ok"] is False
    assert out["verified"] is False
