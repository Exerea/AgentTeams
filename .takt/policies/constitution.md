# Constitution Policy

- 正本は `.codex/AGENTS.md`
- task 作業は `TASK-*.yaml` を中心に実施する
- `status=done` は Gate 充足後のみ
- `warnings.status=open` を残したまま完了しない
- `qa_review_required=true` は code-critic と test-architect の双方が必要
- `backend_security_required=true` は backend/security-expert 証跡必須
- `ux_review_required=true` は frontend/ux-specialist 証跡必須
- `research_track_enabled=true` は `poc_result + ADR` が必須
