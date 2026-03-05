# AIWF (AI Workflow Framework) — CLI-first workflow framework (MVP scaffold)

This repo is a **starter scaffold** for building a general-purpose workflow framework that:
- externalizes "project memory" into `.ai/`
- uses **schemas + artifacts + gates + telemetry** to enforce deterministic, auditable workflows
- allows an **AI executor** to generate changes under policy constraints
- is designed to later integrate with Git / CI / Dashboard sinks

## Quickstart (local)
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
aiwf init
aiwf verify
```

## Repo structure
- `src/aiwf/` : framework code
- `.ai/` : project memory (created by `aiwf init`)
- `schemas/` : JSON Schemas for contracts
- `AGENTS.md` : how to use Codex CLI/agents in this repo
