from __future__ import annotations

import platform
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Any

@dataclass
class GateSpec:
    name: str
    command: str
    timeout_seconds: int = 1800

@dataclass
class GateResult:
    name: str
    status: str  # pass/fail/skip
    command: Optional[str]
    exit_code: Optional[int]
    ts_start: str
    ts_end: str
    duration_seconds: float
    evidence: Dict[str, Any]
    metrics: Dict[str, Any]
    environment: Dict[str, Any]

class GateEngine:
    def __init__(self, reports_dir: Path):
        self.reports_dir = reports_dir
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def _env_info(self) -> Dict[str, Any]:
        return {"platform": platform.platform(), "python": platform.python_version()}

    def run(self, spec: GateSpec) -> GateResult:
        ts0 = datetime.now(timezone.utc).isoformat()
        t0 = time.time()
        exit_code = None
        try:
            proc = subprocess.run(
                spec.command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=spec.timeout_seconds,
            )
            exit_code = proc.returncode
            status = "pass" if exit_code == 0 else "fail"
            evidence = {
                "stdout_tail": (proc.stdout or "")[-4000:],
                "stderr_tail": (proc.stderr or "")[-4000:],
            }
        except subprocess.TimeoutExpired:
            status = "fail"
            evidence = {"stderr_tail": f"timeout after {spec.timeout_seconds}s"}

        ts1 = datetime.now(timezone.utc).isoformat()
        dt = time.time() - t0

        result = GateResult(
            name=spec.name,
            status=status,
            command=spec.command,
            exit_code=exit_code,
            ts_start=ts0,
            ts_end=ts1,
            duration_seconds=dt,
            evidence=evidence,
            metrics={},
            environment=self._env_info(),
        )
        self._write_json(spec.name, result.__dict__)
        return result

    def _write_json(self, name: str, data: Dict[str, Any]) -> None:
        import json
        out = self.reports_dir / f"{name}.json"
        out.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
