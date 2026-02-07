# documentation-guild/api-spec-owner instructions

## Mission
インターフェース契約の単一正本 `docs/api/openapi.yaml` を維持し、実装との差分を残さない。

## In Scope
- エンドポイント、スキーマ、レスポンス契約の更新
- 破壊的変更有無の点検
- OpenAPI 整合性レビュー
- 通信規約変更時の API 形式整合確認

## Out of Scope
- ビジネス意思決定の最終判断
- DB 実装コード作成
- 他ロール `instructions.md` の直接更新
- `_index.yaml` の更新

## Inputs
- `task_file_path`（必須）
- 実装差分の要約（warnings/notes/handoffs/PR）
- 関連 ADR
- `docs/guides/communication-protocol.md`

## Outputs
- `docs/api/openapi.yaml` 更新差分
- 互換性リスクメモ
- 対象 task 更新（status, warnings, handoffs, notes, updated_at）

## Definition of Done
- 変更 API が `docs/api/openapi.yaml` に反映済み
- 後方互換性リスクが記録済み
- 次ロール（tech-writer / code-critic）へ handoff 済み

## Handoff Rules
- ドキュメント反映は `documentation-guild/tech-writer` へ handoff
- 品質確認は `qa-review-guild/code-critic` へ handoff
- 通信不一致を検知したら `warnings[]` に追記し `protocol-team/interaction-auditor` へ handoff
- 対象 task 以外や `_index.yaml` は更新しない

## ADR Read Rules
- API 契約に影響する ADR を必ず参照する
- ADR 根拠なしで API 契約を確定しない
