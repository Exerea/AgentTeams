# Request Routing Scenarios

## Purpose
実運用で「依頼がどう task 化され、どのロールにどの順番で伝播されるか」を統一するための正本ガイド。

## Common Rules
- 依頼は必ず coordinator が受理し、`Goal/Constraints/Acceptance` に分解する。
- 各ロールは `task_file_path` で渡された `TASK-*.yaml` だけを更新する。
- `_index.yaml` は coordinator のみ更新する。
- handoff は `from/to/at/memo` を必須で記録する。
- `done` 判定は各 Gate 条件を満たした場合のみ許可する。

## Scenario 1: 機能追加（標準実装フロー）
### User Request
```text
coordinatorとして処理して。
Goal: 会員ランク一覧APIと管理画面表示を追加したい
Constraints: 既存API互換を維持
Acceptance:
- 一覧APIが取得できる
- 管理画面でランク表示できる
- OpenAPIとREADMEが更新される
```

### Coordinator Decomposition
- Goal: 会員ランク機能追加
- Constraints: 互換性維持、既存運用を壊さない
- Acceptance: API/UI/文書更新を満たす

### Task File Blueprint
```yaml
target_stack:
  language: typescript
  framework: nextjs
  infra: aws
local_flags:
  major_decision_required: false
  documentation_sync_required: true
  tech_specialist_required: false
  qa_review_required: true
  research_track_enabled: false
  backend_security_required: false
```

