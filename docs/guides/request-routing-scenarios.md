# Request Routing Scenarios

## Purpose
依頼文がどのように task へ分解され、どのロールへ伝播し、どの Gate で判定されるかを固定化する。
該当ルールの判定例は `docs/guides/rule-examples.md` を参照する。

## Common Rules
- 依頼は coordinator が受理し、`Goal/Constraints/Acceptance` に分解する。
- `coordinatorとして処理して` は推奨文であり必須ではない。文言がなくても coordinator が受理する。
- 作業ルートは「対象プロダクト repo のルート」を必須とする（`AgentTeams/<project>` 構成では `cd <project>` してから作業開始）。
- 導入確認は対象 repo 直下で `at doctor` を実行し、未導入なら `at init`（または `at init --here`）で是正する。
- 実務ロールは `task_file_path` で渡された `TASK-*.yaml` のみを更新する。
- `_index.yaml` と `_role-gap-index.yaml` の更新は coordinator 専任。
- handoff は `from/to/at/memo` を必須記録する。
- `chat` では作業開始時・ロール切替時・Gate判断時に口上を宣言する。  
`【稼働口上】殿、ただいま <家老|足軽> の <team>/<role> が「<task_title>」を務めます。<要旨>`
- 作業開始時と Gate判断時に必要性判断を行い、追加レビュー・追加Gate・MCP活用が有効なら進言を併記する。  
`【進言】<提案内容>（理由: <risk_or_benefit>）`
- MCP を使った場合は `notes` に `mcp_evidence` を記録する。  
`mcp_evidence: tool=devtools, purpose=<目的>, result=<結果>, artifacts=<証跡パス>`
- 口上で `task_id` のみ（例: `T-310`）を伝えることは禁止する。
- 呼称マッピング: `ユーザー=殿様`, `coordinator=家老`, `coordinator以外=足軽`
- handoff の `memo` 先頭行は宣言フォーマットを必須記録する。  
`DECLARATION team=<team> role=<role> task=<task_id|N/A> action=<action>`
- `frontend/code-reviewer` は廃止済みであり、新規 task の `assignee` / `handoffs` に使用しない（`qa-review-guild/code-critic` を使用）。
- `done` は各 Gate 条件を満たした場合のみ確定する。

## Scenario 1: 機能追加（UI導線あり）
### User Request
```text
会員ランク画面を追加したい。
Goal: 画面追加とAPI連携を実装する
Constraints: 既存デザイン規約を守る
Acceptance: UI/API/文書が一致し、回帰がない
```

### Coordinator Decomposition
- Goal: 会員ランク機能追加
- Constraints: 既存規約順守、既存API非破壊
- Acceptance: 実装/QA/文書同期完了

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
  ux_review_required: true
```

### Handoff Timeline
1. coordinator -> frontend/ui-designer
2. frontend/ui-designer -> frontend/ux-specialist
3. frontend/ux-specialist -> backend/api-architect
4. backend/api-architect -> documentation-guild/api-spec-owner
5. documentation-guild/api-spec-owner -> documentation-guild/tech-writer
6. documentation-guild/tech-writer -> qa-review-guild/code-critic
7. qa-review-guild/code-critic -> qa-review-guild/test-architect
8. qa-review-guild/test-architect -> coordinator
9. handoff memo 先頭行例: `DECLARATION team=frontend role=ux-specialist task=T-001 action=handoff_to_backend_api`
10. 開始時口上例: `【稼働口上】殿、ただいま 足軽 の frontend/ui-designer が「会員ランク画面UI初稿作成」を務めます。UI導線の初稿を作成します。`

### Gate Checks
- UX Gate: `ux_review_required=true` は `frontend/ux-specialist` 完了前に `done` 不可
- Documentation Sync Gate
- QA Gate
- Protocol Gate

### Completion Criteria
- UX証跡（チェックリスト結果）が `notes/handoffs` に記録されている
- API/OpenAPI/README が同期されている
- `warnings.status=open` がない

### Validation Commands
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate-task-state.ps1 -Path .\.codex\states\TASK-xxxxx-feature.yaml
```
```bash
bash ./scripts/validate-task-state.sh ./.codex/states/TASK-xxxxx-feature.yaml
```

