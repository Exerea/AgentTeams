# Task State Knowledge

Task の必須構造:
- top-level keys: id, title, owner, assignee, status, target_stack, depends_on, adr_refs, local_flags, warnings, handoffs, notes, updated_at
- local_flags: major_decision_required, documentation_sync_required, tech_specialist_required, qa_review_required, research_track_enabled, backend_security_required, ux_review_required
- warning status: open | triaged | resolved

重要:
- `in_progress` / `in_review` / `done` は handoff DECLARATION 証跡が必要
- `blocked` または unresolved warning は IMPROVEMENT_PROPOSAL 証跡が必要
