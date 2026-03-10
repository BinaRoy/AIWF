from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from aiwf.storage.ai_workspace import AIWorkspace


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=cwd, text=True, check=True, capture_output=True)


def _copy_schemas(repo_root: Path) -> None:
    src_schemas = Path(__file__).resolve().parents[1] / "schemas"
    shutil.copytree(src_schemas, repo_root / "schemas")


def test_evaluate_self_check_reads_last_run_artifacts_and_pr_state(tmp_path: Path) -> None:
    from aiwf.runtime.checks import evaluate_self_check

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
    _git(tmp_path, "checkout", "-b", "feat/runtime-checks")

    run_id = "run_1"
    (ws.ai_dir / "runs" / run_id).mkdir(parents=True, exist_ok=True)
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
    state = ws.read_state()
    state["last_run_id"] = run_id
    ws.write_state(state)

    out = evaluate_self_check(tmp_path, ws, ws.read_config(), state)

    assert out["ok"] is True
    assert out["checks"]["pr_workflow"]["ok"] is True
    assert out["checks"]["artifacts"]["run_id"] == run_id
    assert out["checks"]["last_run_success"]["ok"] is True
    assert out["run_payload"]["run_id"] == run_id


def test_evaluate_loop_check_reuses_self_check_run_payload(tmp_path: Path) -> None:
    from aiwf.runtime.checks import evaluate_loop_check

    ws = AIWorkspace(tmp_path)
    ws.ensure_layout()
    state = ws.read_state()
    state["stage"] = "DEV"
    ws.write_state(state)

    cfg = {
        "process_policy": {
            "fixed_loop": {
                "enabled": True,
                "required_stage": "DEV",
                "required_gates": ["unit_tests", "self_check"],
            }
        }
    }
    self_eval = {
        "checks": {
            "pr_workflow": {"ok": True},
            "state_schema": {"ok": True},
            "artifacts": {"ok": True, "run_id": "run_1", "gate_reports": 1},
            "last_run_success": {"ok": True, "result": "success"},
        },
        "run_payload": {
            "result": "success",
            "results": {
                "unit_tests": {"status": "pass"},
                "self_check": {"status": "pass"},
            },
        },
    }

    out = evaluate_loop_check(cfg, state, self_eval)

    assert out["ok"] is True
    assert out["checks"]["required_stage"]["ok"] is True
    assert out["checks"]["required_gates"]["ok"] is True


def test_fixed_loop_policy_defaults_required_stage_to_dev() -> None:
    from aiwf.runtime.checks import fixed_loop_policy

    out = fixed_loop_policy({"process_policy": {"fixed_loop": {"enabled": True}}})

    assert out["required_stage"] == "DEV"
