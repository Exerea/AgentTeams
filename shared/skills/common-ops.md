# common-ops

## Purpose
全ロールが共通で守る最小オペレーションを定義する。

## Common Rules
1. 作業前に `task_file_path` で渡された task ファイルだけを読む。
2. 指定されていない task ファイルや `_index.yaml` は更新しない。
3. 開始時に task の `status` を `in_progress` に更新する。
4. 完了時に task の `status` を `in_review` または `done` に更新する。
5. handoff 時は対象 task の `handoffs` と `updated_at` を更新する。
6. ブロッカー発生時は `status=blocked` とし、`notes` に必要入力を記載する。
7. `target_stack` を確認し、担当適合しない場合は coordinator に再割当を依頼する。
8. `local_flags.major_decision_required=true` の場合、ADR 根拠なしで実装へ進まない。
9. `local_flags.documentation_sync_required=true` の場合、tech-writer 完了前に機能 task を `done` にしない。
10. `local_flags.qa_review_required=true` の場合、code-critic と test-architect 完了前に `done` にしない。
11. `local_flags.tech_specialist_required=true` の場合、該当 specialist 完了前に `done` にしない。
12. `local_flags.backend_security_required=true` の場合、`backend/security-expert` 完了前に `done` にしない。
13. バックエンド実装の標準順序は `backend/security-expert -> qa-review-guild/code-critic -> qa-review-guild/test-architect` とする。
14. `local_flags.research_track_enabled=true` の場合、`poc_result` と ADR 承認前に採用実装を開始しない。
15. 通信出力前に `docs/guides/communication-protocol.md` を確認する。
16. 通信違反を検知した場合は `warnings[]` に記録し `status=open` で起票する。
17. 研究提案の一次証跡は `notes/handoffs/warnings` に記録する。

## Status Enum
- `todo`
- `in_progress`
- `in_review`
- `blocked`
- `done`

## Warnings Contract
- `level`: `warning | error`
- `status`: `open | triaged | resolved`
- `code`:  
`PROTO_SCHEMA_MISMATCH` / `PROTO_FIELD_CASE_MISMATCH` / `PROTO_REQUIRED_FIELD_MISSING` / `PROTO_UNEXPECTED_FIELD` / `PROTO_HANDOFF_CONTEXT_MISSING`

## Minimum Checklist
- `task_file_path` のみを操作したか
- `target_stack` と担当適合を確認したか
- 関連 ADR を参照したか
- `handoffs` と `updated_at` を更新したか
- warning / research 証跡を記録したか
