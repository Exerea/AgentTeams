# Communication Protocol Guide

## Purpose
エージェント間の受け渡しを定型化し、解釈ミスと文脈欠落を防ぐ。

## Source of Truth
- 憲法: `.codex/AGENTS.md`
- 司令塔ルール: `.codex/coordinator.md`
- task 契約: `.codex/states/TASK-*.yaml`

## Required Handoff Fields
- `from`
- `to`
- `at`
- `memo`

## Declaration Format
- `DECLARATION team=<team> role=<role> task=<task_id|N/A> action=<action>`
- 適用面:
- `chat`: 作業開始時とロール切替時に宣言する
- `task`: `handoffs[].memo` の先頭行を宣言にする
- `notes`: 主要判断時は任意で宣言を追記する
- 例:
- `DECLARATION team=coordinator role=coordinator task=T-110 action=assign_backend_security_review`
- `DECLARATION team=backend role=security-expert task=T-110 action=handoff_to_code_critic`

## Required Warning Fields
- `id`
- `level` (`warning | error`)
- `code`
- `detected_by`
- `source_role`
- `target_role`
- `detected_at`
- `summary`
- `status` (`open | triaged | resolved`)
- `resolution_task_ids`
- `updated_at`

## Warning Codes
- `PROTO_SCHEMA_MISMATCH`
- `PROTO_FIELD_CASE_MISMATCH`
- `PROTO_REQUIRED_FIELD_MISSING`
- `PROTO_UNEXPECTED_FIELD`
- `PROTO_HANDOFF_CONTEXT_MISSING`

## Routing Metadata
- `target_stack.language`
- `target_stack.framework`
- `target_stack.infra`

## Operational Rules
1. 通信不整合を検知したロールは同一 task の `warnings[]` に即時記録する。
2. `warnings.status=open` が残る task は `done` にしない。
3. `warnings.level=error` は remediation 完了まで downstream 実装を開始しない。
4. 規約変更は `protocol-team/protocol-architect` 提案後、coordinator 承認で反映する。
5. 指示書更新は `protocol-team/prompt-optimizer` が対象ロール限定で実施する。
6. `qa_review_required=true` の task は `qa-review-guild/code-critic` と `qa-review-guild/test-architect` 完了前にクローズしない。
7. `status in (in_progress, in_review, done)` の task は、宣言フォーマットを含む handoff 証跡を最低1件持つ。
