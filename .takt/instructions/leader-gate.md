# Leader Gate Instruction

Make the final decision using triage, implementation, team-leader-gate, and QA evidence.
Approve only if required reviews and quality gates are satisfied.

Hard gate requirements:
- Reject if any required team leader approval is missing or rejected.
- Reject if QA gate is not approved.
- If rejected, force rework back to execute and require new rework declarations.
