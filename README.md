# AgentTeams

Template Repo 前提で各プロジェクトに同梱して使う、マルチAIエージェント運用構成の `v2.8` です。  
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

## 主要方針（v2.8）
1. `frontend/code-reviewer` は廃止済みとし、正規レビュー担当は `qa-review-guild/code-critic` とする（新規割当は validator で失敗）
2. コード変更 task は `qa_review_required=true` を標準適用
3. 外部公開API/認証認可/PII変更は `backend_security_required=true` を標準適用
4. UI変更/導線変更/フォーム体験変更は `ux_review_required=true` を標準適用
5. `ux_review_required=true` の task は `frontend/ux-specialist` 完了前に `done` 不可（UX Gate）
6. `backend_security_required=true` の task は `backend/security-expert` 完了前に `done` 不可
7. `research_track_enabled=true` の採用判断は `poc_result + ADR承認` を必須
8. `detect-role-gaps` は候補検知、`validate-role-gap-review` は放置/証跡不備をブロック
9. `validate-secrets` 失敗時は `done` 不可（Secret Scan Gate）
10. 稼働宣言を二層化し、`chat` は日本語口上、`handoff memo` は `DECLARATION team=<team> role=<role> task=<task_id|N/A> action=<action>` を必須化
11. 作業開始時と Gate判断時に必要性判断を行い、追加レビュー・追加Gate・MCP活用が有効なら `【進言】...` を必須化

## クイックスタート
- 運用シナリオ正本: `docs/guides/request-routing-scenarios.md`
- ルール判定例正本: `docs/guides/rule-examples.md`
- 依頼文テンプレは `User Request` をコピーして使う
- `coordinatorとして処理して` は推奨文であり必須ではない（coordinator がデフォルト受理）

### 導入コマンド（推奨）
```bash
./scripts/install-at.sh
```
- Linux/macOS で `at` を直接使う場合は最初に実行（`~/.local/bin/at` を作成）

```powershell
at init <git-url>
at init --here
at init <git-url> -w <workspace-path>
```
```bash
./at init <git-url>
./at init --here
./at init <git-url> -w <workspace-path>
```
- `--agents-policy coexist|replace|keep`（既定: `coexist`）
- `at init` は clone 先ディレクトリを正規化し、`AGENTS.md` 競合を自動処理する
- `at init` を引数なしで実行した場合は、Repository URL を対話で確認する
- `bootstrap-agent-teams` は `at init` の内部実装として呼び出される
- `at init` 実行には `python`（または `py -3` / `python3`）が必要

### 内部互換コマンド（通常は不要）
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\bootstrap-agent-teams.ps1 --target <project-path>
```
```bash
bash ./scripts/bootstrap-agent-teams.sh --target <project-path>
```

## 稼働宣言プロトコル
- 口上テンプレ: `【稼働口上】殿、ただいま <家老|足軽> の <team>/<role> が「<task_title>」を務めます。<要旨>`
- 進言テンプレ: `【進言】<提案内容>（理由: <risk_or_benefit>）`
- 機械可読フォーマット: `DECLARATION team=<team> role=<role> task=<task_id|N/A> action=<action>`
- 呼称マッピング: `ユーザー=殿様`, `coordinator=家老`, `coordinator以外=足軽`
- `chat`: 作業開始時・ロール切替時・Gate判断時に口上 + 宣言を行う
- `chat`: 作業開始時・Gate判断時には必要性判断を行い、必要時は進言も併記する
- 口上では `T-310` のような `task_id` 単独表現を禁止し、作業タイトルを必ず伝える
- `task`: `handoffs.memo` の先頭行に宣言を記録する
- 例: `DECLARATION team=backend role=security-expert task=T-110 action=handoff_to_code_critic`

## MCP運用（DevTools MCP）
- 位置づけ: MCP は常時必須ではない。`coordinator` が必要性判断して有効と判断した場合に進言して使用する。
- 主な適用場面:
1. UI/UX レビューで実動作確認が必要な場合
2. Protocol warning の再現（Network/Console/DOM確認）が必要な場合
3. 不具合の再現条件が CLI ログだけでは不足する場合
- 証跡の残し方:
1. `chat` に `【進言】...DevTools MCP...` を明記
2. `handoffs.memo` 先頭に `DECLARATION ... action=...` を記録
3. `notes` に `mcp_evidence` を記録
`mcp_evidence: tool=devtools, purpose=<目的>, result=<結果>, artifacts=<スクリーンショット/ログの場所>`
- 禁止事項:
1. 秘密情報（鍵/トークン/個人情報）を画面・ログへ貼り付けない
2. 本番データを無断で操作しない
3. MCP結果のみで確定せず、該当 Gate の基準（QA/Security/Protocol等）を併せて満たす

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
- `gitleaks` 未導入時は初回実行で `./.tools/gitleaks/` に自動取得して実行する（既存導入済みがあればそちらを優先）

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

### `at init` E2E
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test-at-init.ps1
```

## CI 必須チェック
ワークフロー: `.github/workflows/agentteams-validate.yml`

1. `validate-index-windows`
2. `validate-index-linux`
3. `validate-task-windows`
4. `validate-task-linux`
5. `validate-doc-consistency`
6. `validate-scenarios-structure`
7. `validate-rule-examples-coverage`
8. `detect-role-gaps`
9. `validate-role-gap-review`
10. `validate-secrets-linux`

## Branch Protection
1. GitHub `Settings -> Branches -> Add rule` で `main` ルールを作成
2. `Require status checks to pass before merging` を有効化
3. 上記10チェックを Required checks に登録

## 運用メモ
- role gap 候補の状態遷移は `open -> triaged -> accepted/rejected -> implemented`
- `accepted` は `adr_ref` 必須
- `implemented` は `decision_note` に変更証跡必須
- `_index.yaml` と `_role-gap-index.yaml` は coordinator 専任更新
- ルール解釈が曖昧な場合は `docs/guides/rule-examples.md` の Good/Bad を優先する
- `detect-role-gaps.py` は新規候補や内容変化がある場合のみ `_role-gap-index.yaml` を更新する

## Immediate Correction (v2.8.1)
- Improvement Proposal Rule: `status=blocked` または `warnings.status=open` が残る task は、`IMPROVEMENT_PROPOSAL type=<process|role|tool|rule|cleanup> priority=<high|medium|low> owner=coordinator summary=<text>` を `notes` か `handoffs.memo` に必須記録する。
- Deprecation Hygiene: `.codex/deprecation-rules.yaml` を正本とし、`scripts/validate-deprecated-assets.py` で廃止資産の残存と再混入を検査する。

### Deprecation Validation
```powershell
python .\scripts\validate-deprecated-assets.py
```
```bash
python3 ./scripts/validate-deprecated-assets.py
```

## AgentTeams Self-Update
AgentTeams 自身の改善を commit/push まで自動化したい場合は以下を使用する。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\self-update-agentteams.ps1 -Message "chore(agentteams): self-update" 
```

```bash
bash ./scripts/self-update-agentteams.sh --message "chore(agentteams): self-update"
```

### オプション
- `--skip-validate`: 事前の `validate-repo` をスキップ（通常は非推奨）
- `--no-push`: commit のみ作成して push しない
