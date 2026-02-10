# TAKT Orchestration Guide (v5 Canonical)

This is the supported orchestration flow in AgentTeams v5.

## 1. Validate Environment

```bash
agentteams doctor
```

Doctor checks:

- git repository context
- `takt` command availability
- governance piece presence
- local task schema validity
- control-plane schema validity
- intake template/workflow presence

## 2. Prepare Task File

Create or update a task under `.takt/tasks/`:

```yaml
id: T-00140
title: final-code-review
status: todo
task: |
  Execute final governance review and close all open findings.
goal: "Release with full review evidence"
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
      status: approved
      at: 2026-02-10T00:05:00Z
      note: "triage accepted"
      controlled_by:
        - "piece:agentteams-governance"
        - "rule:team-leader-approval-required"
        - "skill:skill-team-leader-gate"
    - team: documentation-guild
      leader_role: team-lead
      status: approved
      at: 2026-02-10T00:06:00Z
      note: "docs ownership accepted"
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
    note: "awaiting final go/no-go"
    controlled_by:
      - "piece:agentteams-governance"
      - "rule:default-routing"
      - "skill:skill-routing-governance"
notes: ""
updated_at: 2026-02-10T00:00:00Z
```

Declaration policy:

- `declarations` must explicitly state who does what before/at each handoff.
- First declaration should be coordinator triage.
- In review/done phases, declarations should contain `rule:<rule_id>` and `skill:<skill_id>` evidence.
- Approval chain is mandatory: `team leaders -> QA -> overall leader`.
- Rejected gates must route back to execute and add rework declarations.

## 3. Execute Orchestration

Default provider (`codex`):

```bash
agentteams orchestrate --task-file .takt/tasks/TASK-00140-final-code-review.yaml
```

Mock provider (CI/smoke):

```bash
agentteams orchestrate --task-file .takt/tasks/TASK-00140-final-code-review.yaml --provider mock --no-post-validate
```

## 4. Post Checks

If post-validation is enabled, CLI runs:

- `scripts/validate-takt-task.py`
- `scripts/validate-takt-evidence.py`

Manual governance audits:

```bash
agentteams audit --scope local --strict
agentteams audit --scope fleet --strict
```

Timeline visibility:

```bash
agentteams audit --scope local --verbose
```

## 5. Fleet Intake and Refresh

Project repositories should use metadata-only intake and bot PR submission:

- template: `templates/workflows/agentteams-export-metadata.yml`
- destination: `.takt/control-plane/intake/<project_id>/YYYYMMDDTHHMMSSZ.yaml`

Refresh detection is event-driven:

- trigger: intake update only (`push` on `.takt/control-plane/intake/**`)
- central-only guard vars:
  - `AGENTTEAMS_CONTROL_PLANE_ENABLED=true`
  - `AGENTTEAMS_CONTROL_PLANE_MODE=hub`
- no periodic schedule required

## 6. Repository Validation

Linux:

```bash
bash ./scripts/validate-repo.sh
```

Windows:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate-repo.ps1
```

## Command Deprecation

The following commands are intentionally removed in v5 and return discontinued errors:

- `agentteams sync`
- `agentteams report-incident`
- `agentteams guard-chat`
