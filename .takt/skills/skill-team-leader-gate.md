# Skill: Team Leader Gate

Purpose:
- Enforce mandatory approvals in this exact order:
  1. required team leaders
  2. QA
  3. overall leader

Execution requirements:
- Every required team (except `qa-review-guild`) must have a leader gate entry.
- Leader gate statuses must be explicit (`approved|rejected|pending`).
- QA cannot approve before all required team leader gates are approved.
- Overall leader cannot approve before QA approval.
- Rejections must trigger rework declarations and route back to execute.

Evidence requirements:
- `approvals.team_leader_gates[*].controlled_by` includes:
  - `piece:agentteams-governance`
  - `rule:team-leader-approval-required`
  - `skill:skill-team-leader-gate`
- `approvals.qa_gate` and `approvals.leader_gate` include rule/skill evidence.
