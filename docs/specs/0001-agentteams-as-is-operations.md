# AgentTeams 現行構成と命令連携・運用サマリー（As-Is v2.8）

## Summary
このリポジトリは Template Repo として各案件に同梱し、coordinator が task 分解とロール割当を行う。  
状態正本は `.codex/states/` で、`_index.yaml` は全体俯瞰、`TASK-*.yaml` は実務詳細を管理する。  
v2.8 では稼働宣言プロトコルを二層化し、`chat` は Task開始時に固定開始宣言 + 日本語口上 + 機械可読宣言の3行契約を必須化した。`handoff memo` は機械可読宣言でアクティブロール可視化を必須化する。加えて、作業開始時と Gate判断時に必要性判断を行い、必要時は `【進言】...` を出す。
`frontend/code-reviewer` は廃止済みとし、新規 task では `qa-review-guild/code-critic` を正規レビュー担当とする。

## 運用シナリオ正本
- `docs/guides/request-routing-scenarios.md`
- coordinator 依頼文は同ガイドの `User Request` テンプレを利用する
- `coordinatorとして処理して` は推奨文であり必須ではない

## ルール判定例正本
- `docs/guides/rule-examples.md`
- 23ルールの Good/Bad/Detection を 1:1 で管理する

## フォルダ構成（主要）
- `.codex/AGENTS.md`
- `.codex/coordinator.md`
- `.codex/states/_index.yaml`
- `.codex/states/TASK-*.yaml`
- `.codex/states/_role-gap-index.yaml`
- `.codex/role-gap-rules.yaml`
- `.codex/roles/frontend/*`
- `.codex/roles/backend/*`
- `.codex/roles/documentation-guild/*`
- `.codex/roles/protocol-team/*`
- `.codex/roles/tech-specialist-guild/*`
- `.codex/roles/qa-review-guild/*`
- `.codex/roles/innovation-research-guild/*`

## スクリプト
- `scripts/bootstrap-agent-teams.ps1`
- `scripts/bootstrap-agent-teams.sh`
- `scripts/validate-states-index.ps1`
- `scripts/validate-states-index.sh`
- `scripts/validate-task-state.ps1`
- `scripts/validate-task-state.sh`
- `scripts/validate-doc-consistency.py`
- `scripts/validate-scenarios-structure.py`
- `scripts/validate-rule-examples-coverage.py`
- `scripts/detect-role-gaps.py`
- `scripts/validate-role-gap-review.py`
- `scripts/validate-secrets.ps1`
- `scripts/validate-secrets.sh`
- `scripts/validate-repo.ps1`
- `scripts/validate-repo.sh`
- `scripts/validate-self-update-evidence.py`

## 制御プレーン
1. coordinator が要求を `Goal/Constraints/Acceptance` に分解
2. `target_stack` と `local_flags` を設定して task 起票
3. `task_file_path` を担当ロールへ引き渡し
4. `_index.yaml` は coordinator のみ更新

## データプレーン
- 各ロールは担当 `TASK-*.yaml` のみ更新
- handoff は `from/to/at/memo` で記録
- warning は `warnings[]` へ記録

## 稼働宣言プロトコル
- 固定開始宣言（Task開始時のみ）: `殿のご命令と各AGENTS.mdに忠実に従う家臣たちが集まりました。──家臣たちが動きます！`
- 口上テンプレ: `【稼働口上】殿、ただいま <家老|足軽> の <team>/<role> が「<task_title>」を務めます。<要旨>`
- 進言テンプレ: `【進言】<提案内容>（理由: <risk_or_benefit>）`
- 機械可読宣言: `DECLARATION team=<team> role=<role> task=<task_id|N/A> action=<action>`
- 呼称マッピング: `ユーザー=殿様`, `coordinator=家老`, `coordinator以外=足軽`
- `chat`: Task開始時は `固定開始宣言 -> 口上 -> DECLARATION` の3行をこの順で出す（固定開始宣言はTask開始時のみ）
- `chat`: ロール切替時・Gate判断時は口上 + 宣言を出す
- `chat`: 作業開始時・Gate判断時には必要性判断を行い、必要時は進言を併記する
- 口上では `task_id` 単独表現を禁止し、作業タイトルを必須記載する
- `task`: `handoffs.memo` の先頭行に宣言を記録する
- `status in (in_progress, in_review, done)` の task は宣言付き handoff 証跡を最低1件持つ

