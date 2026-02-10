# AgentTeams v4 Topology

Canonical runtime:
- Task source of truth: `.takt/tasks/TASK-*.yaml`
- Piece source of truth: `.takt/pieces/agentteams-governance.yaml`
- Evidence source: `.takt/logs/` and task-local handoffs/warnings

Command surface:
- `agentteams init`
- `agentteams doctor`
- `agentteams orchestrate`
- `agentteams audit`
