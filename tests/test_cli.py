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


def test_init_self_hosted_sets_fixed_loop_required_stage_to_dev(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["init", "--self-hosted"])

    assert result.exit_code == 0
    config_text = (tmp_path / ".ai" / "config.yaml").read_text(encoding="utf-8")
    assert "required_stage: DEV" in config_text


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
                "run_type": "verify",
                "result": "success",
                "ok": True,
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
    (ws.ai_dir / "artifacts" / "reports" / run_id).mkdir(parents=True, exist_ok=True)
    (ws.ai_dir / "artifacts" / "reports" / run_id / "smoke.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
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


def test_dispatch_init_creates_run_scoped_dispatch_record(tmp_path: Path, monkeypatch) -> None:
    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    _copy_schemas(tmp_path)
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["dispatch", "init", "--run-id", "run_dispatch_cli_1"])

    assert result.exit_code == 0
    out = json.loads(result.output)
    assert out["run_id"] == "run_dispatch_cli_1"
    assert (ws.ai_dir / "runs" / "run_dispatch_cli_1" / "dispatch.json").exists()


def test_dispatch_add_item_writes_work_item_to_dispatch_record(tmp_path: Path, monkeypatch) -> None:
    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    _copy_schemas(tmp_path)
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["dispatch", "init", "--run-id", "run_dispatch_cli_2"])

    result = runner.invoke(
        app,
        [
            "dispatch",
            "add-item",
            "--run-id",
            "run_dispatch_cli_2",
            "--id",
            "item_1",
            "--title",
            "Write CLI",
            "--owner-role",
            "manager",
            "--acceptance-ref",
            ".ai/plan.json",
        ],
    )

    assert result.exit_code == 0
    out = json.loads(result.output)
    assert out["summary"]["total_work_items"] == 1
    dispatch_payload = json.loads(
        (ws.ai_dir / "runs" / "run_dispatch_cli_2" / "dispatch.json").read_text(encoding="utf-8")
    )
    assert dispatch_payload["work_items"][0]["id"] == "item_1"


def test_dispatch_handoff_records_role_transfer(tmp_path: Path, monkeypatch) -> None:
    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    _copy_schemas(tmp_path)
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["dispatch", "init", "--run-id", "run_dispatch_cli_3"])
    runner.invoke(
        app,
        [
            "dispatch",
            "add-item",
            "--run-id",
            "run_dispatch_cli_3",
            "--id",
            "item_1",
            "--title",
            "Write CLI",
            "--owner-role",
            "manager",
        ],
    )

    result = runner.invoke(
        app,
        [
            "dispatch",
            "handoff",
            "--run-id",
            "run_dispatch_cli_3",
            "--work-item-id",
            "item_1",
            "--from-role",
            "manager",
            "--to-role",
            "implementer",
            "--reason",
            "Ready",
            "--evidence-ref",
            ".ai/runs/run_dispatch_cli_3/run.json",
        ],
    )

    assert result.exit_code == 0
    out = json.loads(result.output)
    assert out["summary"]["handoff_count"] == 1
    dispatch_payload = json.loads(
        (ws.ai_dir / "runs" / "run_dispatch_cli_3" / "dispatch.json").read_text(encoding="utf-8")
    )
    assert dispatch_payload["handoffs"][0]["to_role"] == "implementer"


def test_dispatch_transition_updates_item_status(tmp_path: Path, monkeypatch) -> None:
    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    _copy_schemas(tmp_path)
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["dispatch", "init", "--run-id", "run_dispatch_cli_4"])
    runner.invoke(
        app,
        [
            "dispatch",
            "add-item",
            "--run-id",
            "run_dispatch_cli_4",
            "--id",
            "item_1",
            "--title",
            "Write CLI",
            "--owner-role",
            "implementer",
        ],
    )

    result = runner.invoke(
        app,
        [
            "dispatch",
            "transition",
            "--run-id",
            "run_dispatch_cli_4",
            "--work-item-id",
            "item_1",
            "--to-status",
            "in_progress",
            "--reason",
            "Started",
        ],
    )

    assert result.exit_code == 0
    out = json.loads(result.output)
    assert out["summary"]["in_progress"] == 1
    dispatch_payload = json.loads(
        (ws.ai_dir / "runs" / "run_dispatch_cli_4" / "dispatch.json").read_text(encoding="utf-8")
    )
    assert dispatch_payload["work_items"][0]["status"] == "in_progress"


