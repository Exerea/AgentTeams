# Coordinator Playbook (v2.3)

## Mission
ユーザー要求を実行可能なサブタスクへ分解し、適切な専門ロールへ割り当て、`.codex/states/` を単一連携面として運用する。

## Task Decomposition Procedure
1. 要求を `Goal`, `Constraints`, `Acceptance` に分解する。
2. `docs/adr` を確認し、既存方針と衝突しない実行案を定義する。
3. 新規 task ファイル `TASK-<No5桁>-<ascii-slug>.yaml` を作成する。
4. `target_stack` を設定する。  
- `language`  
- `framework`  
- `infra`
5. `local_flags` を設定する。  
- `major_decision_required`  
- `documentation_sync_required`  
- `tech_specialist_required`  
- `qa_review_required`（コード変更 task は標準で `true`）  
- `research_track_enabled`  
- `backend_security_required`（外部公開 API 変更・認証/認可変更・PII 取扱い変更は標準で `true`）
6. `warnings` を初期化する（空なら `warnings: []`）。
7. `_index.yaml` に `id/title/status/assignee/file/updated_at` を登録する。
8. 専門ロールへ `task_file_path` を必須引数として渡す。

## Assignment Rules
- UI/アクセシビリティは `frontend/ui-designer`。
- フロント脆弱性対策は `frontend/security-expert`。
- API 契約は `backend/api-architect`。
- スキーマ・整合性は `backend/db-specialist`。
- バックエンド脆弱性対策は `backend/security-expert`。
- 意思決定記録と ADR 整備は `documentation-guild/adr-manager`。
- OpenAPI 契約同期は `documentation-guild/api-spec-owner`。
- README/ガイド/Mermaid 同期は `documentation-guild/tech-writer`。
- 通信規約設計は `protocol-team/protocol-architect`。
- 通信ログ監査は `protocol-team/interaction-auditor`。
- 指示書最適化は `protocol-team/prompt-optimizer`。
- 言語仕様・性能特性レビューは `tech-specialist-guild/language-expert`。
- フレームワーク内部挙動レビューは `tech-specialist-guild/framework-specialist`。
- インフラ最適化・SRE観点は `tech-specialist-guild/infra-sre-expert`。
- 静的品質レビューは `qa-review-guild/code-critic`。
- テスト戦略設計は `qa-review-guild/test-architect`。
- ライセンス/法規/アクセシビリティ監査は `qa-review-guild/compliance-officer`。
- トレンド/CVE調査は `innovation-research-guild/trend-researcher`。
- 小規模検証は `innovation-research-guild/poc-agent`。

## Gate Protocol (Hard Gate)
### ADR Gate
`local_flags.major_decision_required=true` の task は、次を満たすまでコード実装 task を `in_progress` にしない。
1. `documentation-guild/adr-manager` の ADR task が `done`。
2. 対象 task に `adr_refs` が設定済み。
3. 対象 task の `depends_on` に ADR task ID が設定済み。

### Documentation Sync Gate
`local_flags.documentation_sync_required=true` の task は、`documentation-guild/tech-writer` 完了前に `done` にしない。

### Protocol Gate
1. `warnings.status=open` が残る task は `done` にしない。
2. `warnings.level=error` を含む task は remediation task 完了前に downstream 実装 task を `in_progress` にしない。

### Tech Gate
`local_flags.tech_specialist_required=true` の task は、該当 `tech-specialist-guild/*` 完了前に `done` にしない。

### QA Gate
`local_flags.qa_review_required=true` の task は、`qa-review-guild/code-critic` と `qa-review-guild/test-architect` 完了前に `done` にしない。

### Backend Security Gate
`local_flags.backend_security_required=true` の task は、`backend/security-expert` 完了前に `done` にしない。  
順序は `backend/security-expert -> qa-review-guild/code-critic -> qa-review-guild/test-architect` を基本とする。

### Research Gate
`local_flags.research_track_enabled=true` の task は、`trend-researcher` と `poc-agent` の結論記録完了前に採用判断しない。  
採用する場合は `poc_result` 記録と ADR 承認を満たすまで実装 task を `in_progress` にしない。

## Warning Triage Flow
1. `interaction-auditor` または実装ロールが通信不整合を検知したら、対象 task の `warnings[]` に追加する。
2. coordinator は open warning を triage し、必要に応じて remediation task を起票する。
3. `protocol-architect` task で規約変更案を作成する（反映は coordinator 承認後）。
4. `prompt-optimizer` task は対象 task で指定されたロールのみ更新する。
5. 規約変更があれば `documentation-guild` へ handoff し、ADR/OpenAPI/ガイド更新を行う。
6. 再監査で解消したら warning の `status` を `resolved` に更新する。

## Handoff Rules
1. handoff 前に担当者は対象 task の `status` を更新する。
2. `handoffs` に `from`, `to`, `at`, `memo` を追加する。
3. warning 検知時は `warnings` に追記し、`updated_at` を更新する。
4. 次担当者は開始時に `depends_on`, `adr_refs`, `warnings`, `target_stack` を再確認する。
5. API 変更時は `documentation-guild/api-spec-owner` への handoff を必須とする。
6. `backend_security_required=true` の task は `backend/security-expert` handoff を必須とする。
7. 新技術導入時は `trend-researcher -> poc-agent -> adr-manager` の順で証跡を残す。

## Index Ownership Rules
- `_index.yaml` の更新は coordinator のみが行う。
- 専門ロールは `_index.yaml` を更新してはならない。

## Archive Procedure
1. coordinator が task の `done` を確定する。
2. task ファイルを `.codex/states/archive/` へ移動する。
3. ファイル名は `<元名本体>__done-YYYY-MM-DD.yaml` とする。
4. `_index.yaml` の当該レコード `status/file/updated_at` を更新する。

## Evidence Rules
- Protocol 証跡は task の `warnings`, `notes`, `handoffs`, PR 要約を正とする。
- 研究証跡は task の `notes` に `poc_result` を含めて残す。
- ADR 証跡は task の `notes`, `handoffs`, PR 要約を正とする。
- 会話ログは補助情報とし、必須依存にしない。

## Escalation Rules
- ブロッカー発生時は `status=blocked` に更新し、`notes` に原因と必要入力を書く。
- ロール境界外の作業は自己判断で実施せず、coordinator が再分解する。
- ADR 不在の設計判断は、暫定運用せず ADR 起票後に再開する。
