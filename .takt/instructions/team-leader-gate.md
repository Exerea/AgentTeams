# Team Leader Gate Instruction

Run a strict gate before QA:

1. Read `routing.required_teams` from the task.
2. Require one leader approval per required team (except `qa-review-guild`).
3. Verify each leader approval is `approved`.
4. Verify approval timestamps are before QA gate.
5. If any team approval is rejected or missing:
   - return rework decision
   - instruct implementer to update artifacts and declarations
   - require `action` evidence that includes rework after rejection.

Do not allow QA to proceed unless all required team leader gates are approved.
