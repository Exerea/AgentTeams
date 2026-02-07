# Rule Examples (v2.7)

## Purpose
`.codex/AGENTS.md` の `Non-Negotiable Rules` 23件に対して、判定に迷わないよう `Good/Bad` 例を固定化する。  
解釈が割れた場合は本ファイルを優先参照する。

## Mapping
- `R-01` 〜 `R-23` は `.codex/AGENTS.md` のルール番号と 1:1 対応
- ルール改訂時は本ファイルを同時更新する

## R-01
### Rule
実装前に `docs/adr/*.md` を確認する。
### Intent
既存判断を壊す実装を防ぐ。
### Good Example
```text
開始前に docs/adr/0005-member-tier-logic.md を確認し、task notes に参照結果を記録した。
```
### Bad Example
```text
ADR未確認のまま schema 変更を実装し、既存方針と矛盾した。
```
### Why Bad
過去の意思決定を無視すると、同じ議論の再発と設計不整合を招く。
### Detection
- manual review（`coordinator` の ADR Gate 運用で確認）
### Related Files
- `.codex/AGENTS.md`
- `.codex/coordinator.md`
- `docs/adr/`

## R-02
### Rule
`task_file_path` で指定された task ファイル以外を更新しない。
### Intent
並行作業時の誤更新と衝突を防ぐ。
### Good Example
```text
担当ロールは TASK-00110 のみ更新し、他 task は触らない。
```
### Bad Example
```text
担当外の TASK-00120 をついでに更新してしまった。
```
### Why Bad
Atomic States の前提が崩れ、責務追跡が不能になる。
### Detection
- manual review（変更ファイル差分レビュー）
### Related Files
- `.codex/AGENTS.md`
- `shared/skills/common-ops.md`
- `.codex/states/TASK-*.yaml`

## R-03
### Rule
`_index.yaml` と `_role-gap-index.yaml` は coordinator のみ更新する。
### Intent
全体状態の一貫性を単一責任で守る。
### Good Example
```text
実務ロールは handoff だけ更新し、index更新は coordinator が実施した。
```
### Bad Example
```text
api-spec-owner が _index.yaml の status を直接書き換えた。
```
### Why Bad
全体進捗の正本が分散し、監査不能になる。
### Detection
- manual review（index ファイルの更新者を確認）
### Related Files
- `.codex/AGENTS.md`
- `.codex/coordinator.md`
- `.codex/states/_index.yaml`
- `.codex/states/_role-gap-index.yaml`

## R-04
### Rule
task 更新時は `status` と `updated_at` を必ず更新する。
### Intent
時系列追跡と停滞検知を可能にする。
### Good Example
```yaml
status: in_review
updated_at: 2026-02-07T10:30:00Z
```
### Bad Example
```yaml
status: in_review
updated_at: 2026-02-07T03:15:00Z  # 変更後も据え置き
```
### Why Bad
最新状態が分からず、運用判断を誤る。
### Detection
- manual review（変更差分で `status/updated_at` 同時更新を確認）
### Related Files
- `.codex/AGENTS.md`
- `shared/skills/common-ops.md`
- `.codex/states/TASK-*.yaml`

## R-05
### Rule
宣言は二層で実施する。`chat` は口上 `【稼働口上】殿、ただいま <家老|足軽> の <team>/<role> が「<task_title>」を務めます。<要旨>` を作業開始時・ロール切替時・Gate判断時に明示し、`handoffs[].memo` 先頭行は `DECLARATION team=<team> role=<role> task=<task_id|N/A> action=<action>` を記録する。必要性判断で追加対応が有効なら `【進言】...` を続けて出す。
### Intent
「誰が動いているか」を常に可視化する。
### Good Example
```text
【稼働口上】殿、ただいま 足軽 の backend/security-expert が「入力検証レビュー」を務めます。入力検証の確認を行います。
【進言】API境界テストを追加し、UI実動作は DevTools MCP で再現確認します（理由: 認可漏れ再発リスクの低減）
memo: DECLARATION team=backend role=security-expert task=T-110 action=handoff_to_code_critic | 重大指摘なし。
```
### Bad Example
```text
T-310をやります。次どうぞ。
memo: handoff done
```
### Why Bad
殿様向けの可読性と機械検証の両方を失い、必要な追加対応の判断も抜ける。
### Detection
- `validate-task-state.ps1`
- `validate-task-state.sh`
- manual review（chat 口上の有無を確認）
### Related Files
- `.codex/AGENTS.md`
- `.codex/coordinator.md`
- `docs/guides/communication-protocol.md`
- `.codex/states/TASK-*.yaml`