## Scenario 2: 不具合修正（限定影響）
### User Request
```text
一覧APIで時々500が出る。coordinatorとして処理して。
Goal: 原因を特定して修正
Constraints: 既存仕様を変更しない
Acceptance: 再発防止と回帰テストがある
```

### Coordinator Decomposition
- Goal: 障害修正と再発防止
- Constraints: 仕様非変更
- Acceptance: 500解消とテスト追加

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
  ux_review_required: false
```

### Handoff Timeline
1. coordinator -> backend/db-specialist
2. backend/db-specialist -> backend/api-architect
3. backend/api-architect -> qa-review-guild/code-critic
4. qa-review-guild/code-critic -> qa-review-guild/test-architect
5. qa-review-guild/test-architect -> coordinator
6. handoff memo 先頭行例: `DECLARATION team=backend role=api-architect task=T-002 action=handoff_to_code_critic`
7. 開始時口上例: `【稼働口上】殿、ただいま 足軽 の backend/db-specialist が「500エラー原因切り分け」を務めます。原因を切り分けます。`

### Gate Checks
- QA Gate
- Protocol Gate

### Completion Criteria
- 再現条件で不具合が解消
- 追加テストが記録済み

### Validation Commands
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate-task-state.ps1 -Path .\.codex\states\TASK-xxxxx-bugfix.yaml
```
```bash
bash ./scripts/validate-task-state.sh ./.codex/states/TASK-xxxxx-bugfix.yaml
```

## Scenario 3: バックエンドセキュリティ対応
### User Request
```text
認証APIの脆弱性を修正したい。
Goal: 認可漏れを修正する
Constraints: 外部API互換を維持
Acceptance: セキュリティレビューとQAを通過
```

### Coordinator Decomposition
- Goal: 認証/認可の安全性強化
- Constraints: 互換性維持
- Acceptance: Security先行で完了

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
  ux_review_required: false
```

### Handoff Timeline
1. coordinator -> backend/api-architect
2. backend/api-architect -> backend/security-expert
3. backend/security-expert -> qa-review-guild/code-critic
4. qa-review-guild/code-critic -> qa-review-guild/test-architect
5. qa-review-guild/test-architect -> coordinator
6. handoff memo 先頭行例: `DECLARATION team=backend role=security-expert task=T-003 action=handoff_to_code_critic`
7. 開始時口上例: `【稼働口上】殿、ただいま 足軽 の backend/security-expert が「認可漏れ点検」を務めます。認可漏れを点検します。`

### Gate Checks
- Backend Security Gate
- QA Gate
- Protocol Gate

### Completion Criteria
- セキュリティ指摘が解消
- `backend/security-expert` の証跡が残る

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
BackendとFrontendの受け渡し形式が不一致。coordinatorとして処理して。
Goal: 警告を解消する
Constraints: 既存利用者影響を最小化
Acceptance: warning が resolved になる
```

### Coordinator Decomposition
- Goal: 通信規約の整合回復
- Constraints: 段階移行
- Acceptance: 規約/実装/文書同期

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
  ux_review_required: false
warnings:
  - id: W-001
    level: warning
    code: PROTO_FIELD_CASE_MISMATCH
    status: open
```

### Handoff Timeline
1. interaction-auditor -> coordinator（警告通知）
2. coordinator -> protocol-team/protocol-architect
3. protocol-architect -> protocol-team/prompt-optimizer
4. prompt-optimizer -> documentation-guild/adr-manager
5. documentation-guild/adr-manager -> documentation-guild/tech-writer
6. coordinator が warning を `resolved` に更新
7. handoff memo 先頭行例: `DECLARATION team=protocol-team role=interaction-auditor task=T-004 action=raise_protocol_warning`
8. 開始時口上例: `【稼働口上】殿、ただいま 足軽 の protocol-team/interaction-auditor が「通信警告の一次監査」を務めます。監査を行います。`

### Gate Checks
- Protocol Gate
- ADR Gate
- Documentation Sync Gate

### Completion Criteria
- warning が `resolved`
- 変更理由が ADR に残る
- OpenAPI/README/guide が同期

### Validation Commands
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate-task-state.ps1 -Path .\.codex\states\TASK-xxxxx-protocol-fix.yaml
```
```bash
bash ./scripts/validate-task-state.sh ./.codex/states/TASK-xxxxx-protocol-fix.yaml
```

