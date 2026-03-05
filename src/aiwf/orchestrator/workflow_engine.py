from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from aiwf.gate.gate_engine import GateEngine, GateSpec
from aiwf.schema.json_validator import load_schema, validate_payload
from aiwf.storage.ai_workspace import AIWorkspace
from aiwf.telemetry.sink import TelemetrySink

def _run_id() -> str:
    return datetime.now(timezone.utc).strftime("run_%Y%m%d_%H%M%S")

@dataclass
class WorkflowEngine:
    repo_root: Path
    ws: AIWorkspace
    telemetry: TelemetrySink

    def verify(self) -> Dict[str, Any]:
        cfg = self.ws.read_config()
        gates_cfg = (cfg.get("gates") or {})
        reports_dir = self.ws.ai_dir / "artifacts" / "reports"
        gate_engine = GateEngine(reports_dir=reports_dir)
        gate_schema = load_schema(self.repo_root, "gate_result.schema.json")
        run_schema = load_schema(self.repo_root, "run_record.schema.json")

        run_id = _run_id()
        self.telemetry.emit("run_started", {"stage": "VERIFY"}, run_id=run_id)

        results: Dict[str, Any] = {}
        ok = True
        for name, cmd in gates_cfg.items():
            res = gate_engine.run(GateSpec(name=name, command=str(cmd)))
            gate_payload = res.__dict__
            validate_payload(gate_payload, gate_schema)
            results[name] = gate_payload
            self.telemetry.emit("gate_result", {"name": name, "status": res.status}, run_id=run_id)
            if res.status != "pass":
                ok = False

        result_status = "success" if ok else "failure"
        run_record = {
            "run_id": run_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "stage": "VERIFY",
            "result": result_status,
            "ok": ok,
            "results": results,
        }
        validate_payload(run_record, run_schema)
        run_dir = self.ws.ai_dir / "runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "run.json").write_text(
            json.dumps(run_record, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        state = self.ws.read_state()
        state["stage"] = "VERIFY"
        state["last_run_id"] = run_id
        state["gates"] = results
        self.ws.write_state(state)

        self.telemetry.emit("run_finished", {"stage": "VERIFY", "ok": ok}, run_id=run_id)
        return {"run_id": run_id, "ok": ok, "results": results}
