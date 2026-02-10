# AgentTeams v4 (TAKT-Only Runtime)

AgentTeams v4 is a destructive migration to a single runtime source of truth based on TAKT.

## Runtime Model

- Canonical runtime: `TAKT only`
- Canonical task source: `.takt/tasks/TASK-*.yaml`
- Canonical orchestration piece: `.takt/pieces/agentteams-governance.yaml`
- Legacy historical task files: `legacy/codex-states/`

## CLI

Supported commands:

- `agentteams init`
- `agentteams doctor`
- `agentteams orchestrate`
- `agentteams audit`

Removed commands:

- `agentteams sync`
- `agentteams report-incident`
- `agentteams guard-chat`

Removed commands return an explicit discontinued error in v4.

## Install Prerequisites

- Git
- Python 3.9+
- TAKT (`npm install -g takt`)
- PyYAML (`python -m pip install pyyaml`)

## Quick Start

### 1. Initialize Current Repository

```bash
agentteams init --here
```

### 2. Run Health Check

```bash
agentteams doctor
```

### 3. Orchestrate a Task

```bash
agentteams orchestrate --task-file .takt/tasks/TASK-00140-final-code-review.yaml
```

Mock smoke execution:

```bash
agentteams orchestrate --task-file .takt/tasks/TASK-00140-final-code-review.yaml --provider mock --no-post-validate
```

### 4. Audit Governance Distribution

```bash
agentteams audit --strict
```

## Task Schema (v4)

```yaml
id: T-00140
title: final-code-review
status: todo # todo|in_progress|in_review|blocked|done
task: |
  Execution instruction body for TAKT
goal: ""
constraints: []
acceptance: []
flags:
  qa_required: true
  security_required: false
  ux_required: false
  docs_required: true
  research_required: false
warnings: []
handoffs: []
notes: ""
updated_at: 2026-02-10T00:00:00Z
```

## Validation

Repository validation scripts:

- Linux: `bash ./scripts/validate-repo.sh`
- Windows: `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate-repo.ps1`

Main checks:

- `validate-takt-task.py`
- `validate-takt-evidence.py`
- `validate-doc-consistency.py`
- `validate-scenarios-structure.py`
- `validate-secrets.sh/.ps1`

## CI Required Checks (v4)

- `validate-takt-task-linux`
- `validate-takt-task-windows`
- `validate-takt-evidence-linux`
- `orchestrate-smoke-mock`
- `validate-doc-consistency`
- `validate-secrets-linux`

## Guides

- `docs/guides/architecture.md`
- `docs/guides/request-routing-scenarios.md`
- `docs/guides/takt-orchestration.md`

## Notes

- Runtime behavior must not depend on assets under `legacy/`.
- Backward compatibility with pre-v4 operation is intentionally dropped.
