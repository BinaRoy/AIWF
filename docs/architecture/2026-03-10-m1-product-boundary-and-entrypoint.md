# AIWF M1 Product Boundary and Primary Entry Point

Date: 2026-03-10

## Purpose

This note records the current product definition after runtime-core convergence.
It keeps README, guides, CI, and process docs aligned on what AIWF M1 is, and what it is not.

## Product Boundary

AIWF M1 is a CLI-first workflow runtime for AI-assisted software development with a narrow scope:

- workspace initialization
- workflow global state
- basic development loop
- verification gates
- artifact recording

This is enough to support the current scaffold and self-hosted usage model.
It is not a claim that AIWF is already a general-purpose integration platform for arbitrary repositories.

## Supported Framing

Current supported framing:

- Python self-hosted repository
- `.ai/` workspace accepted as local process state
- git / PR workflow required
- JSON schema contracts enforced
- gate commands expressed as local shell commands, with pytest-style defaults in self-hosted examples

Avoid stronger framing such as:

- universal project onboarding
- generic plugin platform
- complete governance operating system
- full multi-agent orchestration engine

## Primary Entry Point

For M1, the only primary closed-loop entry point is:

```bash
aiwf develop
```

Supporting commands:

- `aiwf verify`: low-level gate executor; can run independently, but is not the primary closed-loop command
- `aiwf roles autopilot`: helper for role-state progression; not the primary release gate

## Roles Positioning

Current `roles` capability should be described as:

- role-state governance
- evidence mapping
- machine-checkable collaboration status

It should not yet be described as configurable multi-role orchestration unless handoff/work-item/transition models are added later.
