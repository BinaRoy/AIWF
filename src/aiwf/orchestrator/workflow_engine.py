from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from aiwf.gate.gate_engine import GateEngine, GateSpec
from aiwf.policy.policy_engine import PolicyEngine
from aiwf.schema.json_validator import load_schema, validate_payload
from aiwf.storage.ai_workspace import AIWorkspace
from aiwf.storage.dispatch_artifacts import ensure_dispatch_record, has_unresolved_blocked_items
from aiwf.telemetry.sink import TelemetrySink
from aiwf.vcs.pr_workflow import evaluate_pr_workflow


def _run_id() -> str:
    return datetime.now(timezone.utc).strftime("run_%Y%m%d_%H%M%S")


class ContractError(ValueError):
    """Raised when develop input/workspace contract is invalid."""


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

    def verify(
        self,
        *,
        run_id: Optional[str] = None,
        run_stage: str = "VERIFY",
        write_run_record: bool = True,
        update_state_stage: bool = True,
    ) -> Dict[str, Any]:
        cfg = self.ws.read_config()
        gates_cfg = (cfg.get("gates") or {})
        resolved_run_id = run_id or _run_id()
        reports_dir = self.ws.ai_dir / "artifacts" / "reports" / resolved_run_id
        gate_engine = GateEngine(reports_dir=reports_dir)
        gate_schema = load_schema(self.repo_root, "gate_result.schema.json")
        run_schema = load_schema(self.repo_root, "run_record.schema.json")
        self.telemetry.emit("run_started", {"stage": run_stage, "run_type": "verify"}, run_id=resolved_run_id)

        def finalize_run(ok: bool, results: Dict[str, Any]) -> Dict[str, Any]:
            result_status = "success" if ok else "failure"
            gate_reports = [
                f".ai/artifacts/reports/{resolved_run_id}/{gate_name}.json" for gate_name in results.keys()
            ]
            run_record = {
                "run_id": resolved_run_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "stage": run_stage,
                "run_type": "verify",
                "result": result_status,
                "ok": ok,
                "results": results,
                "artifacts": {
                    "run_record": f".ai/runs/{resolved_run_id}/run.json",
                    "gate_reports": gate_reports,
                    "telemetry": ".ai/telemetry/events.jsonl",
                },
            }
            if write_run_record:
                validate_payload(run_record, run_schema)
                run_dir = self.ws.ai_dir / "runs" / resolved_run_id
                run_dir.mkdir(parents=True, exist_ok=True)
                (run_dir / "run.json").write_text(
                    json.dumps(run_record, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )

            state = self.ws.read_state()
            if update_state_stage:
                state["stage"] = "VERIFY"
            state["last_run_id"] = resolved_run_id
            state["last_run_type"] = "verify"
            state["last_run_result"] = result_status
            state["gates"] = results
            self.ws.write_state(state)

            self.telemetry.emit("run_finished", {"stage": run_stage, "ok": ok, "run_type": "verify"}, run_id=resolved_run_id)
            return {"run_id": resolved_run_id, "ok": ok, "results": results}

        git_cfg = (cfg.get("git") or {})
        if bool(git_cfg.get("require_pr", False)):
            pr_check = evaluate_pr_workflow(self.repo_root, cfg).to_dict()
            self.telemetry.emit("pr_check", pr_check, run_id=resolved_run_id)
            if not pr_check["ok"]:
                return finalize_run(ok=False, results={})

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
                run_id=resolved_run_id,
            )
            if not decision.allowed:
                return finalize_run(ok=False, results={})

        if not gates_cfg:
            self.telemetry.emit(
                "no_gates_configured",
                {"reason": "No gates configured in .ai/config.yaml"},
                run_id=resolved_run_id,
            )
            return finalize_run(ok=False, results={})

        results: Dict[str, Any] = {}
        ok = True
        for name, cmd in gates_cfg.items():
            res = gate_engine.run(GateSpec(name=name, command=str(cmd)), run_id=resolved_run_id)
            gate_payload = res.__dict__
            validate_payload(gate_payload, gate_schema)
            results[name] = gate_payload
            self.telemetry.emit("gate_result", {"name": name, "status": res.status}, run_id=resolved_run_id)
            if res.status != "pass":
                ok = False

        return finalize_run(ok=ok, results=results)

    def develop(
        self,
        *,
        run_verify: bool = True,
        sync_roles: bool = True,
        strict_plan: bool = True,
        run_id: Optional[str] = None,
        roles_sync: Optional[Callable[[str], Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        resolved_run_id = run_id or _run_id()
        mode = "full" if run_verify else "preflight"
        verified = False
        steps: Dict[str, Any] = {}
        run_schema = load_schema(self.repo_root, "run_record.schema.json")
        develop_schema = load_schema(self.repo_root, "develop_record.schema.json")

        def write_run_files(ok: bool, result: str, error: Optional[dict] = None) -> Dict[str, Any]:
            run_dir = self.ws.ai_dir / "runs" / resolved_run_id
            run_dir.mkdir(parents=True, exist_ok=True)
            dispatch_record = f".ai/runs/{resolved_run_id}/dispatch.json"

            gate_reports: list[str] = []
            verify_step = steps.get("verify") or {}
            verify_results = verify_step.get("results") if isinstance(verify_step, dict) else {}
            if isinstance(verify_results, dict):
                for gate_name in verify_results.keys():
                    gate_reports.append(f".ai/artifacts/reports/{resolved_run_id}/{gate_name}.json")

            run_record = {
                "run_id": resolved_run_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "stage": "DEVELOP",
                "run_type": "develop",
                "mode": mode,
                "verified": verified,
                "result": result,
                "ok": ok,
                "steps": steps,
                "artifacts": {
                    "run_record": f".ai/runs/{resolved_run_id}/run.json",
                    "develop_record": f".ai/runs/{resolved_run_id}/develop.json",
                    "dispatch_record": dispatch_record,
                    "gate_reports": gate_reports,
                    "telemetry": ".ai/telemetry/events.jsonl",
                },
            }
            validate_payload(run_record, run_schema)
            (run_dir / "run.json").write_text(
                json.dumps(run_record, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

            develop_record = {
                "run_id": resolved_run_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "mode": mode,
                "verified": verified,
                "ok": ok,
                "steps": steps,
                "artifacts": {
                    "run_record": f".ai/runs/{resolved_run_id}/run.json",
                    "develop_record": f".ai/runs/{resolved_run_id}/develop.json",
                    "dispatch_record": dispatch_record,
                    "gate_reports": gate_reports,
                    "telemetry": ".ai/telemetry/events.jsonl",
                },
            }
            if error:
                develop_record["error"] = error
            validate_payload(develop_record, develop_schema)
            (run_dir / "develop.json").write_text(
                json.dumps(develop_record, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            return {
                "run_id": resolved_run_id,
                "ok": ok,
                "verified": verified,
                "mode": mode,
                "steps": steps,
                "artifacts": develop_record["artifacts"],
            }

        self.telemetry.emit(
            "develop_started",
            {
                "mode": mode,
                "strict_plan": strict_plan,
                "sync_roles": sync_roles,
                "verify_enabled": run_verify,
            },
            run_id=resolved_run_id,
        )
        try:
            ensure_dispatch_record(self.ws, self.repo_root, resolved_run_id)
            if strict_plan:
                plan = self.ws.read_plan()
                if plan is None:
                    raise ContractError("Missing .ai/plan.json")
                validate_payload(plan, load_schema(self.repo_root, "plan.schema.json"))
                steps["plan"] = {"ok": True}
            else:
                steps["plan"] = {"ok": True, "skipped": True}
            self.telemetry.emit("develop_step", {"name": "plan", "ok": bool(steps["plan"]["ok"])}, run_id=resolved_run_id)

            if sync_roles:
                if roles_sync is None:
                    raise ContractError("Missing roles sync handler")
                role_result = roles_sync(resolved_run_id)
                if not isinstance(role_result, dict):
                    role_result = {"ok": False, "error": "Invalid roles sync result"}
                steps["roles_sync"] = role_result
            else:
                steps["roles_sync"] = {"ok": True, "skipped": True}
            self.telemetry.emit(
                "develop_step",
                {"name": "roles_sync", "ok": bool((steps["roles_sync"] or {}).get("ok"))},
                run_id=resolved_run_id,
            )
            if not bool((steps["roles_sync"] or {}).get("ok")):
                out = write_run_files(ok=False, result="failure")
                self.telemetry.emit("develop_finished", {"ok": False, "verified": False, "mode": mode}, run_id=resolved_run_id)
                state = self.ws.read_state()
                state["last_run_id"] = resolved_run_id
                state["last_run_type"] = "develop"
                state["last_run_result"] = "failure"
                self.ws.write_state(state)
                return out

            if run_verify:
                verify_out = self.verify(
                    run_id=resolved_run_id,
                    run_stage="DEVELOP",
                    write_run_record=False,
                    update_state_stage=False,
                )
                verified = bool(verify_out.get("ok"))
                steps["verify"] = verify_out
                self.telemetry.emit("develop_step", {"name": "verify", "ok": verified}, run_id=resolved_run_id)
                if not verified:
                    out = write_run_files(ok=False, result="failure")
                    self.telemetry.emit(
                        "develop_finished",
                        {"ok": False, "verified": False, "mode": mode},
                        run_id=resolved_run_id,
                    )
                    state = self.ws.read_state()
                    state["last_run_id"] = resolved_run_id
                    state["last_run_type"] = "develop"
                    state["last_run_result"] = "failure"
                    self.ws.write_state(state)
                    return out
            else:
                steps["verify"] = {"ok": True, "skipped": True, "verified": False}
                self.telemetry.emit("develop_step", {"name": "verify", "ok": True, "skipped": True}, run_id=resolved_run_id)

            if has_unresolved_blocked_items(self.ws, self.repo_root, resolved_run_id):
                steps["dispatch"] = {"ok": False, "error": "Unresolved blocked work items in dispatch record"}
                out = write_run_files(ok=False, result="failure")
                state = self.ws.read_state()
                state["last_run_id"] = resolved_run_id
                state["last_run_type"] = "develop"
                state["last_run_result"] = "failure"
                self.ws.write_state(state)
                self.telemetry.emit(
                    "develop_finished",
                    {"ok": False, "verified": verified, "mode": mode, "error": "dispatch_blocked"},
                    run_id=resolved_run_id,
                )
                return out

            result = "success" if run_verify else "partial"
            out = write_run_files(ok=True, result=result)
            state = self.ws.read_state()
            state["stage"] = "DEV"
            state["last_run_id"] = resolved_run_id
            state["last_run_type"] = "develop"
            state["last_run_result"] = result
            self.ws.write_state(state)
            self.telemetry.emit(
                "develop_finished",
                {"ok": True, "verified": verified, "mode": mode},
                run_id=resolved_run_id,
            )
            return out
        except ContractError as exc:
            steps["contract_error"] = {"ok": False, "error": str(exc)}
            write_run_files(
                ok=False,
                result="failure",
                error={"type": exc.__class__.__name__, "message": str(exc)},
            )
            state = self.ws.read_state()
            state["last_run_id"] = resolved_run_id
            state["last_run_type"] = "develop"
            state["last_run_result"] = "failure"
            self.ws.write_state(state)
            self.telemetry.emit(
                "develop_finished",
                {"ok": False, "verified": False, "mode": mode, "error": exc.__class__.__name__},
                run_id=resolved_run_id,
            )
            raise
        except Exception as exc:
            steps["runtime_error"] = {"ok": False, "error": str(exc)}
            out = write_run_files(
                ok=False,
                result="failure",
                error={"type": exc.__class__.__name__, "message": str(exc)},
            )
            state = self.ws.read_state()
            state["last_run_id"] = resolved_run_id
            state["last_run_type"] = "develop"
            state["last_run_result"] = "failure"
            self.ws.write_state(state)
            self.telemetry.emit(
                "develop_finished",
                {"ok": False, "verified": False, "mode": mode, "error": exc.__class__.__name__},
                run_id=resolved_run_id,
            )
            return out
