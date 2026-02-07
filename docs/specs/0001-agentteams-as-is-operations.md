# AgentTeams 現行構成と命令連携・運用サマリー（As-Is v2.3）

## Summary
このリポジトリは Template Repo として各案件に同梱し、coordinator が task 分解とロール割当を行う運用を前提に構成されています。  
状態管理の正本は `.codex/states/` で、`_index.yaml`（全体俯瞰）と `TASK-*.yaml`（個別カルテ）に分離します。  
v2.3 では `tech-specialist-guild`、`qa-review-guild`、`innovation-research-guild` に加えて `backend/security-expert` を追加し、バックエンド脆弱性レビューを明示統治します。

## 運用シナリオ正本
- 実運用の依頼テンプレ、task配賦、handoff時系列の正本は `docs/guides/request-routing-scenarios.md` とする。
- coordinator への依頼文は同ガイドの `User Request` テンプレを利用する。

## 現在のフォルダ構成
### 正本・司令塔
- `.codex/AGENTS.md`
- `.codex/coordinator.md`

### 状態管理
- `.codex/states/_index.yaml`
- `.codex/states/TASK-*.yaml`
- `.codex/states/archive/.gitkeep`

### ギルド構成
- 実装: `.codex/roles/frontend/*`, `.codex/roles/backend/*`
- Documentation: `.codex/roles/documentation-guild/*`
- Protocol: `.codex/roles/protocol-team/*`
- Tech Specialist: `.codex/roles/tech-specialist-guild/*`
- QA & Review: `.codex/roles/qa-review-guild/*`
- Innovation & Research: `.codex/roles/innovation-research-guild/*`

### ドキュメント
- ADR: `docs/adr/*.md`
- API 契約: `docs/api/openapi.yaml`
- ガイド: `docs/guides/*.md`
- 仕様: `docs/specs/*.md`

### スクリプト
- `scripts/bootstrap-agent-teams.ps1`
- `scripts/bootstrap-agent-teams.sh`
- `scripts/validate-states-index.ps1`
- `scripts/validate-states-index.sh`
- `scripts/validate-task-state.ps1`
- `scripts/validate-task-state.sh`

## 連携方式
### 制御プレーン
- coordinator が `Goal/Constraints/Acceptance` へ分解
- `target_stack` と `local_flags` を設定して task 起票
- `task_file_path` を必須引数で割当
- 外部公開API/認証/認可/PII 変更 task は `backend_security_required=true` を標準設定

### データプレーン
- task 更新は対象 `TASK-*.yaml` のみ
- handoff は `from/to/at/memo` で記録
- warning は `warnings[]` に記録

### ガバナンス
- ADR 参照を必須化
- QA必須・Tech条件付き・R&D任意トラック
- R&D採用条件は `PoC成功 + ADR承認`

## Task 契約（v2.2）
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

### `warnings` 契約
- `level`: `warning | error`
- `status`: `open | triaged | resolved`
- `code`:  
`PROTO_SCHEMA_MISMATCH` / `PROTO_FIELD_CASE_MISMATCH` / `PROTO_REQUIRED_FIELD_MISSING` / `PROTO_UNEXPECTED_FIELD` / `PROTO_HANDOFF_CONTEXT_MISSING`

## Gate 仕様
1. ADR Gate: `major_decision_required=true` の実装 task は ADR条件充足前に開始禁止
2. Protocol Gate: `warnings.status=open` が残る task は `done` 禁止
3. Tech Gate: `tech_specialist_required=true` は specialist 完了前に `done` 禁止
4. QA Gate: `qa_review_required=true` は `code-critic` と `test-architect` 完了前に `done` 禁止
5. Backend Security Gate: `backend_security_required=true` は `backend/security-expert` 完了前に `done` 禁止
6. Research Gate: `research_track_enabled=true` かつ採用判断ありは `poc_result` と ADR 承認前に実装開始禁止

## 日次運用コマンド
### Index 検証（PowerShell）
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate-states-index.ps1 -Path .\.codex\states\_index.yaml
```

### Task 検証（PowerShell）
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate-task-state.ps1 -Path .\.codex\states\TASK-00110-member-tier-migration.yaml
```

### Index 検証（Bash）
```bash
bash ./scripts/validate-states-index.sh ./.codex/states/_index.yaml
```

### Task 検証（Bash）
```bash
bash ./scripts/validate-task-state.sh ./.codex/states/TASK-00110-member-tier-migration.yaml
```

## テストケース（v2.3）
1. 新3ギルド全ロールに `instructions.md` と `skills/*.md` が存在
2. `target_stack` + 拡張 `local_flags` を持つ task が validate 成功
3. `target_stack` 欠落で validate 失敗
4. `local_flags.qa_review_required` 欠落で validate 失敗
5. `warnings.status=open` のまま `status=done` は validate 失敗
6. `local_flags.backend_security_required` 欠落で validate 失敗
7. `backend_security_required=true` かつ security 証跡なしで `status=done` は validate 失敗
8. `frontend/code-reviewer` が新規割当先として使われていない

## 前提とデフォルト
- `frontend/code-reviewer` は後継 `qa-review-guild/code-critic` へ即時置換
- QAは必須、Techは条件付き、R&Dは任意
- `backend_security_required=true` の標準条件は外部公開API・認証/認可・PII変更
- バックエンド実装のレビュー順序は `backend/security-expert -> code-critic -> test-architect`
- 外部調査の一次証跡は `notes/handoffs/warnings`
- CI 強制ゲートは次フェーズ（現状は運用 + ローカル validator）
