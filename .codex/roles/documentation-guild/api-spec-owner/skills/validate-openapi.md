# validate-openapi

## Trigger
- API 関連 task が起票された時
- コード差分に新規/変更エンドポイントが含まれる時

## Goal
`docs/api/openapi.yaml` を実装差分と同期し、契約不整合を防ぐ。

## Procedure
1. `task_file_path` の warnings/notes/handoffs/PR 要約から変更 API を列挙する。
2. `docs/api/openapi.yaml` の `paths` と `components.schemas` を照合する。
3. 以下の差分を修正または指摘する。  
- path 未定義  
- request/response スキーマ不一致  
- status code の不足
4. 破壊的変更の場合は task notes に移行方針を追記する。

## Output Format
- OpenAPI 更新差分
- 差分チェック結果（pass/fail）
- 次 handoff（tech-writer または code-critic）
