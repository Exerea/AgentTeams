# common-ops

## Purpose
全ロールで共通適用する最小運用ルール。

## Common Rules
1. 作業開始時は `task_file_path` で渡された `TASK-*.yaml` のみを読み書きする。
2. `_index.yaml` と `_role-gap-index.yaml` は coordinator 専任更新とする。
3. 作業着手時に `status=in_progress`、完了時は `in_review` または `done` へ更新する。
4. handoff 時は `handoffs` に `from/to/at/memo` を記録し、`updated_at` を更新する。
5. ブロッカーは `status=blocked` とし、`notes` に原因と次アクションを記録する。
6. `target_stack` を確認し、担当外なら coordinator に再割当を要求する。
7. `local_flags.major_decision_required=true` は ADR 条件充足前に実装へ進めない。
8. `local_flags.documentation_sync_required=true` は `documentation-guild/tech-writer` 完了前に `done` にしない。
9. `local_flags.qa_review_required=true` は `qa-review-guild/code-critic` と `qa-review-guild/test-architect` 完了前に `done` にしない。
10. `local_flags.tech_specialist_required=true` は該当 specialist 完了前に `done` にしない。
11. `local_flags.backend_security_required=true` は `backend/security-expert` 完了前に `done` にしない。
12. `local_flags.ux_review_required=true` は `frontend/ux-specialist` 完了前に `done` にしない。
13. `local_flags.research_track_enabled=true` は `poc_result` と ADR 承認前に採用実装を開始しない。
14. `warnings.status=open` が残る task は `done` にしない。
15. 研究/セキュリティ/UX の一次証跡は `notes/handoffs/warnings` に記録する。
16. `done` 前に `validate-secrets` の最新成功を確認する。
17. 稼働宣言を作業開始時・ロール切替時・Gate判断時（停止/再開/完了確定）に明示する。  
口上テンプレ: `【稼働口上】殿、ただいま <家老|足軽> の <team>/<role> が <task> を務めます。<要旨>`  
呼称マッピング: `ユーザー=殿様`, `coordinator=家老`, `coordinator以外=足軽`  
`DECLARATION team=<team> role=<role> task=<task_id|N/A> action=<action>`
18. `handoffs.memo` の先頭行は稼働宣言にする。  
例: `DECLARATION team=backend role=api-architect task=T-110 action=handoff_to_security`

## UX Evidence Format
- `notes` に `ux_checklist`（pass/needs_fix と根拠）を残す。
- `handoffs.memo` に主要UX判断を1-2行で残す。

## Status Enum
- `todo`
- `in_progress`
- `in_review`
- `blocked`
- `done`

## Warnings Contract
- `level`: `warning | error`
- `status`: `open | triaged | resolved`
- `code`: `PROTO_SCHEMA_MISMATCH | PROTO_FIELD_CASE_MISMATCH | PROTO_REQUIRED_FIELD_MISSING | PROTO_UNEXPECTED_FIELD | PROTO_HANDOFF_CONTEXT_MISSING`
