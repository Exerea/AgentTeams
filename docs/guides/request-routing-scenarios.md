# Request Routing Scenarios (v4)

This guide defines canonical routing for AgentTeams v4 under TAKT-only runtime.

## Common Preconditions

- Task file exists under `.takt/tasks/`.
- Task schema is valid.
- Flags reflect review requirements (`qa_required`, `security_required`, `docs_required`, `ux_required`, `research_required`).

## Scenario 1: Standard Feature Delivery

When: normal feature request with `qa_required=true` and `docs_required=true`.

Flow:

1. Run `agentteams orchestrate --task-file .takt/tasks/TASK-xxxxx-feature.yaml`.
2. Piece routes triage -> execute -> qa review -> leader gate.
3. Audit with `agentteams audit --strict`.

Expected routing:

- coordinator
- implementer
- qa-review-guild
- documentation-guild
- leader

## Scenario 2: Security-Sensitive Backend Change

When: backend task where `security_required=true`.

Flow:

1. Ensure task flags include `security_required: true`.
2. Run `agentteams orchestrate --task-file .takt/tasks/TASK-xxxxx-security.yaml`.
3. Verify evidence via `python scripts/validate-takt-evidence.py`.

Expected routing:

- coordinator
- backend
- qa-review-guild
- leader

## Scenario 3: UX-Heavy Frontend Change

When: frontend experience task where `ux_required=true`.

Flow:

1. Ensure task flags include `ux_required: true`.
2. Run `agentteams orchestrate --task-file .takt/tasks/TASK-xxxxx-ux.yaml`.
3. Run `agentteams audit --min-teams 3 --strict`.

Expected routing:

- coordinator
- frontend
- qa-review-guild
- leader

## Scenario 4: Research-Driven Discovery Task

When: exploratory task where `research_required=true`.

Flow:

1. Ensure task flags include `research_required: true`.
2. Run `agentteams orchestrate --task-file .takt/tasks/TASK-xxxxx-research.yaml`.
3. Validate task/evidence:
   - `python scripts/validate-takt-task.py --file .takt/tasks/TASK-xxxxx-research.yaml`
   - `python scripts/validate-takt-evidence.py`

Expected routing:

- coordinator
- innovation-research-guild
- qa-review-guild
- leader

## Failure and Rework Routing

- QA rework -> piece loops back to execute.
- Leader rework -> piece loops back to execute.
- Critical issues -> piece abort path.

## Operational Commands

- `agentteams doctor`
- `agentteams orchestrate --task-file .takt/tasks/TASK-00140-final-code-review.yaml`
- `agentteams audit`
