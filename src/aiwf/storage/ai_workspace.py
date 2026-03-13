from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

import yaml

DEFAULT_CONFIG_YAML = """# AIWF configuration
# Add gate commands below. Each gate is a shell command that exits 0 on success.
# Example:
#   gates:
#     unit_tests: "pytest -q"
#     lint: "ruff check src"
gates: {}
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
        (self.ai_dir / "tasks").mkdir(parents=True, exist_ok=True)
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
                        "version": "0.2",
                        "current_task": None,
                        "last_run_id": None,
                        "last_run_result": None,
                        "task_counts": {
                            "total": 0,
                            "defined": 0,
                            "in_progress": 0,
                            "done": 0,
                            "failed": 0,
                            "blocked": 0,
                        },
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

