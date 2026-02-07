# backend-threat-model-and-hardening-check

## Trigger
- `local_flags.backend_security_required=true`
- 外部公開 API、認証/認可、PII 取扱い変更を含む task

## Action
1. `task_file_path` の変更範囲、`target_stack`、`notes/handoffs` を確認する。
2. 脅威モデルを作成し、攻撃面（認証、入力、データ保護、可観測性）を列挙する。
3. 主要観点を点検する。  
   認証/認可、入力検証、SQL/ORM 安全性、SSRF、Deserialization、Secrets、監査ログ、レート制限。
4. 必須修正と保留リスクを `notes` に追記する。
5. protocol 起点の不整合がある場合は `warnings[]` に記録する。
6. セキュリティレビュー完了後、`qa-review-guild/code-critic` と `qa-review-guild/test-architect` に handoff する。

## Output
- セキュリティレビュー結果（対策済み/要対応/保留リスク）
- handoff 記録
