# AgentTeams Constitution (v2.8)

## Purpose
AgentTeams は複数エージェントで一貫した意思決定と実装品質を維持するための運用規約である。  
状態正本は Atomic States（`.codex/states/`）とし、coordinator が全体制御を担う。

## Non-Negotiable Rules
1. 実装前に `docs/adr/*.md` を確認する。
2. `task_file_path` で指定された task ファイル以外を更新しない。
3. `_index.yaml` と `_role-gap-index.yaml` は coordinator のみ更新する。
4. task 更新時は `status` と `updated_at` を必ず更新する。
5. 稼働宣言は二層で実施する。`chat` では日本語口上 `【稼働口上】殿、ただいま <家老|足軽> の <team>/<role> が <task> を務めます。<要旨>` を作業開始時・ロール切替時・Gate判断時に明示し、`handoffs[].memo` 先頭行は機械可読フォーマット `DECLARATION team=<team> role=<role> task=<task_id|N/A> action=<action>` を必須記録する（呼称マッピング: ユーザー=殿様、coordinator=家老、coordinator以外=足軽）。
6. `local_flags.major_decision_required=true` は ADR 条件充足前に実装 task を `in_progress` にしない。
7. API仕様の正本は `docs/api/openapi.yaml` とし、API変更は `documentation-guild/api-spec-owner` を経由する。
8. `local_flags.documentation_sync_required=true` は `documentation-guild/tech-writer` 完了前に `done` にしない。
9. `warnings.status=open` が残る task は `done` にしない。
10. `warnings.level=error` がある場合は remediation 完了前に downstream 実装を開始しない。
11. コード変更 task は `local_flags.qa_review_required=true` を標準とし、`qa-review-guild/code-critic` と `qa-review-guild/test-architect` 完了前に `done` にしない。
12. `local_flags.backend_security_required=true` は `backend/security-expert` 完了前に `done` にしない。
13. `backend_security_required=true` の標準適用条件は「外部公開API変更・認証/認可変更・PII取扱い変更」。
14. バックエンドレビュー順序は `backend/security-expert -> qa-review-guild/code-critic -> qa-review-guild/test-architect` を基本とする。
15. `local_flags.tech_specialist_required=true` は該当 specialist 完了前に `done` にしない。
16. `local_flags.research_track_enabled=true` かつ採用判断ありの場合、`poc_result` 記録と ADR 承認前に実装着手しない。
17. `frontend/code-reviewer` は後継を `qa-review-guild/code-critic` とし、新規割当しない。
18. `local_flags.ux_review_required=true` は `frontend/ux-specialist` 完了前に `done` にしない。
19. UX心理学レビューでは、認知負荷低減・導線明確化・段階的開示を確認し、ダークパターン（強制/誤認誘導/過度な希少性煽り）を禁止する。
20. `validate-secrets` の最新成功確認前に `done` を確定しない（Secret Scan Gate）。
21. role gap 候補は `detect-role-gaps` で検知し、`.codex/states/_role-gap-index.yaml` に反映する。
22. `validate-role-gap-review` 失敗状態では運用変更 task の `done` を確定しない（Role Gap Review Gate）。
23. `role_split/new_role` の反映は ADR を必須とし、`documentation-guild/adr-manager` 記録なしでは実施しない。

## Collaboration Surface
- 司令塔: `.codex/coordinator.md`
- ロール定義: `.codex/roles/**/instructions.md`
- 共通規約: `shared/skills/common-ops.md`
- 状態正本: `.codex/states/_index.yaml`, `.codex/states/TASK-*.yaml`
- ロール不足管理: `.codex/states/_role-gap-index.yaml`, `.codex/role-gap-rules.yaml`
- 通信規約: `docs/guides/communication-protocol.md`
- ルール判定例: `docs/guides/rule-examples.md`
- API正本: `docs/api/openapi.yaml`

## Escalation
- 担当外作業や競合判断は coordinator にエスカレーションする。
- ADR未整備の重要判断は先に ADR 起票を行う。
- 通信プロトコル違反は `protocol-team/interaction-auditor` が検知し、coordinator が最終決裁する。
- ルール解釈に迷った場合は `docs/guides/rule-examples.md` を優先参照する。