def test_dispatch_status_returns_current_dispatch_record(tmp_path: Path, monkeypatch) -> None:
    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    _copy_schemas(tmp_path)
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["dispatch", "init", "--run-id", "run_dispatch_cli_5"])
    runner.invoke(
        app,
        [
            "dispatch",
            "add-item",
            "--run-id",
            "run_dispatch_cli_5",
            "--id",
            "item_1",
            "--title",
            "Write CLI",
            "--owner-role",
            "manager",
        ],
    )

    result = runner.invoke(app, ["dispatch", "status", "--run-id", "run_dispatch_cli_5"])

    assert result.exit_code == 0
    out = json.loads(result.output)
    assert out["run_id"] == "run_dispatch_cli_5"
    assert out["summary"]["total_work_items"] == 1


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
                "run_type": "verify",
                "result": "success",
                "ok": True,
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
    (ws.ai_dir / "artifacts" / "reports" / run_id).mkdir(parents=True, exist_ok=True)
    (ws.ai_dir / "artifacts" / "reports" / run_id / "smoke.json").write_text("{}\n", encoding="utf-8")
    state = ws.read_state()
    state["last_run_id"] = run_id
    ws.write_state(state)

    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["validate-artifacts"])

    assert result.exit_code == 1
    out = json.loads(result.output)
    assert out["valid"] is False