## R-06
### Rule
`local_flags.major_decision_required=true` は ADR 条件充足前に実装 task を `in_progress` にしない。
### Intent
重要判断を先に確定して実装の手戻りを防ぐ。
### Good Example
```text
ADR task done -> depends_on/adr_refs 反映 -> 実装 task を in_progress へ遷移。
```
### Bad Example
```text
ADR未作成のまま migration task を in_progress にした。
```
### Why Bad
決定理由のない実装が先行し、後から設計崩壊が起きる。
### Detection
- manual review（ADR Gate 運用確認）
### Related Files
- `.codex/AGENTS.md`
- `.codex/coordinator.md`
- `.codex/states/TASK-*.yaml`

## R-07
### Rule
API仕様の正本は `docs/api/openapi.yaml` とし、API変更は `documentation-guild/api-spec-owner` を経由する。
### Intent
実装とIF仕様の乖離を防ぐ。
### Good Example
```text
API変更 task で api-spec-owner が openapi.yaml を更新し、handoff を記録した。
```
### Bad Example
```text
実装だけ変更し openapi.yaml 未更新で完了扱いにした。
```
### Why Bad
クライアントとサーバ間の契約が破綻する。
### Detection
- manual review（OpenAPI更新と handoff を確認）
### Related Files
- `.codex/AGENTS.md`
- `docs/api/openapi.yaml`
- `.codex/roles/documentation-guild/api-spec-owner/instructions.md`

## R-08
### Rule
`local_flags.documentation_sync_required=true` は `documentation-guild/tech-writer` 完了前に `done` にしない。
### Intent
実装と利用者向け文書の同期を保証する。
### Good Example
```text
tech-writer handoff 後に task を done へ遷移。
```
### Bad Example
```text
README更新前に task を done にした。
```
### Why Bad
運用者が古い手順を参照し、誤運用を誘発する。
### Detection
- manual review（Documentation Sync Gate の運用確認）
### Related Files
- `.codex/AGENTS.md`
- `.codex/coordinator.md`
- `.codex/roles/documentation-guild/tech-writer/instructions.md`

## R-09
### Rule
`warnings.status=open` が残る task は `done` にしない。
### Intent
未解決の通信・連携不整合を持ち越さない。
### Good Example
```yaml
warnings:
  - id: W-001
    status: resolved
status: done
```
### Bad Example
```yaml
warnings:
  - id: W-001
    status: open
status: done
```
### Why Bad
既知不具合を抱えたまま完了扱いになり再発する。
### Detection
- `validate-task-state.ps1`
- `validate-task-state.sh`
### Related Files
- `.codex/AGENTS.md`
- `scripts/validate-task-state.ps1`
- `scripts/validate-task-state.sh`

## R-10
### Rule
`warnings.level=error` がある場合は remediation 完了前に downstream 実装を開始しない。
### Intent
重大障害の伝播をブロックする。
### Good Example
```text
error warning を triage -> remediation task done 後に downstream を再開。
```
### Bad Example
```text
error warning を無視して次工程を in_progress にした。
```
### Why Bad
障害が連鎖し、復旧コストが増大する。
### Detection
- manual review（Protocol Gate / triage 履歴確認）
### Related Files
- `.codex/AGENTS.md`
- `.codex/coordinator.md`
- `.codex/states/TASK-*.yaml`

## R-11
### Rule
コード変更 task は `local_flags.qa_review_required=true` を標準とし、`qa-review-guild/code-critic` と `qa-review-guild/test-architect` 完了前に `done` にしない。
### Intent
品質レビューとテスト設計を必須化する。
### Good Example
```yaml
local_flags:
  qa_review_required: true
handoffs:
  - from: qa-review-guild/code-critic
    to: qa-review-guild/test-architect
```
### Bad Example
```yaml
local_flags:
  qa_review_required: true
status: done
```
### Why Bad
レビュー工程スキップで品質劣化が本番へ流出する。
### Detection
- `validate-task-state.ps1`
- `validate-task-state.sh`
### Related Files
- `.codex/AGENTS.md`
- `.codex/roles/qa-review-guild/code-critic/instructions.md`
- `.codex/roles/qa-review-guild/test-architect/instructions.md`

