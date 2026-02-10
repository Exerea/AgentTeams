# Request Routing Scenarios (v4)

This guide defines canonical routing for AgentTeams v4 under TAKT-only runtime.

## Common Preconditions

- Task file exists under `.takt/tasks/`.
- Task schema is valid, including `declarations` and `handoffs`.
- Flags reflect review requirements (`qa_required`, `security_required`, `docs_required`, `ux_required`, `research_required`).

## Declaration Contract (Who Does What)

- `declarations` is the canonical declaration log of role intent.
- Each declaration must record `at`, `team`, `role`, `action`, `what`, `controlled_by`.
- First declaration should be `coordinator/coordinator` with `action=triage`.
- Every handoff phase should have a matching declaration phase.
- `controlled_by` expresses the control source, typically:
  - `piece:agentteams-governance`
  - `flags`
  - `policy:*`
  - `handoff`

## Time-Ordered Routing Model

1. Intake (`T0`):
   - Team: `coordinator`
   - Action: triage and team assignment
   - Control: `piece:agentteams-governance`, `flags`
2. Execution declaration (`T1`):
   - Team: domain implementer (`backend` or `frontend` or `documentation-guild`)
   - Action: declare scope and start execution
   - Control: `policy:*`, `flags`
3. Handoff (`T2`):
   - Team: current owner to next reviewer
   - Action: handoff with evidence note
   - Control: `handoff`, `policy:*`
4. Review / rework (`T3`):
   - Team: `qa-review-guild` and required specialist teams
   - Action: approve or request rework
   - Control: `policy:qa-review`, `policy:security-review`, `policy:docs-review`
5. Leader gate (`T4`):
   - Team: `leader`
   - Action: final go/no-go
   - Control: governance piece decision path

`agentteams audit --verbose` prints declarations and handoffs in time order per task.

## Scenario 1: Standard Feature Delivery

When: `qa_required=true` and `docs_required=true`.

Flow:

1. Run `agentteams orchestrate --task-file .takt/tasks/TASK-xxxxx-feature.yaml`.
2. Ensure task has declarations for coordinator -> implementer -> docs -> qa.
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
2. Add coordinator declaration (`triage`) and backend declaration (`security review owner`).
3. Run `agentteams orchestrate --task-file .takt/tasks/TASK-xxxxx-security.yaml`.
4. Verify evidence via `python scripts/validate-takt-evidence.py`.

Expected routing:

- coordinator
- backend
- qa-review-guild
- leader

## Scenario 3: UX-Heavy Frontend Change

When: frontend experience task where `ux_required=true`.

Flow:

1. Ensure task flags include `ux_required: true`.
2. Add declarations for coordinator -> frontend -> qa handoff.
3. Run `agentteams orchestrate --task-file .takt/tasks/TASK-xxxxx-ux.yaml`.
4. Run `agentteams audit --min-teams 3 --strict`.

Expected routing:

- coordinator
- frontend
- qa-review-guild
- leader

## Scenario 4: Research-Driven Discovery Task

When: exploratory task where `research_required=true`.

Flow:

1. Ensure task flags include `research_required: true`.
2. Add declarations for coordinator -> innovation-research-guild -> qa.
3. Run `agentteams orchestrate --task-file .takt/tasks/TASK-xxxxx-research.yaml`.
4. Validate task/evidence:
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
