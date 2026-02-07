# audit-interaction-warnings

## Trigger
- handoff 後に通信フォーマット不一致が発生した時
- `warnings.level=error` が追加された時

## Goal
warning を証跡付きで記録し、修復タスクに繋げる。

## Procedure
1. `task_file_path` の最新 handoff と出力フォーマットを確認する。
2. warning code を選び、`warnings[]` に `status=open` で追記する。
3. 再現条件と暫定回避策を `notes` に記録する。
4. coordinator へ triage 依頼を handoff する。
5. 修復後に再監査し、解消済みなら `status=resolved` に更新する。

## Output Format
- `warnings` の追加または更新
- 監査メモ（原因、影響、再現条件）
- 次アクション（architect / optimizer / docs）
