from __future__ import annotations

import json
import subprocess
from pathlib import Path

from typer.testing import CliRunner

from aiwf.cli.main import app
from aiwf.storage.ai_workspace import AIWorkspace


runner = CliRunner()


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=cwd, text=True, check=True, capture_output=True)


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
