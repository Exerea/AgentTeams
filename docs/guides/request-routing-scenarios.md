# Request Routing Scenarios (v5)

This guide defines canonical routing for AgentTeams v5 under TAKT-only runtime.

## Common Preconditions

- Task file exists under `.takt/tasks/`.
- Task schema is valid, including `declarations`, `handoffs`, and `routing`.
- Legacy flags (`qa_required`, `security_required`, `docs_required`) are allowed during compatibility period.

## Declaration Contract (Who Does What)

- `declarations` is the canonical declaration log of role intent.
- Each declaration must record `at`, `team`, `role`, `action`, `what`, `controlled_by`.
- `controlled_by` must include governance evidence when applicable:
  - `rule:<rule_id>`
  - `skill:<skill_id>`
  - `policy:*`
  - `handoff`

## Time-Ordered Routing Model

1. Intake (`T0`)
   - Team: `coordinator`
   - Action: triage and assignment
   - Control: `rule:default-routing`, `skill:skill-routing-governance`
2. Execution declaration (`T1`)
   - Team: domain team from `routing.required_teams`
   - Action: declare scope and start execution
3. Handoff (`T2`)
   - Team: current owner to next reviewer
   - Action: handoff with evidence note
4. Review / rework (`T3`)
   - Team: QA and required specialist teams
   - Action: approve or request rework
5. Leader gate (`T4`)
   - Team: `leader`
   - Action: final go/no-go

Use:

- `agentteams audit --scope local --verbose`
- `agentteams audit --scope fleet --strict`

## Scenario 1: Standard Feature Delivery

When: `qa_required=true`, `docs_required=true`.

Flow:

1. Run `agentteams orchestrate --task-file .takt/tasks/TASK-xxxxx-feature.yaml`.
2. Ensure routing includes coordinator + implementation + docs + QA.
3. Add declaration evidence for routing rule and active skills.
4. Audit local governance.

Expected routing:

- coordinator
- implementer team
- documentation-guild
- qa-review-guild
- leader

## Scenario 2: Security-Sensitive Backend Change

When: backend task where `security_required=true`.

Flow:

1. Ensure compatibility flags include `security_required: true`.
2. Ensure `routing.required_teams` includes `backend`.
3. Run `agentteams orchestrate --task-file .takt/tasks/TASK-xxxxx-security.yaml`.
4. Verify evidence:
   - `rule:security-required`
   - `skill:skill-backend-security-review`

Expected routing:

- coordinator
- backend
- qa-review-guild
- leader

## Scenario 3: UX-Heavy Frontend Change

When: frontend experience task where `ux_required=true`.

Flow:

1. Ensure compatibility flags include `ux_required: true`.
2. Ensure `routing.required_teams` includes `frontend`.
3. Run `agentteams orchestrate --task-file .takt/tasks/TASK-xxxxx-ux.yaml`.
4. Run local/fleet audit and check overload warnings.

Expected routing:

- coordinator
- frontend
- qa-review-guild
- leader

## Scenario 4: Research-Driven Discovery Task

When: exploratory task where `research_required=true`.

Flow:

1. Ensure compatibility flags include `research_required: true`.
2. Ensure `routing.required_teams` includes `innovation-research-guild`.
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
- Recurrent cross-project issues -> refresh queue/proposal generated in control-plane.

## Operational Commands

- `agentteams doctor`
- `agentteams orchestrate --task-file .takt/tasks/TASK-00140-final-code-review.yaml`
- `agentteams audit --scope local`
- `agentteams audit --scope fleet`
