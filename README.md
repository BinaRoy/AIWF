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
aiwf status
aiwf verify
aiwf validate-state
aiwf validate-artifacts
aiwf audit-summary
aiwf pr-status
```

## Repo structure
- `src/aiwf/` : framework code
- `.ai/` : project memory (created by `aiwf init`)
- `schemas/` : JSON Schemas for contracts
- `AGENTS.md` : how to use Codex CLI/agents in this repo

## PR-driven workflow (recommended/default)
- `aiwf pr-status` : show if current repo state is ready for PR-based development
- `aiwf pr-check` : same as above, but exits non-zero when not ready
- `aiwf verify` : when `git.require_pr: true`, verify will fail early unless:
  - repository has configured remote (default: `origin`)
  - current branch is not default branch (default: `main`)

Config lives in `.ai/config.yaml`:
```yaml
git:
  remote: origin
  default_branch: main
  require_pr: true
```

## Core command reference
- `aiwf status`: print current `.ai/state.json`
- `aiwf policy-check [--git] [paths...]`: evaluate changed paths against policy rules
- `aiwf validate-state`: validate `.ai/state.json` against `schemas/state.schema.json`
- `aiwf validate-artifacts`: validate latest run record and gate reports against schemas
- `aiwf audit-summary`: show stage, latest run result, gate counts, and latest policy decision
- `aiwf stage set <stage>`: set workflow stage with guardrails (`SHIP` and `DONE`)

## Standard development loop
```bash
# 1) sync before development
git fetch origin
git checkout <feature-branch>
git rebase origin/main
aiwf pr-check

# 2) implement + verify
pytest -q
aiwf verify
aiwf validate-state
aiwf validate-artifacts
aiwf audit-summary

# 3) ship via PR
git push -u origin <feature-branch>
# open PR to main, wait checks/review, then merge
```
