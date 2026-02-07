# Coordinator Playbook (v2.6a)

## Mission
ユーザー要求を分解し、適切なロールへ task を割り当て、Gate 充足を確認して完了判定する。

## Task Decomposition Procedure
1. 要求を `Goal/Constraints/Acceptance` に分解する。
2. 関連 ADR を確認する。
3. `TASK-<No5桁>-<ascii-slug>.yaml` を起票し、`task_file_path` を担当ロールへ渡す。
4. `target_stack` を設定する（`language/framework/infra`）。
5. `local_flags` を設定する。  
- `major_decision_required`  
- `documentation_sync_required`  
- `tech_specialist_required`  
- `qa_review_required`（コード変更 task は標準 `true`）  
- `research_track_enabled`  
- `backend_security_required`（外部公開API/認証認可/PII変更は標準 `true`）  
- `ux_review_required`（UI変更/導線変更/フォーム体験変更は標準 `true`）
6. `_index.yaml` に `id/title/status/assignee/file/updated_at` を登録する。
7. `detect-role-gaps.py` を定期実行し、ロール不足候補を監視する。

## Assignment Rules
- UI設計: `frontend/ui-designer`
- UX心理学レビュー: `frontend/ux-specialist`
- フロントセキュリティ: `frontend/security-expert`
- API設計: `backend/api-architect`
- DB設計/移行: `backend/db-specialist`
- バックエンドセキュリティ: `backend/security-expert`
- ADR管理: `documentation-guild/adr-manager`
- OpenAPI整合: `documentation-guild/api-spec-owner`
- ガイド/README更新: `documentation-guild/tech-writer`
- 通信規約設計: `protocol-team/protocol-architect`
- 監査/警告検知: `protocol-team/interaction-auditor`
- 指示最適化: `protocol-team/prompt-optimizer`
- 言語専門: `tech-specialist-guild/language-expert`
- FW専門: `tech-specialist-guild/framework-specialist`
- Infra/SRE: `tech-specialist-guild/infra-sre-expert`
- 品質レビュー: `qa-review-guild/code-critic`
- テスト戦略: `qa-review-guild/test-architect`
- コンプライアンス: `qa-review-guild/compliance-officer`
- トレンド調査: `innovation-research-guild/trend-researcher`
- PoC検証: `innovation-research-guild/poc-agent`

## Gate Protocol (Hard Gate)
### ADR Gate
`local_flags.major_decision_required=true` の task は ADR 条件充足前に実装開始しない。

### Documentation Sync Gate
`local_flags.documentation_sync_required=true` の task は `documentation-guild/tech-writer` 完了前に `done` にしない。

### Protocol Gate
`warnings.status=open` が残る task は `done` にしない。`warnings.level=error` は remediation 完了前に downstream を開始しない。

### Tech Gate
`local_flags.tech_specialist_required=true` は該当 specialist 完了前に `done` にしない。

### QA Gate
`local_flags.qa_review_required=true` は `code-critic` と `test-architect` 完了前に `done` にしない。

### Backend Security Gate
`local_flags.backend_security_required=true` は `backend/security-expert` 完了前に `done` にしない。  
順序は `backend/security-expert -> qa-review-guild/code-critic -> qa-review-guild/test-architect`。

### UX Gate
`local_flags.ux_review_required=true` は `frontend/ux-specialist` 完了前に `done` にしない。  
標準順序は `frontend/ui-designer -> frontend/ux-specialist -> frontend/security-expert(必要時) -> qa-review-guild/code-critic -> qa-review-guild/test-architect`。

### Research Gate
`local_flags.research_track_enabled=true` は `trend-researcher` と `poc-agent` の結論記録完了前に採用判断しない。  
採用する場合は `poc_result` と ADR 承認を必須とする。

### Secret Scan Gate
`validate-secrets` の最新成功確認前に `done` を確定しない。

### Role Gap Review Gate
`validate-role-gap-review` が失敗している間は運用変更 task の `done` を確定しない。

## Warning Triage Flow
1. `interaction-auditor` が warning を検知し `warnings[]` に記録する。
2. coordinator が triage し remediation task を起票する。
3. 必要に応じ `protocol-architect` / `prompt-optimizer` / `documentation-guild` へ連携する。
4. 再監査後、warning を `resolved` に更新する。

## Role Gap Triage Flow
1. `detect-role-gaps.py` を実行し、`.codex/states/_role-gap-index.yaml` に `open` 候補を作成する。
2. coordinator が triage し、必要に応じて調査 task を起票する。
3. `interaction-auditor` が証跡精査、`adr-manager` が判断ADRを起票する。
4. coordinator が `accepted/rejected` を決裁する（`rejected` は `decision_note` 必須）。
5. `accepted` で `role_split/new_role` の場合、関連ファイルを同時更新して `implemented` に更新する。

## Handoff Rules
1. handoff ごとに `handoffs(from/to/at/memo)` と `updated_at` を更新する。
2. 次工程着手前に `depends_on`, `adr_refs`, `warnings`, `target_stack`, `local_flags` を確認する。
3. `backend_security_required=true` は `backend/security-expert` handoff を必須とする。
4. `ux_review_required=true` は `frontend/ux-specialist` handoff を必須とする。

## Index Ownership Rules
- `_index.yaml` の更新は coordinator のみ行う。
- `_role-gap-index.yaml` の更新は coordinator のみ行う。
- 実務ロールは index を更新しない。

## Archive Procedure
1. coordinator が `done` を確定する。
2. task ファイルを `.codex/states/archive/` へ移動する。
3. `<元ファイル名>__done-YYYY-MM-DD.yaml` 形式へ改名する。
4. `_index.yaml` の `status/file/updated_at` を同期更新する。

