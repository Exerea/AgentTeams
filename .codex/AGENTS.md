# AgentTeams Constitution (v2.3)

## Purpose
AgentTeams は、複数 AI エージェントが同一プロジェクトで一貫した意思決定を行うための運用基盤です。  
本憲法は、ロール責務分離・ADR 継承・Atomic States 運用・通信品質管理・品質/技術/研究/バックエンドセキュリティガバナンスを固定します。

## Non-Negotiable Rules
1. 実装・レビュー・設計変更の前に、関連する `docs/adr/*.md` を参照する。
2. 状態管理の正本は `.codex/states/` とし、単一巨大 state 運用は禁止する。
3. 専門ロールは必ず `task_file_path` で渡された 1 ファイルだけを読み書きする。
4. `_index.yaml` の更新は coordinator のみが行う。
5. task 状態が変わったら、担当者は `status` と `updated_at` を更新する。
6. 担当外の責務を直接実施しない。必要な作業は coordinator 経由で再分解する。
7. `local_flags.major_decision_required=true` の task は ADR ゲート通過前に実装 task を `in_progress` にしない。  
条件A: ADR task が `done`。  
条件B: 対象 task に `adr_refs` が設定済み。  
条件C: 対象 task の `depends_on` に ADR task ID が設定済み。
8. API 契約の正本は `docs/api/openapi.yaml` とし、API 変更時は `documentation-guild/api-spec-owner` を必ず経由する。
9. `local_flags.documentation_sync_required=true` の task は `documentation-guild/tech-writer` 完了前に `done` にしない。
10. 通信規約変更は `protocol-team/protocol-architect` が提案し、coordinator 承認後に反映する。
11. `warnings.status=open` が残る task は `done` にしない。
12. `warnings.level=error` を含む task は remediation 完了前に downstream 実装 task を `in_progress` にしない。
13. 通信エラーの証跡は task の `warnings`, `handoffs`, `notes` を正とする。
14. コード変更 task は `local_flags.qa_review_required=true` を標準とし、`qa-review-guild/code-critic` 完了前に `done` にしない。
15. `local_flags.backend_security_required=true` の task は `backend/security-expert` 完了前に `done` にしない。
16. `backend_security_required=true` の標準適用条件は「外部公開 API 変更・認証/認可変更・PII 取扱い変更」のいずれかとする。
17. バックエンド実装のレビュー順序は `backend/security-expert -> qa-review-guild/code-critic -> qa-review-guild/test-architect` を基本とする。
18. `local_flags.tech_specialist_required=true` の task は該当 specialist 完了前に `done` にしない。
19. `local_flags.research_track_enabled=true` かつ採用判断がある場合、`poc_result` 記録と ADR 承認前に実装着手しない。
20. `frontend/code-reviewer` は運用上の正規後継を `qa-review-guild/code-critic` とし、新規割当は行わない。
21. 専門性ルーティングは `target_stack.language/framework/infra` を基準に行う。

## Collaboration Surface
- 司令塔: `.codex/coordinator.md`
- ロール定義: `.codex/roles/**/instructions.md`
- 共通オペレーション: `shared/skills/common-ops.md`
- 状態管理: `.codex/states/_index.yaml`, `.codex/states/TASK-*.yaml`
- 通信ガイド: `docs/guides/communication-protocol.md`
- API 契約: `docs/api/openapi.yaml`
- 技術ガイド: `docs/guides/`

## Escalation
- 競合する判断が発生した場合は、coordinator が最終決定者となる。
- 既存 ADR と矛盾する変更は、`docs/adr` に新規 ADR を追加して意思決定を明文化する。
- コード差分と OpenAPI/ガイドの不整合は `documentation-guild` が差し戻し可能とする。
- 通信プロトコル違反は `protocol-team/interaction-auditor` が検知し coordinator へエスカレーションする。
