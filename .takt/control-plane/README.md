# AgentTeams v5 Control Plane

This directory is the centralized control plane for cross-project metadata
intake, fleet-level signal aggregation, and self-refresh proposal generation.

## Security and Operation Contract

- Collect metadata only. Do not store source code content or full session logs.
- Intake PRs may change only `.takt/control-plane/intake/**`.
- Fleet detection is event-driven. No periodic schedule is required.
- Fleet refresh workflow trigger is intake push only (no manual/dispatch trigger).
- Enable fleet workflows only in the designated central repository with:
  - `AGENTTEAMS_CONTROL_PLANE_ENABLED=true`
  - `AGENTTEAMS_CONTROL_PLANE_MODE=hub`

## Directory Layout

- `registry/projects.yaml`:
  - monitored projects and control-plane settings
- `intake/<project_id>/YYYYMMDDTHHMMSSZ.yaml`:
  - immutable intake metadata snapshots from project repositories
- `signals/latest.yaml`:
  - current aggregated fleet signals
- `signals/history/*.yaml`:
  - historical aggregation snapshots
- `team-catalog/teams.yaml`:
  - configuration-driven team definitions
- `rule-catalog/routing-rules.yaml`:
  - configuration-driven routing rules
- `skill-catalog/skills.yaml`:
  - configuration-driven skill registry
- `refresh-queue/R-*.yaml`:
  - generated refresh work items
- `refresh-proposals/RP-*.md`:
  - generated proposal drafts for review
