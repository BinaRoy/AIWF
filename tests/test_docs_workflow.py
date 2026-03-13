from __future__ import annotations

import re
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_current_workflow_docs_exist() -> None:
    assert (REPO_ROOT / "docs" / "current" / "module-task-list.md").exists()
    assert (REPO_ROOT / "docs" / "current" / "current-work-state.md").exists()


def test_agents_read_chain_references_current_workflow_docs() -> None:
    agents = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")

    assert "docs/current/module-task-list.md" in agents
    assert "docs/current/current-work-state.md" in agents


def test_current_work_state_references_existing_task() -> None:
    module_list = REPO_ROOT / "docs" / "current" / "module-task-list.md"
    work_state = REPO_ROOT / "docs" / "current" / "current-work-state.md"

    module_text = module_list.read_text(encoding="utf-8")
    state_text = work_state.read_text(encoding="utf-8")

    match = re.search(r"recommended_next_task:\s*`([^`]+)`", state_text)
    assert match is not None
    assert match.group(1) in module_text


def test_pyproject_matches_current_packaging_contract() -> None:
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert 'requires = ["setuptools>=64", "wheel"]' in pyproject
    assert "[tool.setuptools]" in pyproject
    assert 'package-dir = {"" = "src"}' in pyproject
    assert "[tool.setuptools.packages.find]" in pyproject
    assert 'where = ["src"]' in pyproject


def test_ci_workflow_runs_aiwf_smoke_commands() -> None:
    workflow = yaml.safe_load(
        (REPO_ROOT / ".github" / "workflows" / "aiwf-verify.yml").read_text(encoding="utf-8")
    )
    run_steps = [
        step.get("run", "")
        for step in workflow["jobs"]["verify"]["steps"]
        if isinstance(step, dict)
    ]
    combined = "\n".join(run_steps)

    assert "aiwf init" in combined
    assert "aiwf verify" in combined
