from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from aiwf.gate.gate_engine import GateEngine, GateSpec
from aiwf.policy.policy_engine import PolicyEngine
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

    def _git_changed_paths(self) -> list[str]:
        proc = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=self.repo_root,
            text=True,
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0:
            return []

        paths: list[str] = []
        for line in proc.stdout.splitlines():
            if len(line) < 4:
                continue
            raw = line[3:]
            if " -> " in raw:
                raw = raw.split(" -> ", 1)[1]
            paths.append(raw)
        return paths

    def verify(self) -> Dict[str, Any]:
        cfg = self.ws.read_config()
        gates_cfg = (cfg.get("gates") or {})
        reports_dir = self.ws.ai_dir / "artifacts" / "reports"
        gate_engine = GateEngine(reports_dir=reports_dir)
        gate_schema = load_schema(self.repo_root, "gate_result.schema.json")
        run_schema = load_schema(self.repo_root, "run_record.schema.json")

        run_id = _run_id()
        self.telemetry.emit("run_started", {"stage": "VERIFY"}, run_id=run_id)

        def finalize_run(ok: bool, results: Dict[str, Any]) -> Dict[str, Any]:
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

        changed_paths = self._git_changed_paths()
        if changed_paths:
            decision = PolicyEngine(cfg).decide(changed_paths)
            self.telemetry.emit(
                "policy_check",
                {
                    "allowed": decision.allowed,
                    "requires_approval": decision.requires_approval,
                    "requires_adr": decision.requires_adr,
                    "reason": decision.reason,
                    "paths": changed_paths,
                },
                run_id=run_id,
            )
            if not decision.allowed:
                return finalize_run(ok=False, results={})

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

        return finalize_run(ok=ok, results=results)
