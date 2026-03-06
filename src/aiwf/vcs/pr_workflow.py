from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class PRWorkflowCheck:
    ok: bool
    in_git_repo: bool
    remote: str
    default_branch: str
    branch: Optional[str]
    remote_exists: bool
    reasons: list[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "in_git_repo": self.in_git_repo,
            "remote": self.remote,
            "default_branch": self.default_branch,
            "branch": self.branch,
            "remote_exists": self.remote_exists,
            "reasons": self.reasons,
        }


def _run_git(repo_root: Path, args: list[str]) -> tuple[int, str]:
    proc = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    return proc.returncode, (proc.stdout or "").strip()


def evaluate_pr_workflow(repo_root: Path, cfg: Dict[str, Any]) -> PRWorkflowCheck:
    git_cfg = (cfg.get("git") or {})
    remote = str(git_cfg.get("remote", "origin"))
    default_branch = str(git_cfg.get("default_branch", "main"))
    reasons: list[str] = []

    rc, inside = _run_git(repo_root, ["rev-parse", "--is-inside-work-tree"])
    in_git_repo = rc == 0 and inside == "true"
    branch: Optional[str] = None
    remote_exists = False
    if not in_git_repo:
        reasons.append("Not a git repository")
    else:
        _, branch_name = _run_git(repo_root, ["rev-parse", "--abbrev-ref", "HEAD"])
        branch = branch_name or None
        _, remotes = _run_git(repo_root, ["remote"])
        remote_exists = remote in remotes.splitlines()

        if not remote_exists:
            reasons.append(f"Missing remote: {remote}")
        if branch == default_branch:
            reasons.append(f"On default branch: {default_branch}")

    return PRWorkflowCheck(
        ok=len(reasons) == 0,
        in_git_repo=in_git_repo,
        remote=remote,
        default_branch=default_branch,
        branch=branch,
        remote_exists=remote_exists,
        reasons=reasons,
    )
