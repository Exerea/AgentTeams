# AgentTeams v5 (TAKT-Only + Control Plane)

AgentTeams v5 keeps TAKT as the only runtime and adds a metadata-only fleet
control plane for cross-project detection and self-refresh proposals.

## Runtime Model

- Canonical runtime: `TAKT only`
- Canonical task source: `.takt/tasks/TASK-*.yaml`
- Canonical orchestration piece: `.takt/pieces/agentteams-governance.yaml`
- Fleet control plane: `.takt/control-plane/`
- Legacy historical task files: `legacy/codex-states/`
- Mandatory gate order: `team leaders -> QA -> overall leader`

## CLI

Supported commands:

- `agentteams init`
- `agentteams doctor`
- `agentteams orchestrate`
- `agentteams audit`

`agentteams audit` scopes:

- Local governance audit: `agentteams audit --scope local --strict`
- Fleet control-plane audit: `agentteams audit --scope fleet --strict`
- Default scope is local.

Removed commands:

- `agentteams sync`
- `agentteams report-incident`
- `agentteams guard-chat`

Removed commands return an explicit discontinued error in v5.

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

### 4. Audit Local/Fleet Governance

```bash
agentteams audit --scope local --strict
agentteams audit --scope fleet --strict
```

## Task Schema (v5)

```yaml
id: T-00140
title: final-code-review
status: todo # todo|in_progress|in_review|blocked|done
task: |
  Execution instruction body for TAKT
goal: ""
constraints: []
acceptance: []
routing:
  required_teams:
    - coordinator
    - documentation-guild
    - qa-review-guild
  capability_tags:
    - final-review
    - docs-sync
    - qa-review
warnings: []
declarations:
  - at: 2026-02-10T00:00:00Z
    team: coordinator
    role: coordinator
    action: triage
    what: "decompose task and assign required teams"
    controlled_by:
      - "piece:agentteams-governance"
      - "rule:default-routing"
      - "skill:skill-routing-governance"
handoffs: []
approvals:
  team_leader_gates:
    - team: coordinator
      leader_role: team-lead
      status: approved # pending|approved|rejected
      at: 2026-02-10T00:05:00Z
      note: "triage ownership accepted"
      controlled_by:
        - "piece:agentteams-governance"
        - "rule:team-leader-approval-required"
        - "skill:skill-team-leader-gate"
    - team: documentation-guild
      leader_role: team-lead
      status: approved
      at: 2026-02-10T00:06:00Z
      note: "docs path approved"
      controlled_by:
        - "piece:agentteams-governance"
        - "rule:team-leader-approval-required"
        - "skill:skill-team-leader-gate"
  qa_gate:
    by: qa-review-guild/lead-reviewer
    status: approved
    at: 2026-02-10T00:08:00Z
    note: "qa checks passed"
    controlled_by:
      - "piece:agentteams-governance"
      - "rule:qa-required"
      - "skill:skill-qa-regression-trace"
  leader_gate:
    by: leader/overall-lead
    status: pending
    at: 2026-02-10T00:09:00Z
    note: "awaiting final decision"
    controlled_by:
      - "piece:agentteams-governance"
      - "rule:default-routing"
      - "skill:skill-routing-governance"
notes: ""
updated_at: 2026-02-10T00:00:00Z
```

Approval policy:

- Team leader approvals for all required teams are mandatory before QA.
- QA approval is mandatory before overall leader approval.
- Any rejection must route back to execute with explicit rework declaration evidence.

Schema policy:

- tasks must define `routing.required_teams` and `routing.capability_tags`
- legacy review fields are unsupported

## Control Plane Operation

- Intake source: `.takt/control-plane/intake/<project_id>/YYYYMMDDTHHMMSSZ.yaml`
- Aggregated signals: `.takt/control-plane/signals/latest.yaml`
- Queue/proposals:
  - `.takt/control-plane/refresh-queue/R-*.yaml`
  - `.takt/control-plane/refresh-proposals/RP-*.md`
- Team/rule/skill catalogs:
  - `.takt/control-plane/team-catalog/teams.yaml`
  - `.takt/control-plane/rule-catalog/routing-rules.yaml`
  - `.takt/control-plane/skill-catalog/skills.yaml`

Detection mode:

- Event-driven only (no periodic schedule required)
- Triggered only by intake updates (`push` on `.takt/control-plane/intake/**`)
- Workflow guard variables:
  - `AGENTTEAMS_CONTROL_PLANE_ENABLED=true`
  - `AGENTTEAMS_CONTROL_PLANE_MODE=hub`
- Set these only in the central AgentTeams repository

## Validation

Repository validation scripts:

- Linux: `bash ./scripts/validate-repo.sh`
- Windows: `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate-repo.ps1`

Main checks:

- `validate-takt-task.py`
- `validate-takt-evidence.py`
- `validate-control-plane-schema.py`
- `validate-doc-consistency.py`
- `validate-scenarios-structure.py`
- `validate-secrets.sh/.ps1`

## CI Required Checks (v5)

- `validate-takt-task-linux`
- `validate-takt-task-windows`
- `validate-takt-evidence-linux`
- `validate-control-plane-schema`
- `validate-intake-pr-paths`
- `orchestrate-smoke-mock`
- `validate-doc-consistency`
- `validate-secrets-linux`

## Guides

- `docs/guides/architecture.md`
- `docs/guides/request-routing-scenarios.md`
- `docs/guides/takt-orchestration.md`

## Notes

- Runtime behavior must not depend on assets under `legacy/`.
- Fleet control plane stores metadata only; source/session full text is out of scope.
