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
- 口上（人間向け / chat 必須）  
`【稼働口上】殿、ただいま <家老|足軽> の <team>/<role> が「<task_title>」を務めます。<要旨>`
- 機械可読（既存 / task 必須）  
`DECLARATION team=<team> role=<role> task=<task_id|N/A> action=<action>`
- 呼称マッピング  
- `ユーザー=殿様`
- `coordinator=家老`
- `coordinator以外の実行ロール=足軽`
- 適用面:
- `chat`: 作業開始時・ロール切替時・Gate判断時（停止/再開/完了確定）に口上 + 宣言を出す
- 口上は `task_id` 単独表現を禁止し、作業タイトルを必須記載する
- `task`: `handoffs[].memo` の先頭行を宣言にする
- `notes`: 主要判断時は任意で宣言を追記する
- 例:
- `【稼働口上】殿、ただいま 家老 の coordinator/coordinator が「Backend Security Gate 判定」を務めます。判定を開始します。`
- `DECLARATION team=coordinator role=coordinator task=T-110 action=assign_backend_security_review`
- `DECLARATION team=backend role=security-expert task=T-110 action=handoff_to_code_critic`

## Declaration Good/Bad
- Good:
```text
【稼働口上】殿、ただいま 足軽 の backend/security-expert が「入力検証レビュー」を務めます。入力検証の確認を行います。
DECLARATION team=backend role=security-expert task=T-110 action=security_review
```
- Bad:
```text
T-110をやります。
```

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
