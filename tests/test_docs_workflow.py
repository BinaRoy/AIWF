from __future__ import annotations

import re
from pathlib import Path


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