def test_validate_artifacts_uses_last_run_scoped_directory_only(tmp_path: Path, monkeypatch) -> None:
    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    _copy_schemas(tmp_path)

    valid_run_id = "run_valid"
    stale_run_id = "run_stale"
    for run_id in [valid_run_id, stale_run_id]:
        (ws.ai_dir / "runs" / run_id).mkdir(parents=True, exist_ok=True)
    (ws.ai_dir / "runs" / valid_run_id / "run.json").write_text(
        json.dumps(
            {
                "run_id": valid_run_id,
                "timestamp": "2026-03-06T00:00:00+00:00",
                "stage": "VERIFY",
                "run_type": "verify",
                "result": "success",
                "ok": True,
                "artifacts": {
                    "run_record": f".ai/runs/{valid_run_id}/run.json",
                    "gate_reports": [f".ai/artifacts/reports/{valid_run_id}/smoke.json"],
                    "telemetry": ".ai/telemetry/events.jsonl",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (ws.ai_dir / "runs" / stale_run_id / "run.json").write_text(
        json.dumps(
            {
                "run_id": stale_run_id,
                "timestamp": "2026-03-05T00:00:00+00:00",
                "stage": "VERIFY",
                "run_type": "verify",
                "result": "failure",
                "ok": False,
                "artifacts": {
                    "run_record": f".ai/runs/{stale_run_id}/run.json",
                    "gate_reports": [f".ai/artifacts/reports/{stale_run_id}/smoke.json"],
                    "telemetry": ".ai/telemetry/events.jsonl",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    (ws.ai_dir / "artifacts" / "reports" / valid_run_id).mkdir(parents=True, exist_ok=True)
    (ws.ai_dir / "artifacts" / "reports" / valid_run_id / "smoke.json").write_text(
        json.dumps(
            {
                "run_id": valid_run_id,
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

    (ws.ai_dir / "artifacts" / "reports" / stale_run_id).mkdir(parents=True, exist_ok=True)
    (ws.ai_dir / "artifacts" / "reports" / stale_run_id / "smoke.json").write_text(
        "{}\n",
        encoding="utf-8",
    )

    state = ws.read_state()
    state["last_run_id"] = valid_run_id
    ws.write_state(state)

    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["validate-artifacts"])

    assert result.exit_code == 0
    out = json.loads(result.output)
    assert out["valid"] is True
    assert out["run_id"] == valid_run_id


def test_validate_artifacts_validates_dispatch_record_when_referenced(tmp_path: Path, monkeypatch) -> None:
    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    _copy_schemas(tmp_path)

    run_id = "run_dispatch_validate"
    (ws.ai_dir / "runs" / run_id).mkdir(parents=True, exist_ok=True)
    (ws.ai_dir / "runs" / run_id / "run.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "timestamp": "2026-03-11T00:00:00+00:00",
                "stage": "DEVELOP",
                "run_type": "develop",
                "result": "success",
                "ok": True,
                "mode": "full",
                "verified": True,
                "steps": {},
                "artifacts": {
                    "run_record": f".ai/runs/{run_id}/run.json",
                    "develop_record": f".ai/runs/{run_id}/develop.json",
                    "dispatch_record": f".ai/runs/{run_id}/dispatch.json",
                    "gate_reports": [f".ai/artifacts/reports/{run_id}/smoke.json"],
                    "telemetry": ".ai/telemetry/events.jsonl",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (ws.ai_dir / "runs" / run_id / "dispatch.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "timestamp": "2026-03-11T00:00:00+00:00",
                "work_items": [],
                "handoffs": [],
                "transitions": [],
                "summary": {
                    "total_work_items": 0,
                    "pending": 0,
                    "in_progress": 0,
                    "handoff": 0,
                    "review": 0,
                    "done": 0,
                    "blocked": 0,
                    "handoff_count": 0,
                    "transition_count": 0,
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
                "ts_start": "2026-03-11T00:00:00+00:00",
                "ts_end": "2026-03-11T00:00:01+00:00",
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
    assert out["run_id"] == run_id


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


def test_stage_set_ship_allows_successful_verified_develop_run(tmp_path: Path, monkeypatch) -> None:
    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    _copy_schemas(tmp_path)
    run_id = "run_20260310_120000"
    (ws.ai_dir / "runs" / run_id).mkdir(parents=True, exist_ok=True)
    (ws.ai_dir / "runs" / run_id / "run.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "timestamp": "2026-03-10T12:00:00+00:00",
                "stage": "DEVELOP",
                "run_type": "develop",
                "mode": "full",
                "verified": True,
                "result": "success",
                "ok": True,
                "steps": {
                    "plan": {"ok": True},
                    "roles_sync": {"ok": True},
                    "verify": {"ok": True},
                },
                "artifacts": {
                    "run_record": f".ai/runs/{run_id}/run.json",
                    "develop_record": f".ai/runs/{run_id}/develop.json",
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
    ws.write_state(state)
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["stage", "set", "SHIP"])

    assert result.exit_code == 0
    out = json.loads(result.output)
    assert out["ok"] is True
    assert ws.read_state()["stage"] == "SHIP"


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


def test_audit_summary_reads_policy_check_for_last_run_id(tmp_path: Path, monkeypatch) -> None:
    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    run_id = "run_20260310_130000"
    state = ws.read_state()
    state["last_run_id"] = run_id
    ws.write_state(state)
    telemetry_path = ws.ai_dir / "telemetry" / "events.jsonl"
    telemetry_path.write_text(
        json.dumps({"type": "policy_check", "run_id": "run_old", "payload": {"allowed": False, "reason": "old"}})
        + "\n"
        + json.dumps({"type": "policy_check", "run_id": run_id, "payload": {"allowed": True, "reason": "current"}})
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["audit-summary"])

    assert result.exit_code == 0
    out = json.loads(result.output)
    assert out["policy"]["present"] is True
    assert out["policy"]["allowed"] is True
    assert out["policy"]["reason"] == "current"


def test_audit_summary_includes_dispatch_summary_when_present(tmp_path: Path, monkeypatch) -> None:
    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    run_id = "run_dispatch_summary"
    (ws.ai_dir / "runs" / run_id).mkdir(parents=True, exist_ok=True)
    (ws.ai_dir / "runs" / run_id / "run.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "timestamp": "2026-03-11T00:00:00+00:00",
                "stage": "DEVELOP",
                "run_type": "develop",
                "result": "success",
                "ok": True,
                "mode": "full",
                "verified": True,
                "steps": {},
                "artifacts": {
                    "run_record": f".ai/runs/{run_id}/run.json",
                    "develop_record": f".ai/runs/{run_id}/develop.json",
                    "dispatch_record": f".ai/runs/{run_id}/dispatch.json",
                    "gate_reports": [],
                    "telemetry": ".ai/telemetry/events.jsonl",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (ws.ai_dir / "runs" / run_id / "dispatch.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "timestamp": "2026-03-11T00:00:00+00:00",
                "work_items": [
                    {
                        "id": "item_1",
                        "title": "demo",
                        "status": "in_progress",
                        "owner_role": "implementer",
                        "created_at": "2026-03-11T00:00:00+00:00",
                        "updated_at": "2026-03-11T00:01:00+00:00",
                        "acceptance_refs": [],
                    }
                ],
                "handoffs": [],
                "transitions": [],
                "summary": {
                    "total_work_items": 1,
                    "pending": 0,
                    "in_progress": 1,
                    "handoff": 0,
                    "review": 0,
                    "done": 0,
                    "blocked": 0,
                    "handoff_count": 0,
                    "transition_count": 0,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    state = ws.read_state()
    state["stage"] = "DEV"
    state["last_run_id"] = run_id
    ws.write_state(state)
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["audit-summary"])

    assert result.exit_code == 0
    out = json.loads(result.output)
    assert out["dispatch"]["present"] is True
    assert out["dispatch"]["summary"]["in_progress"] == 1


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
                "run_type": "verify",
                "result": "success",
                "ok": True,
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
    (ws.ai_dir / "artifacts" / "reports" / run_id).mkdir(parents=True, exist_ok=True)
    (ws.ai_dir / "artifacts" / "reports" / run_id / "smoke.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
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
        "run_type": "verify",
        "result": "success",
        "ok": True,
        "results": {
            "unit_tests": {"status": "pass"},
            "self_check": {"status": "pass"},
        },
        "artifacts": {
            "run_record": f".ai/runs/{run_id}/run.json",
            "gate_reports": [f".ai/artifacts/reports/{run_id}/unit_tests.json"],
            "telemetry": ".ai/telemetry/events.jsonl",
        },
    }
    (ws.ai_dir / "runs" / run_id).mkdir(parents=True, exist_ok=True)
    (ws.ai_dir / "runs" / run_id / "run.json").write_text(
        json.dumps(run_payload) + "\n", encoding="utf-8"
    )
    (ws.ai_dir / "artifacts" / "reports" / run_id).mkdir(parents=True, exist_ok=True)
    (ws.ai_dir / "artifacts" / "reports" / run_id / "unit_tests.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
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
    ws.write_plan({"project_id": "aiwf", "version": 1, "tasks": [{"id": "T1", "status": "pending"}]})
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
    ws.write_plan({"project_id": "aiwf", "version": 1, "tasks": [{"id": "T1", "status": "pending"}]})
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
