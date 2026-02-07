# AgentTeams

Template Repo 前提で各プロジェクトに同梱して使う、マルチAIエージェント運用構成の `v2.6b` です。  
基盤は `Atomic States + Protocol Team + Documentation Guild` を維持し、`Tech Specialist / QA&Review / Innovation&Research`、`backend/security-expert`、`frontend/ux-specialist`、Secret Leakage 最終保証、Role Gap 半自動検知を統合しています。

## 目的
- 依頼の分解、実装、レビュー、文書更新を一貫運用する
- `1 task = 1 file` で衝突を避ける
- ゲートで品質を強制する（QA/Security/UX/Protocol/Secret/Role Gap）

## 正本ファイル
- 憲法: `.codex/AGENTS.md`
- 司令塔: `.codex/coordinator.md`
- 状態: `.codex/states/_index.yaml`, `.codex/states/TASK-*.yaml`
- ロール不足管理: `.codex/states/_role-gap-index.yaml`, `.codex/role-gap-rules.yaml`
- 共通運用: `shared/skills/common-ops.md`

## 主要方針（v2.6b）
1. `frontend/code-reviewer` は後継を `qa-review-guild/code-critic` とする
2. コード変更 task は `qa_review_required=true` を標準適用
3. 外部公開API/認証認可/PII変更は `backend_security_required=true` を標準適用
4. UI変更/導線変更/フォーム体験変更は `ux_review_required=true` を標準適用
5. `ux_review_required=true` の task は `frontend/ux-specialist` 完了前に `done` 不可（UX Gate）
6. `backend_security_required=true` の task は `backend/security-expert` 完了前に `done` 不可
7. `research_track_enabled=true` の採用判断は `poc_result + ADR承認` を必須
8. `detect-role-gaps` は候補検知、`validate-role-gap-review` は放置/証跡不備をブロック
9. `validate-secrets` 失敗時は `done` 不可（Secret Scan Gate）
10. 稼働宣言 `DECLARATION team=<team> role=<role> task=<task_id|N/A> action=<action>` を `chat + handoff memo` で必須化

## クイックスタート
- 運用シナリオ正本: `docs/guides/request-routing-scenarios.md`
- 依頼文テンプレは `User Request` をコピーして使う
- `coordinatorとして処理して` は推奨文であり必須ではない（coordinator がデフォルト受理）

## 稼働宣言プロトコル
- 宣言フォーマット: `DECLARATION team=<team> role=<role> task=<task_id|N/A> action=<action>`
- `chat`: 作業開始時とロール切替時に宣言する
- `task`: `handoffs.memo` の先頭行に宣言を記録する
- 例: `DECLARATION team=backend role=security-expert task=T-110 action=handoff_to_code_critic`

## ローカル検証
### Index
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate-states-index.ps1 -Path .\.codex\states\_index.yaml
```
```bash
bash ./scripts/validate-states-index.sh ./.codex/states/_index.yaml
```

### Task
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate-task-state.ps1 -Path .\.codex\states\TASK-00110-member-tier-migration.yaml
```
```bash
bash ./scripts/validate-task-state.sh ./.codex/states/TASK-00110-member-tier-migration.yaml
```

### Secret Scan
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate-secrets.ps1
```
```bash
bash ./scripts/validate-secrets.sh
```

### Role Gap
```powershell
python .\scripts\detect-role-gaps.py
python .\scripts\validate-role-gap-review.py
```
```bash
python3 ./scripts/detect-role-gaps.py
python3 ./scripts/validate-role-gap-review.py
```

### All-in-one
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate-repo.ps1
```
```bash
bash ./scripts/validate-repo.sh
```

## CI 必須チェック
ワークフロー: `.github/workflows/agentteams-validate.yml`

1. `validate-index-windows`
2. `validate-index-linux`
3. `validate-task-windows`
4. `validate-task-linux`
5. `validate-doc-consistency`
6. `validate-scenarios-structure`
7. `detect-role-gaps`
8. `validate-role-gap-review`
9. `validate-secrets-linux`

## Branch Protection
1. GitHub `Settings -> Branches -> Add rule` で `main` ルールを作成
2. `Require status checks to pass before merging` を有効化
3. 上記9チェックを Required checks に登録

## 運用メモ
- role gap 候補の状態遷移は `open -> triaged -> accepted/rejected -> implemented`
- `accepted` は `adr_ref` 必須
- `implemented` は `decision_note` に変更証跡必須
- `_index.yaml` と `_role-gap-index.yaml` は coordinator 専任更新