## Scenario 5: 新技術導入（PoC + ADR）
### User Request
```text
新しい高速ライブラリを検証したい。coordinatorとして処理して。
Goal: 導入可否を判断する
Constraints: 本番影響を出さない
Acceptance: PoC結果とADRで採否を確定
```

### Coordinator Decomposition
- Goal: 研究トラックで導入可否判断
- Constraints: 小規模検証
- Acceptance: PoC + ADR + QA

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
  ux_review_required: false
notes: poc_result: pending
```

### Handoff Timeline
1. coordinator -> innovation-research-guild/trend-researcher
2. trend-researcher -> innovation-research-guild/poc-agent
3. poc-agent -> documentation-guild/adr-manager
4. adr-manager -> tech-specialist-guild/language-expert
5. tech-specialist-guild/language-expert -> qa-review-guild/code-critic
6. code-critic -> qa-review-guild/test-architect
7. qa-review-guild/test-architect -> coordinator
8. handoff memo 先頭行例: `DECLARATION team=innovation-research-guild role=poc-agent task=T-005 action=handoff_to_adr_manager`
9. 開始時口上例: `【稼働口上】殿、ただいま 足軽 の innovation-research-guild/trend-researcher が「候補技術調査」を務めます。候補技術を調査します。`

### Gate Checks
- Research Gate
- Tech Gate
- QA Gate

### Completion Criteria
- `notes` に `poc_result` を記録
- `adr_refs` が設定済み
- 採否判断の証跡がある

### Validation Commands
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate-task-state.ps1 -Path .\.codex\states\TASK-xxxxx-research.yaml
```
```bash
bash ./scripts/validate-task-state.sh ./.codex/states/TASK-xxxxx-research.yaml
```

## Scenario 6: ロール不足検知起点（半自動）
### User Request
```text
最近同じ警告が再発している。coordinatorとして処理して。
Goal: ロール不足候補を評価する
Constraints: 検知は自動、承認はcoordinator
Acceptance: triage結果とADRが残る
```

### Coordinator Decomposition
- Goal: ロール不足候補の可視化と決裁
- Constraints: 誤検知を最小化
- Acceptance: candidate 状態遷移が追跡可能

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
  ux_review_required: false
notes: Role gap triage required
```

### Handoff Timeline
1. coordinator -> `detect-role-gaps.py`（候補生成）
2. coordinator -> protocol-team/interaction-auditor（証跡精査）
3. interaction-auditor -> documentation-guild/adr-manager（判断ADR）
4. adr-manager -> coordinator（accepted/rejected 決裁）
5. accepted の場合: coordinator -> 実装ロール（role_split/new_role反映）
6. 実装完了後: coordinator が candidate を `implemented` に更新
7. handoff memo 先頭行例: `DECLARATION team=coordinator role=coordinator task=T-006 action=triage_role_gap_candidate`
8. 開始時口上例: `【稼働口上】殿、ただいま 家老 の coordinator/coordinator が「不足ロール候補の裁定」を務めます。候補を裁定します。`

### Gate Checks
- Role Gap Review Gate
- ADR Gate
- Protocol Gate

### Completion Criteria
- `.codex/states/_role-gap-index.yaml` に候補と決裁結果が記録される
- `accepted` は `adr_ref` を持つ
- `implemented` は `decision_note` に変更証跡を持つ

### Validation Commands
```powershell
python .\scripts\detect-role-gaps.py
python .\scripts\validate-role-gap-review.py
```
```bash
python3 ./scripts/detect-role-gaps.py
python3 ./scripts/validate-role-gap-review.py
```

## Improvement Proposal Rule (Cross-Scenario)
- `status=blocked` または `warnings.status=open` の task は、以下の記録がない限り次工程へ進めない。
- `IMPROVEMENT_PROPOSAL type=<process|role|tool|rule|cleanup> priority=<high|medium|low> owner=coordinator summary=<text>`
