from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

DEFAULT_CONFIG_YAML = """workflow_version: "0.1"
gates: {}
paths:
  allow:
    - "src/**"
  deny:
    - ".git/**"
    - ".ai/**"
  require_approval:
    - "ci/**"
  require_adr:
    - "ci/**"
telemetry:
  enabled: true
"""

@dataclass
class AIWorkspace:
    root: Path

    @property
    def ai_dir(self) -> Path:
        return self.root / ".ai"

    def ensure_layout(self) -> None:
        (self.ai_dir / "artifacts" / "reports").mkdir(parents=True, exist_ok=True)
        (self.ai_dir / "memory" / "adr").mkdir(parents=True, exist_ok=True)
        (self.ai_dir / "runs").mkdir(parents=True, exist_ok=True)
        (self.ai_dir / "telemetry").mkdir(parents=True, exist_ok=True)

        cfg = self.ai_dir / "config.yaml"
        if not cfg.exists():
            cfg.write_text(DEFAULT_CONFIG_YAML, encoding="utf-8")

        state = self.ai_dir / "state.json"
        if not state.exists():
            state.write_text(
                json.dumps(
                    {
                        "workflow_version": "0.1",
                        "stage": "INIT",
                        "current_task": None,
                        "branch": None,
                        "last_run_id": None,
                        "retry_count": 0,
                        "gates": {},
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

    def read_state(self) -> Dict[str, Any]:
        return json.loads((self.ai_dir / "state.json").read_text(encoding="utf-8"))

    def write_state(self, state: Dict[str, Any]) -> None:
        (self.ai_dir / "state.json").write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

    def read_config(self) -> Dict[str, Any]:
        return yaml.safe_load((self.ai_dir / "config.yaml").read_text(encoding="utf-8")) or {}

    def read_plan(self) -> Optional[Dict[str, Any]]:
        p = self.ai_dir / "plan.json"
        if not p.exists():
            return None
        return json.loads(p.read_text(encoding="utf-8"))

    def write_plan(self, plan: Dict[str, Any]) -> None:
        (self.ai_dir / "plan.json").write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
