from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatch
from typing import Dict, List

@dataclass
class PolicyDecision:
    allowed: bool
    requires_approval: bool
    requires_adr: bool
    reason: str

class PolicyEngine:
    def __init__(self, cfg: Dict):
        paths = (cfg.get("paths") or {})
        self.allow = paths.get("allow") or []
        self.deny = paths.get("deny") or []
        self.require_approval = paths.get("require_approval") or []
        self.require_adr = paths.get("require_adr") or []

    def _match_any(self, path: str, patterns: List[str]) -> bool:
        return any(fnmatch(path, pat) for pat in patterns)

    def decide(self, changed_paths: List[str]) -> PolicyDecision:
        for p in changed_paths:
            if self._match_any(p, self.deny):
                return PolicyDecision(False, False, False, f"Denied by policy: {p}")
            if self.allow and not self._match_any(p, self.allow):
                return PolicyDecision(False, False, False, f"Not in allowlist: {p}")

        needs_approval = any(self._match_any(p, self.require_approval) for p in changed_paths)
        needs_adr = any(self._match_any(p, self.require_adr) for p in changed_paths)
        return PolicyDecision(True, needs_approval, needs_adr, "OK")
