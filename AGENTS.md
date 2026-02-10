# AgentTeams v4 Entry Contract

## Canonical Runtime

- Source of truth: `.takt/`
- Task files: `.takt/tasks/TASK-*.yaml`
- Piece: `.takt/pieces/agentteams-governance.yaml`

## Command Contract

Use only:

- `agentteams init`
- `agentteams doctor`
- `agentteams orchestrate`
- `agentteams audit`

## Chat/Execution Start Contract

Before implementation begins:

1. Read the assigned `.takt/tasks/TASK-*.yaml` file.
2. Confirm `goal`, `constraints`, `acceptance`, and `flags`.
3. Run work through TAKT orchestration or explicit role handoff with evidence.

## Evidence Contract

- Keep handoff evidence in task `handoffs` and `notes`.
- Keep runtime logs under `.takt/logs/`.
- Ensure required guild coverage matches task flags.