## MCP運用契約（DevTools MCP）
1. MCP は常時必須ではない。`coordinator` が必要性判断し、必要時のみ進言して適用する。
2. MCP適用候補:
- UI/UX 実動作確認
- Protocol warning の再現と切り分け
- CLIログのみでは根拠不足の不具合再現
3. MCP を使った場合は `notes` に `mcp_evidence` を記録する。  
`mcp_evidence: tool=devtools, purpose=<目的>, result=<結果>, artifacts=<証跡パス>`
4. MCP 利用時も Gate 判定は別途満たす。MCP結果だけでは `done` を確定しない。
5. 秘密情報（鍵/トークン/PII）を MCP 操作・ログへ含めない。

## Task 契約（v2.8）
### 必須トップレベルキー
- `id`
- `title`
- `owner`
- `assignee`
- `status`
- `target_stack`
- `depends_on`
- `adr_refs`
- `local_flags`
- `warnings`
- `handoffs`
- `notes`
- `updated_at`

### `target_stack` 必須キー
- `language`
- `framework`
- `infra`

### `local_flags` 必須キー
- `major_decision_required`
- `documentation_sync_required`
- `tech_specialist_required`
- `qa_review_required`
- `research_track_enabled`
- `backend_security_required`
- `ux_review_required`

### `warnings` 契約
- `level`: `warning | error`
- `status`: `open | triaged | resolved`
- `code`:  
`PROTO_SCHEMA_MISMATCH` / `PROTO_FIELD_CASE_MISMATCH` / `PROTO_REQUIRED_FIELD_MISSING` / `PROTO_UNEXPECTED_FIELD` / `PROTO_HANDOFF_CONTEXT_MISSING`

## Gate 仕様
1. ADR Gate: `major_decision_required=true` の実装 task は ADR 条件充足前に開始禁止
2. Documentation Sync Gate: `documentation_sync_required=true` は `tech-writer` 完了前に `done` 禁止
3. Protocol Gate: `warnings.status=open` が残る task は `done` 禁止
4. Tech Gate: `tech_specialist_required=true` は specialist 完了前に `done` 禁止
5. QA Gate: `qa_review_required=true` は `code-critic` と `test-architect` 完了前に `done` 禁止
6. Backend Security Gate: `backend_security_required=true` は `backend/security-expert` 完了前に `done` 禁止
7. UX Gate: `ux_review_required=true` は `frontend/ux-specialist` 完了前に `done` 禁止
8. Research Gate: `research_track_enabled=true` かつ採用判断ありは `poc_result` と ADR 承認前に実装開始禁止
9. Secret Scan Gate: 最新の `validate-secrets` 成功確認前に `done` を確定しない
10. Role Gap Review Gate: `validate-role-gap-review` が失敗している間は運用変更 task の `done` を確定しない

