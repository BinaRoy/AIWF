# AIWF Current Architecture Baseline

Date: 2026-03-06

## 1. System Goal

AIWF is a CLI-first workflow framework that enforces deterministic and auditable development loops with:
- Workspace state in `.ai/`
- Explicit JSON schema contracts
- Configurable gate execution
- Policy constraints on changed paths
- Append-only telemetry events

## 2. Layered Architecture

### 2.1 CLI Layer
- File: `src/aiwf/cli/main.py`
- Role: command entrypoint and user-facing output.
- Commands:
  - `init`: create `.ai` workspace layout
  - `verify`: run orchestrated verification flow
  - `status`: print `.ai/state.json`
  - `policy-check`: evaluate paths against policy rules
  - `validate-state`: validate state payload against schema

### 2.2 Orchestration Layer
- File: `src/aiwf/orchestrator/workflow_engine.py`
- Role: coordinate full `VERIFY` stage.
- Responsibilities:
  - load config and schemas
  - open run and emit telemetry events
  - perform policy check from git changed paths
  - execute configured gates
  - persist run record and update state

### 2.3 Capability Layer
- Workspace storage: `src/aiwf/storage/ai_workspace.py`
- Policy engine: `src/aiwf/policy/policy_engine.py`
- Gate engine: `src/aiwf/gate/gate_engine.py`
- Schema validator: `src/aiwf/schema/json_validator.py`
- Telemetry sink: `src/aiwf/telemetry/sink.py`

## 3. Runtime Data Flow

`aiwf verify` flow:
1. Ensure `.ai` layout exists.
2. Emit `run_started` event.
3. Collect git changed paths.
4. Evaluate path policy.
5. If denied, finish run as failure.
6. If allowed, execute each configured gate command.
7. Validate gate and run payloads with schemas.
8. Persist artifacts and run record.
9. Update `.ai/state.json`.
10. Emit `run_finished` event.

## 4. Data Contracts

- `schemas/state.schema.json`: current workflow stage and state metadata.
- `schemas/gate_result.schema.json`: required gate output fields.
- `schemas/run_record.schema.json`: required run record fields.
- `schemas/plan.schema.json`: future task plan structure.

## 5. Known Constraints

- Policy evaluation is path-based only (no semantic change analysis).
- Gate execution is serial and shell-based.
- Telemetry sink is local JSONL only.
- `verify` enforces policy only when git reports changed files.

## 6. Extension Seams (Next Phase)

- Add richer policy checks (ownership, file type, change intent).
- Introduce retry and optional parallel gate execution strategy.
- Add schema validation command coverage for run/gate artifacts.
- Add CI-friendly exit semantics and stable report aggregation.
