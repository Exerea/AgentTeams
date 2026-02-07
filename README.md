# AgentTeams

Template Repo 前提で各プロジェクトに内包して使う、マルチAIエージェント運用構成の `v2.3` です。  
基盤は `Atomic States + Protocol Team + Documentation Guild` を維持しつつ、`Tech Specialist / QA&Review / Innovation&Research` に加えて `backend/security-expert` を追加しています。

## 目的
- 役割分離で実装品質・検証品質・技術更新を分離統治する
- `1タスク=1ファイル` で並列運用時の誤更新を防ぐ
- warning 起点の修復フローを標準化する
- 新技術導入を `PoC成功 + ADR承認` で統制する
- バックエンド脆弱性レビューを条件付き必須ゲートで統制する

## 構成
- 正本ルール: `.codex/AGENTS.md`
- 司令塔: `.codex/coordinator.md`
- 状態管理: `.codex/states/_index.yaml`, `.codex/states/TASK-*.yaml`
- 実装ロール: `.codex/roles/frontend/**`, `.codex/roles/backend/**`
- ドキュメントロール: `.codex/roles/documentation-guild/**`
- 通信ロール: `.codex/roles/protocol-team/**`
- 技術ロール: `.codex/roles/tech-specialist-guild/**`
- 品質ロール: `.codex/roles/qa-review-guild/**`
- 研究ロール: `.codex/roles/innovation-research-guild/**`
- 共通運用: `shared/skills/common-ops.md`
- 運用スクリプト: `scripts/`

## 利用シナリオ集
- 実運用の依頼テンプレ、task配賦、handoff時系列の正本: `docs/guides/request-routing-scenarios.md`
- まず coordinator 依頼文を作る場合はこのガイドの `User Request` をコピーして使う

## v2.3 の主要方針
1. `frontend/code-reviewer` は即時に `qa-review-guild/code-critic` へ置換
2. ゲート方針は `QA必須・Tech条件付き・R&D任意`
3. 専門性は `target_stack.language/framework/infra` でルーティング
4. R&D採用条件は `PoC成功 + ADR承認`
5. `local_flags.backend_security_required=true` の task は `backend/security-expert` 完了前に `done` 禁止
6. `backend_security_required=true` の標準条件は「外部公開API・認証/認可・PII変更」
7. バックエンド実装レビュー順序は `Security先行 -> QA`

## クイックスタート
### 状態検証
PowerShell（index）:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate-states-index.ps1 -Path .\.codex\states\_index.yaml
```

PowerShell（task）:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate-task-state.ps1 -Path .\.codex\states\TASK-00110-member-tier-migration.yaml
```

Bash（index）:

```bash
bash ./scripts/validate-states-index.sh ./.codex/states/_index.yaml
```

Bash（task）:

```bash
bash ./scripts/validate-task-state.sh ./.codex/states/TASK-00110-member-tier-migration.yaml
```

### 他プロジェクトへ適用
PowerShell:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\bootstrap-agent-teams.ps1 --target ..\your-project
```

Bash:

```bash
bash ./scripts/bootstrap-agent-teams.sh --target ../your-project
```

既存ファイルも上書きしたい場合は `--force` を追加します。

## 運用フロー例（トレンド起点）
1. `innovation-research-guild/trend-researcher` が候補技術を提案
2. `innovation-research-guild/poc-agent` が `poc_result` を記録
3. `tech-specialist-guild` が互換性・性能・運用影響を評価
4. `documentation-guild/adr-manager` が採用理由を ADR 化
5. `qa-review-guild/code-critic` と `qa-review-guild/test-architect` が品質確認
6. coordinator が `PoC成功 + ADR承認 + QA完了` を満たした task のみ実装開始を許可

## 運用フロー例（バックエンド実装）
1. `backend/api-architect` または `backend/db-specialist` が実装 task を進行
2. `backend_security_required=true` の場合、`backend/security-expert` が先行レビュー
3. セキュリティ完了後に `qa-review-guild/code-critic` と `qa-review-guild/test-architect` を実施
4. coordinator が `Backend Security Gate + QA Gate` 充足を確認して `done` を確定

## 受け入れ確認
- 新3ギルドの全ロールに `instructions.md` と `skills/*.md` が存在する
- `backend/security-expert` ロールに `instructions.md` と `skills/*.md` が存在する
- 全 `TASK-*.yaml` に `target_stack` と拡張 `local_flags`（`backend_security_required` 含む）が存在する
- `validate-task-state` が `warnings` と新フラグ契約を検証できる
- `qa_review_required=true` の task が QA未完了で `done` にならない運用ルールがある
- `backend_security_required=true` の task が security未完了で `done` にならない運用ルールがある