## R-12
### Rule
`local_flags.backend_security_required=true` は `backend/security-expert` 完了前に `done` にしない。
### Intent
バックエンド脆弱性レビューを必須化する。
### Good Example
```yaml
local_flags:
  backend_security_required: true
handoffs:
  - from: backend/security-expert
    to: qa-review-guild/code-critic
```
### Bad Example
```yaml
local_flags:
  backend_security_required: true
status: done
```
### Why Bad
認可漏れや入力検証不備を見落とす。
### Detection
- `validate-task-state.ps1`
- `validate-task-state.sh`
### Related Files
- `.codex/AGENTS.md`
- `.codex/roles/backend/security-expert/instructions.md`
- `scripts/validate-task-state.ps1`

## R-13
### Rule
`backend_security_required=true` の標準適用条件は「外部公開API変更・認証/認可変更・PII取扱い変更」。
### Intent
高リスク変更でのセキュリティレビュー漏れを防ぐ。
### Good Example
```text
認可ロジック変更 task で backend_security_required=true を設定した。
```
### Bad Example
```text
外部API変更 task なのに backend_security_required=false のまま進行した。
```
### Why Bad
リスク分類が崩れ、Gate が機能しない。
### Detection
- manual review（coordinator の flag 設定確認）
### Related Files
- `.codex/AGENTS.md`
- `.codex/coordinator.md`
- `.codex/states/TASK-*.yaml`

## R-14
### Rule
バックエンドレビュー順序は `backend/security-expert -> qa-review-guild/code-critic -> qa-review-guild/test-architect` を基本とする。
### Intent
セキュリティ起点で QA を実施し、後戻りを減らす。
### Good Example
```text
api-architect -> security-expert -> code-critic -> test-architect の順で handoff。
```
### Bad Example
```text
code-critic 完了後に security-expert を実施した。
```
### Why Bad
security 指摘で QA をやり直すことになり効率が落ちる。
### Detection
- manual review（handoff 時系列確認）
### Related Files
- `.codex/AGENTS.md`
- `.codex/coordinator.md`
- `.codex/states/TASK-*.yaml`

## R-15
### Rule
`local_flags.tech_specialist_required=true` は該当 specialist 完了前に `done` にしない。
### Intent
言語/FW/Infra の専門観点を必要時に強制する。
### Good Example
```yaml
local_flags:
  tech_specialist_required: true
handoffs:
  - from: tech-specialist-guild/language-expert
    to: qa-review-guild/code-critic
```
### Bad Example
```yaml
local_flags:
  tech_specialist_required: true
status: done
```
### Why Bad
専門的アンチパターンの見落としが残る。
### Detection
- `validate-task-state.ps1`
- `validate-task-state.sh`
### Related Files
- `.codex/AGENTS.md`
- `.codex/roles/tech-specialist-guild/language-expert/instructions.md`
- `scripts/validate-task-state.sh`

## R-16
### Rule
`local_flags.research_track_enabled=true` かつ採用判断ありの場合、`poc_result` 記録と ADR 承認前に実装着手しない。
### Intent
新技術導入の意思決定品質を担保する。
### Good Example
```yaml
local_flags:
  research_track_enabled: true
notes: poc_result: pass (build -28%)
adr_refs:
  - 0010-adopt-fast-lib.md
```
### Bad Example
```yaml
local_flags:
  research_track_enabled: true
notes: pending
status: done
```
### Why Bad
検証根拠のない採用で技術負債が増える。
### Detection
- `validate-task-state.ps1`
- `validate-task-state.sh`
- manual review（着手タイミング確認）
### Related Files
- `.codex/AGENTS.md`
- `.codex/coordinator.md`
- `.codex/states/TASK-*.yaml`

## R-17
### Rule
`frontend/code-reviewer` は後継を `qa-review-guild/code-critic` とし、新規割当しない。
### Intent
レビュー責務を QA ギルドへ統一する。
### Good Example
```text
新規 task の assignee は qa-review-guild/code-critic を使用した。
```
### Bad Example
```text
新規 task を frontend/code-reviewer に割り当てた。
```
### Why Bad
新旧運用が混在し、判定ルールが分裂する。
### Detection
- manual review（assignee / handoff 宛先確認）
### Related Files
- `.codex/AGENTS.md`
- `.codex/roles/frontend/code-reviewer/instructions.md`
- `.codex/coordinator.md`

## R-18
### Rule
`local_flags.ux_review_required=true` は `frontend/ux-specialist` 完了前に `done` にしない。
### Intent
UI/導線変更の UX 品質を必須化する。
### Good Example
```yaml
local_flags:
  ux_review_required: true
handoffs:
  - from: frontend/ux-specialist
    to: qa-review-guild/code-critic
```
### Bad Example
```yaml
local_flags:
  ux_review_required: true
status: done
```
### Why Bad
体験品質の劣化や離脱増加を未検知でリリースしてしまう。
### Detection
- `validate-task-state.ps1`
- `validate-task-state.sh`
### Related Files
- `.codex/AGENTS.md`
- `.codex/roles/frontend/ux-specialist/instructions.md`
- `scripts/validate-task-state.ps1`

