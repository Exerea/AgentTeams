# Architecture (v4)

## Overview

AgentTeams v4 is a TAKT-first orchestration architecture with a single execution source of truth.

### Core Principles

- One runtime authority: `.takt/`
- One task authority: `.takt/tasks/TASK-*.yaml`
- One governance piece: `.takt/pieces/agentteams-governance.yaml`
- No runtime fallback to legacy operation

## Topology

```text
.
├─ .takt/
│  ├─ config.yaml
│  ├─ pieces/
│  │  └─ agentteams-governance.yaml
│  ├─ personas/
│  ├─ policies/
│  ├─ knowledge/
│  ├─ output-contracts/
│  ├─ instructions/
│  ├─ tasks/
│  │  └─ TASK-*.yaml
│  └─ logs/
├─ scripts/
│  ├─ at.py
│  ├─ audit-takt-governance.py
│  ├─ validate-takt-task.py
│  └─ validate-takt-evidence.py
└─ legacy/
   └─ codex-states/
```

## Execution Flow

1. `agentteams orchestrate --task-file .takt/tasks/TASK-*.yaml`
2. `at.py` compiles task payload into TAKT prompt input.
3. TAKT executes `.takt/pieces/agentteams-governance.yaml`.
4. Post validation runs:
   - `validate-takt-task.py`
   - `validate-takt-evidence.py`
5. Governance audit is available through `agentteams audit`.

## Governance Distribution Model

Required team coverage is derived from task flags:

- `qa_required` -> `qa-review-guild`
- `security_required` -> `backend`
- `ux_required` -> `frontend`
- `docs_required` -> `documentation-guild`
- `research_required` -> `innovation-research-guild`

Audit checks required coverage and minimum distribution count.

## CI Contract

Required jobs:

- `validate-takt-task-linux`
- `validate-takt-task-windows`
- `validate-takt-evidence-linux`
- `orchestrate-smoke-mock`
- `validate-doc-consistency`
- `validate-secrets-linux`
