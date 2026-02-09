# AgentTeams Structure Audit

## Summary
- tasks scanned: 5
- findings: 11
- log has AGENTS read evidence: no
- log has ADR read evidence: no
- log has guard usage evidence: no

## Findings
- [warning] T-100 ROLE_DISTRIBUTION_LOW: unique roles=3 < min-roles=5
- [warning] T-110 TEAM_DISTRIBUTION_LOW: unique teams=2 < min-teams=3
- [warning] T-110 ROLE_DISTRIBUTION_LOW: unique roles=4 < min-roles=5
- [error] T-110 QA_EVIDENCE_MISSING: qa_review_required=true but code-critic/test-architect evidence is incomplete
- [warning] T-120 TEAM_DISTRIBUTION_LOW: unique teams=2 < min-teams=3
- [warning] T-120 ROLE_DISTRIBUTION_LOW: unique roles=3 < min-roles=5
- [warning] T-130 TEAM_DISTRIBUTION_LOW: unique teams=2 < min-teams=3
- [warning] T-130 ROLE_DISTRIBUTION_LOW: unique roles=3 < min-roles=5
- [warning] T-140 TEAM_DISTRIBUTION_LOW: unique teams=2 < min-teams=3
- [warning] T-140 ROLE_DISTRIBUTION_LOW: unique roles=2 < min-roles=5
- [error] T-140 QA_EVIDENCE_MISSING: qa_review_required=true but code-critic/test-architect evidence is incomplete

## Task Matrix
- T-100 | status=done | teams=3 | roles=3 | open_warnings=0
- T-110 | status=in_review | teams=2 | roles=4 | open_warnings=0
- T-120 | status=in_review | teams=2 | roles=3 | open_warnings=0
- T-130 | status=in_progress | teams=2 | roles=3 | open_warnings=0
- T-140 | status=todo | teams=2 | roles=2 | open_warnings=0
