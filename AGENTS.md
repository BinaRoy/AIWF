# Agent guide (Codex / other coding agents)

This repo is designed for agentic development with **strict contracts**.

## Operating rules
1. **Read before write.** Inspect existing files before changing anything.
2. **Patch-first changes.** Propose a unified diff patch first; apply via framework logic.
3. **Everything is recorded.**
   - Each run writes `.ai/runs/<run_id>/run.json` (future step)
   - Gates write `.ai/artifacts/reports/<gate>.json`
   - Telemetry writes `.ai/telemetry/events.jsonl`
4. **Small diffs.** Prefer minimal, high-confidence changes.

## Using Codex CLI
- Install: `npm i -g @openai/codex`
- Run (in this folder): `codex`
- First run prompts sign-in.

Docs: OpenAI Codex CLI setup and reference.
