# Architecture (v5)

## Overview

AgentTeams v5 is a TAKT-first orchestration architecture with:

- local task governance runtime
- metadata-only fleet control plane
- event-driven self-refresh proposal generation

## Core Principles

- One runtime authority: `.takt/`
- One task authority: `.takt/tasks/TASK-*.yaml`
- One governance piece: `.takt/pieces/agentteams-governance.yaml`
- One evidence authority: task `declarations` + `handoffs` + `approvals`
- One fleet authority: `.takt/control-plane/` (metadata only)
- No runtime fallback to legacy operation

## Topology

```text
.
|- .takt/
|  |- config.yaml
|  |- pieces/agentteams-governance.yaml
|  |- personas/
|  |- policies/
|  |- knowledge/
|  |- output-contracts/
|  |- instructions/
|  |- skills/
|  |- tasks/TASK-*.yaml
|  |- logs/
|  `- control-plane/
|     |- registry/projects.yaml
|     |- intake/<project_id>/YYYYMMDDTHHMMSSZ.yaml
|     |- signals/latest.yaml
|     |- signals/history/
|     |- team-catalog/teams.yaml
|     |- rule-catalog/routing-rules.yaml
|     |- skill-catalog/skills.yaml
|     |- refresh-queue/R-*.yaml
|     `- refresh-proposals/RP-*.md
|- scripts/
|  |- at.py
|  |- audit-takt-governance.py
|  |- audit-fleet-control-plane.py
|  |- validate-takt-task.py
|  |- validate-takt-evidence.py
|  |- validate-control-plane-schema.py
|  |- aggregate-fleet-signals.py
|  |- detect-fleet-incidents.py
|  |- detect-role-overload.py
|  `- generate-refresh-pr.py
`- templates/workflows/agentteams-export-metadata.yml
```

## Execution Flow (Local Runtime)

1. `agentteams orchestrate --task-file .takt/tasks/TASK-*.yaml`
2. `at.py` compiles local task payload plus active team/skill context.
3. TAKT executes `.takt/pieces/agentteams-governance.yaml`.
4. Team intent/handoff/gate evidence is recorded in `declarations`, `handoffs`, and `approvals`.
5. Post validation runs:
   - `validate-takt-task.py`
   - `validate-takt-evidence.py`
6. Governance audit:
   - `agentteams audit --scope local --strict`

## Fleet Detection Flow (Control Plane)

1. Project repo exports metadata-only intake.
2. Bot PR submits only `.takt/control-plane/intake/**` to central AgentTeams repo.
3. Path guard validates intake-only changes.
4. Intake merge triggers event-driven detection workflow.
5. Workflow runs:
   - aggregate signals
   - recurring incident detection
   - role overload detection
   - refresh queue/proposal generation
6. Auto-generated refresh PR is reviewed by QA and leader gates.

## Governance Distribution Model

Required team coverage resolves in this order:

1. `routing.required_teams` (v5 canonical)
2. `flags` mapping (legacy compatibility until 2026-06-30)

Evidence coverage in review/done phases must include:

- required teams
- expected `rule:<rule_id>`
- expected `skill:<skill_id>`
- approval chain order: team leaders -> QA -> overall leader

## Scheduling Policy

- Fleet detection does not rely on periodic jobs.
- Event trigger is intake update only (`push` on `.takt/control-plane/intake/**`).
- Workflow execution requires both repo variables:
  - `AGENTTEAMS_CONTROL_PLANE_ENABLED=true`
  - `AGENTTEAMS_CONTROL_PLANE_MODE=hub`
- This avoids duplicate scheduled runs in every repository.