## 検証コマンド
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate-states-index.ps1 -Path .\.codex\states\_index.yaml
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate-task-state.ps1 -Path .\.codex\states\TASK-00110-member-tier-migration.yaml
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate-secrets.ps1
python .\scripts\detect-role-gaps.py
python .\scripts\validate-role-gap-review.py
python .\scripts\validate-rule-examples-coverage.py
```

```bash
bash ./scripts/validate-states-index.sh ./.codex/states/_index.yaml
bash ./scripts/validate-task-state.sh ./.codex/states/TASK-00110-member-tier-migration.yaml
bash ./scripts/validate-secrets.sh
python3 ./scripts/detect-role-gaps.py
python3 ./scripts/validate-role-gap-review.py
python3 ./scripts/validate-rule-examples-coverage.py
```

## Cross-Repo Incident Registry（v2.8.x）
- 正本台帳は AgentTeams 本体の `knowledge/incidents/_index.yaml` と `knowledge/incidents/INC-*.yaml`。
- 各プロジェクトは `at sync` で `.codex/cache/incident-registry.yaml` と `.codex/cache/incident-registry.meta.yaml` を更新する。
- 事象発生時は `at report-incident --task-file <path> --code <warning_code> --summary <text> --project <name>` を実行し、task warning/notes と incident-registry 候補を更新する。
- 再発判定は `scripts/detect-recurring-incident.py` が担当し、閾値（14日/3回/2task）到達時に root-cause 証跡を必須化する。
- 同期鮮度検証は `scripts/validate-incident-sync-freshness.py`。CI では stale/missing を `INCIDENT_REGISTRY_STALE` として失敗化する。
- 台帳スキーマ検証は `scripts/validate-incident-registry.py` が担当する。

## テストケース（v2.6b）
1. `frontend/ux-specialist` に `instructions.md` と `skills/*.md` が存在
2. `local_flags.ux_review_required` を持つ task が validate 成功
3. `local_flags.ux_review_required` 欠落で validate 失敗
4. `ux_review_required=true` かつ UX証跡なし `done` で validate 失敗
5. `backend_security_required=true` かつ security証跡なし `done` で validate 失敗
6. `warnings.status=open` の task は `done` で validate 失敗
7. `detect-role-gaps` と `validate-role-gap-review` が CI で起動
8. `validate-secrets` 失敗で `done` を確定しない
9. `in_progress/in_review/done` task で宣言付き handoff がない場合 validate 失敗
10. 宣言に `team/role/task/action` のいずれか欠落がある場合 validate 失敗
11. 23ルールのいずれかで Good/Bad/Detection/Related Files 欠落がある場合 coverage validate 失敗
12. `frontend/code-reviewer` を `assignee` または `handoffs` に含む task は validate 失敗

## 前提
- `_index.yaml` と `_role-gap-index.yaml` の更新者は coordinator のみ
- `task_file_path` 以外の task ファイル更新は禁止
- CI 必須チェックを通らない変更はマージ不可

## Immediate Correction Addendum (v2.8.1)
- Improvement Proposal Rule: `status=blocked` または `warnings.status=open` を含む task は、`IMPROVEMENT_PROPOSAL type=<process|role|tool|rule|cleanup> priority=<high|medium|low> owner=coordinator summary=<text>` を `notes` または `handoffs.memo` に記録しない限り前進不可。
- Deprecation Hygiene: `.codex/deprecation-rules.yaml` を参照し、`scripts/validate-deprecated-assets.py` を CI/ローカルで必須実行する。

## AgentTeams Self-Update Contract
- AgentTeams 自己改善 task は coordinator 決裁後にのみ `self-update-agentteams` スクリプトで反映する。
- `--task-file` / `-TaskFile` を必須とし、`status=done` の task のみ self-update 実行可能とする。
- 反映順序は `validate-repo -> validate-task-state -> git add -A -> validate-self-update-evidence -> git commit -> git push` を固定する。
- `logs/e2e-ai-log.md` に `【稼働口上】` と `DECLARATION team=coordinator role=coordinator task=<task_id> action=self_update_commit_push` を追加し、同一commitでstageする。
- 実行コマンド:
  - `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\self-update-agentteams.ps1 -TaskFile .\.codex\states\TASK-00100-member-tier-adr.yaml -Message "chore(agentteams): self-update" -NoPush`
  - `bash ./scripts/self-update-agentteams.sh --task-file ./.codex/states/TASK-00100-member-tier-adr.yaml --message "chore(agentteams): self-update" --no-push`