## R-19
### Rule
UX心理学レビューでは、認知負荷低減・導線明確化・段階的開示を確認し、ダークパターンを禁止する。
### Intent
改善効果と倫理性を同時に担保する。
### Good Example
```text
ux_checklist: pass
dark_pattern_risk: none
```
### Bad Example
```text
「今だけ残り1件」を根拠なく表示し、解約導線を隠した。
```
### Why Bad
短期指標は上がっても信頼毀損と離反を招く。
### Detection
- manual review（ux-specialist の notes/handoffs を確認）
### Related Files
- `.codex/AGENTS.md`
- `.codex/roles/frontend/ux-specialist/skills/ux-psychology-checklist.md`
- `.codex/roles/frontend/ux-specialist/skills/dark-pattern-risk-review.md`

## R-20
### Rule
`validate-secrets` の最新成功確認前に `done` を確定しない（Secret Scan Gate）。
### Intent
秘密情報の混入を最終段でブロックする。
### Good Example
```text
validate-secrets 成功を確認してから task を done に更新した。
```
### Bad Example
```text
secret scan 未実行のまま done にした。
```
### Why Bad
鍵情報漏洩は即時の重大事故に直結する。
### Detection
- `validate-secrets.ps1`
- `validate-secrets.sh`
- manual review（done 判定時の実行ログ確認）
### Related Files
- `.codex/AGENTS.md`
- `scripts/validate-secrets.ps1`
- `scripts/validate-secrets.sh`
- `.gitleaks.toml`

## R-21
### Rule
role gap 候補は `detect-role-gaps` で検知し、`.codex/states/_role-gap-index.yaml` に反映する。
### Intent
不足ロールの兆候を継続的に可視化する。
### Good Example
```text
CIで detect-role-gaps 実行後、candidate が _role-gap-index.yaml に作成された。
```
### Bad Example
```text
再発 warning が続いているのに role-gap 検知を回していない。
```
### Why Bad
運用改善ポイントを取り逃がし、同じ失敗を反復する。
### Detection
- `detect-role-gaps.py`
### Related Files
- `.codex/AGENTS.md`
- `.codex/role-gap-rules.yaml`
- `.codex/states/_role-gap-index.yaml`
- `scripts/detect-role-gaps.py`

## R-22
### Rule
`validate-role-gap-review` 失敗状態では運用変更 task の `done` を確定しない（Role Gap Review Gate）。
### Intent
未処理 candidate の放置を防ぐ。
### Good Example
```text
open candidate を triage してから運用変更 task を done にした。
```
### Bad Example
```text
open candidate が7日超過しているのに運用変更を done 扱いにした。
```
### Why Bad
ロール改善の未処理が蓄積し、運用品質が劣化する。
### Detection
- `validate-role-gap-review.py`
### Related Files
- `.codex/AGENTS.md`
- `.codex/states/_role-gap-index.yaml`
- `scripts/validate-role-gap-review.py`

## R-23
### Rule
`role_split/new_role` の反映は ADR を必須とし、`documentation-guild/adr-manager` 記録なしでは実施しない。
### Intent
ロール構造変更の理由と影響を監査可能にする。
### Good Example
```text
candidate accepted -> adr_ref 記録 -> 新ロール追加 -> decision_note に変更証跡を記録。
```
### Bad Example
```text
ADRなしで role ディレクトリを追加し、運用文書を更新しなかった。
```
### Why Bad
組織設計の根拠が消え、継承不能になる。
### Detection
- `validate-role-gap-review.py`
- manual review（adr-manager 記録確認）
### Related Files
- `.codex/AGENTS.md`
- `.codex/states/_role-gap-index.yaml`
- `.codex/roles/documentation-guild/adr-manager/instructions.md`
- `docs/adr/`

## Supplemental Notes (v2.8.1)
- 必要性判断: 追加レビュー・追加Gate・MCP活用の要否を都度確認する。
- 進言: 必要な追加対応は `【進言】...` で明示する。
- Improvement Proposal format: `IMPROVEMENT_PROPOSAL type=<process|role|tool|rule|cleanup> priority=<high|medium|low> owner=coordinator summary=<text>`
- Deprecated role reminder: `frontend/code-reviewer` は廃止済み扱いで、新規レビューは `qa-review-guild/code-critic` に統一する。
