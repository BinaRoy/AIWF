from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from aiwf.cli.main import app
from aiwf.storage.ai_workspace import AIWorkspace


runner = CliRunner()


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