### Handoff Timeline
1. coordinator -> backend/api-architect（API設計）
2. backend/api-architect -> backend/db-specialist（必要時）
3. backend/* -> documentation-guild/api-spec-owner（OpenAPI同期）
4. documentation-guild/api-spec-owner -> documentation-guild/tech-writer（README/guide更新）
5. documentation-guild/tech-writer -> qa-review-guild/code-critic
6. qa-review-guild/code-critic -> qa-review-guild/test-architect
7. qa-review-guild/test-architect -> coordinator

### Gate Checks
- Documentation Sync Gate: tech-writer 完了前に `done` 不可
- QA Gate: code-critic/test-architect 完了前に `done` 不可
- Protocol Gate: `warnings.status=open` が残る場合 `done` 不可

### Completion Criteria
- API/UI/ドキュメントが反映済み
- `warnings.status=open` が 0 件
- QA 完了の handoff 証跡あり

### Validation Commands
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate-states-index.ps1 -Path .\.codex\states\_index.yaml
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate-task-state.ps1 -Path .\.codex\states\TASK-xxxxx-feature.yaml
```
```bash
bash ./scripts/validate-states-index.sh ./.codex/states/_index.yaml
bash ./scripts/validate-task-state.sh ./.codex/states/TASK-xxxxx-feature.yaml
```

## Scenario 2: 不具合修正（影響範囲限定フロー）
### User Request
```text
coordinatorとして処理して。
Goal: 会員ランク一覧APIが500を返す不具合を修正したい
Constraints: 既存レスポンス形式は変更しない
Acceptance:
- 500が解消される
- 回帰テストが追加される
- handoff証跡が残る
```

### Coordinator Decomposition
- Goal: 障害修正と再発防止
- Constraints: 互換性維持
- Acceptance: 修正 + テスト + 証跡

### Task File Blueprint
```yaml
target_stack:
  language: typescript
  framework: nextjs
  infra: aws
local_flags:
  major_decision_required: false
  documentation_sync_required: false
  tech_specialist_required: false
  qa_review_required: true
  research_track_enabled: false
  backend_security_required: false
```

### Handoff Timeline
1. coordinator -> backend/db-specialist（原因調査）
2. backend/db-specialist -> backend/api-architect（API影響確認）
3. backend/api-architect -> qa-review-guild/code-critic
4. qa-review-guild/code-critic -> qa-review-guild/test-architect
5. qa-review-guild/test-architect -> coordinator

### Gate Checks
- QA Gate: QA 未完了で `done` 不可
- Protocol Gate: open warning 残存で `done` 不可

### Completion Criteria
- 不具合再現手順で再発しない
- 回帰テスト観点が `notes` に記録済み
- QA handoff 済み

### Validation Commands
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate-task-state.ps1 -Path .\.codex\states\TASK-xxxxx-bugfix.yaml
```
```bash
bash ./scripts/validate-task-state.sh ./.codex/states/TASK-xxxxx-bugfix.yaml
```

## Scenario 3: バックエンドセキュリティ対応（Security先行）
### User Request
```text
coordinatorとして処理して。
Goal: 認証APIの権限判定不備を修正したい
Constraints: 既存クライアント互換を維持
Acceptance:
- 認可不備が解消される
- 監査ログが追跡できる
- Security先行でレビュー完了
```

### Coordinator Decomposition
- Goal: 認証/認可の脆弱性修正
- Constraints: API互換維持
- Acceptance: 修正 + security証跡 + QA完了

### Task File Blueprint
```yaml
target_stack:
  language: typescript
  framework: nextjs
  infra: aws
local_flags:
  major_decision_required: false
  documentation_sync_required: false
  tech_specialist_required: false
  qa_review_required: true
  research_track_enabled: false
  backend_security_required: true
```

### Handoff Timeline
1. coordinator -> backend/api-architect（実装）
2. backend/api-architect -> backend/security-expert（Security先行）
3. backend/security-expert -> qa-review-guild/code-critic
4. qa-review-guild/code-critic -> qa-review-guild/test-architect
5. qa-review-guild/test-architect -> coordinator

### Gate Checks
- Backend Security Gate: `backend/security-expert` 証跡なしで `done` 不可
- QA Gate: QA 未完了で `done` 不可
- Protocol Gate: open warning 残存で `done` 不可

### Completion Criteria
- セキュリティ重大指摘が残っていない
- Security先行 -> QA の handoff 順序が記録済み
- `backend_security_required=true` の task が validate 通過

### Validation Commands
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate-task-state.ps1 -Path .\.codex\states\TASK-xxxxx-backend-security.yaml
```
```bash
bash ./scripts/validate-task-state.sh ./.codex/states/TASK-xxxxx-backend-security.yaml
```

## Scenario 4: プロトコル警告起点の修復
### User Request
```text
coordinatorとして処理して。
Goal: BackendとFrontendのフィールド命名不一致を解消したい
Constraints: 既存利用者への影響を最小化
Acceptance:
- warningがresolvedになる
- 規約とドキュメントが同期される
- 再発防止策が反映される
```

### Coordinator Decomposition
- Goal: 通信不一致の解消と再発防止
- Constraints: 互換性と移行性の確保
- Acceptance: warning解消 + 規約/文書同期

### Task File Blueprint
```yaml
target_stack:
  language: typescript
  framework: nextjs
  infra: aws
local_flags:
  major_decision_required: true
  documentation_sync_required: true
  tech_specialist_required: false
  qa_review_required: true
  research_track_enabled: false
  backend_security_required: false
warnings:
  - id: W-001
    level: warning
    code: PROTO_FIELD_CASE_MISMATCH
    status: open
```

### Handoff Timeline
1. 実装ロール -> protocol-team/interaction-auditor（warning記録）
2. interaction-auditor -> coordinator（triage）
3. coordinator -> protocol-team/protocol-architect（規約案）
4. protocol-architect -> protocol-team/prompt-optimizer（指示更新）
5. prompt-optimizer -> documentation-guild/adr-manager（意思決定記録）
6. documentation-guild/adr-manager -> documentation-guild/tech-writer（ガイド更新）
7. coordinator が warning を `resolved` へ更新

### Gate Checks
- Protocol Gate: `warnings.status=open` で `done` 不可
- ADR Gate: `major_decision_required=true` 時は ADR条件充足まで実装開始不可
- Documentation Sync Gate: 文書同期前に `done` 不可

### Completion Criteria
- warning が `resolved`
- 規約更新と文書更新の handoff 証跡あり
- 変更理由が ADR に記録済み

### Validation Commands
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate-task-state.ps1 -Path .\.codex\states\TASK-xxxxx-protocol-fix.yaml
```
```bash
bash ./scripts/validate-task-state.sh ./.codex/states/TASK-xxxxx-protocol-fix.yaml
```

## Scenario 5: 新技術導入（PoC + ADR 承認）
### User Request
```text
coordinatorとして処理して。
Goal: 新ライブラリ導入でビルド時間短縮を検討したい
Constraints: 既存本番安定性を最優先
Acceptance:
- PoC結果が記録される
- 採用/非採用理由がADR化される
- 採用時のみ実装taskに着手する
```

### Coordinator Decomposition
- Goal: 新技術の採用判断
- Constraints: 安定性優先、リスク可視化
- Acceptance: PoC + ADR + QA 条件で意思決定

### Task File Blueprint
```yaml
target_stack:
  language: typescript
  framework: nextjs
  infra: aws
local_flags:
  major_decision_required: true
  documentation_sync_required: true
  tech_specialist_required: true
  qa_review_required: true
  research_track_enabled: true
  backend_security_required: false
notes: poc_result: pending
```

### Handoff Timeline
1. coordinator -> innovation-research-guild/trend-researcher
2. trend-researcher -> innovation-research-guild/poc-agent
3. poc-agent -> documentation-guild/adr-manager
4. adr-manager -> tech-specialist-guild/language-expert（必要に応じて framework/infra）
5. tech-specialist-guild -> qa-review-guild/code-critic
6. code-critic -> qa-review-guild/test-architect
7. qa-review-guild/test-architect -> coordinator（採用可否確定）

### Gate Checks
- Research Gate: `poc_result` と ADR承認前に採用実装 `in_progress` 不可
- Tech Gate: specialist 完了前に `done` 不可
- QA Gate: QA 未完了で `done` 不可

### Completion Criteria
- `notes` に `poc_result` 記録あり
- `adr_refs` が設定済み
- 採用判断の証跡が handoff に残る

### Validation Commands
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate-task-state.ps1 -Path .\.codex\states\TASK-xxxxx-research.yaml
```
```bash
bash ./scripts/validate-task-state.sh ./.codex/states/TASK-xxxxx-research.yaml
```
