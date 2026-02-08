# Communication Protocol Guide

## Purpose
エージェント間の受け渡しを定型化し、解釈ミスと文脈欠落を防ぐ。

## Source of Truth
- 憲法: `.codex/AGENTS.md`
- 司令塔ルール: `.codex/coordinator.md`
- task 契約: `.codex/states/TASK-*.yaml`

## Required Handoff Fields
- `from`
- `to`
- `at`
- `memo`

## Declaration Format
- 固定開始宣言（人間向け / Task開始時のみ）  
`殿のご命令と各AGENTS.mdに忠実に従う家臣たちが集まりました。──家臣たちが動きます！`
- 口上（人間向け / chat 必須）  
`【稼働口上】殿、ただいま <家老|足軽> の <team>/<role> が「<task_title>」を務めます。<要旨>`
- 機械可読（既存 / task 必須）  
`DECLARATION team=<team> role=<role> task=<task_id|N/A> action=<action>`
- 進言（人間向け / 必要時）  
`【進言】<提案内容>（理由: <risk_or_benefit>）`
- 呼称マッピング  
- `ユーザー=殿様`
- `coordinator=家老`
- `coordinator以外の実行ロール=足軽`
- 適用面:
- `chat`: Task開始時は `固定開始宣言 -> 口上 -> DECLARATION` の3行をこの順で出す（固定開始宣言はTask開始時のみ）
- `chat`: ロール切替時・Gate判断時（停止/再開/完了確定）は口上 + 宣言を出す
- 口上は `task_id` 単独表現を禁止し、作業タイトルを必須記載する
- `chat` の標準ログは `logs/e2e-ai-log.md` とする（`at init` でテンプレート生成）
- `task`: `handoffs[].memo` の先頭行を宣言にする
- `notes`: 主要判断時は任意で宣言を追記する
- 必要性判断: 作業開始時と Gate判断時に「追加レビュー・追加Gate・MCP活用・先行調査」の要否を確認する
- 例:
- `殿のご命令と各AGENTS.mdに忠実に従う家臣たちが集まりました。──家臣たちが動きます！`
- `【稼働口上】殿、ただいま 家老 の coordinator/coordinator が「Backend Security Gate 判定」を務めます。判定を開始します。`
- `【進言】UI実動作確認のため DevTools MCP を併用します（理由: 画面回帰検知の精度向上）`
- `DECLARATION team=coordinator role=coordinator task=T-110 action=assign_backend_security_review`
- `DECLARATION team=backend role=security-expert task=T-110 action=handoff_to_code_critic`

## Declaration Good/Bad
- Good:
```text
【稼働口上】殿、ただいま 足軽 の backend/security-expert が「入力検証レビュー」を務めます。入力検証の確認を行います。
DECLARATION team=backend role=security-expert task=T-110 action=security_review
```
- Bad:
```text
T-110をやります。
```

## Required Warning Fields
- `id`
- `level` (`warning | error`)
- `code`
- `detected_by`
- `source_role`
- `target_role`
- `detected_at`
- `summary`
- `status` (`open | triaged | resolved`)
- `resolution_task_ids`
- `updated_at`

## Warning Codes
- `PROTO_SCHEMA_MISMATCH`
- `PROTO_FIELD_CASE_MISMATCH`
- `PROTO_REQUIRED_FIELD_MISSING`
- `PROTO_UNEXPECTED_FIELD`
- `PROTO_HANDOFF_CONTEXT_MISSING`

## Routing Metadata
- `target_stack.language`
- `target_stack.framework`
- `target_stack.infra`

## Operational Rules
1. 通信不整合を検知したロールは同一 task の `warnings[]` に即時記録する。
2. `warnings.status=open` が残る task は `done` にしない。
3. `warnings.level=error` は remediation 完了まで downstream 実装を開始しない。
4. 規約変更は `protocol-team/protocol-architect` 提案後、coordinator 承認で反映する。
5. 指示書更新は `protocol-team/prompt-optimizer` が対象ロール限定で実施する。
6. `qa_review_required=true` の task は `qa-review-guild/code-critic` と `qa-review-guild/test-architect` 完了前にクローズしない。
7. `status in (in_progress, in_review, done)` の task は、宣言フォーマットを含む handoff 証跡を最低1件持つ。

## Chat Log Validation
- 標準ログパス: `logs/e2e-ai-log.md`
- 必須:
1. `## Entries` セクションを保持する
2. Task開始時の先頭3エントリで `固定開始宣言` -> `【稼働口上】` -> `DECLARATION ...` を連続記録する
3. `実行` / `調べました` / `Ran` 系エントリ前に、直近宣言を残す
- 検証コマンド:
```powershell
python .\scripts\validate-chat-declaration.py
```
```bash
python3 ./scripts/validate-chat-declaration.py
```

## MCP Usage Pattern
1. MCP 使用前に口上と進言を出す。  
`【進言】UI実動作確認のため DevTools MCP を併用します（理由: 画面回帰検知の精度向上）`
2. handoff 先頭行は通常どおり `DECLARATION ...` を記録する。
3. `notes` に `mcp_evidence` を記録する。  
`mcp_evidence: tool=devtools, purpose=<目的>, result=<結果>, artifacts=<証跡パス>`
4. MCP 実行結果だけで完了判定しない。Gate 基準の充足を優先する。
5. 秘密情報（鍵/トークン/PII）を MCP 入力・画面・ログへ含めない。

## Improvement Proposal Pattern
- Trigger: status=blocked または warnings.status=open を保持したまま作業継続する場合。
- Required format: IMPROVEMENT_PROPOSAL type=<process|role|tool|rule|cleanup> priority=<high|medium|low> owner=coordinator summary=<text>
- Good:
DECLARATION team=coordinator role=coordinator task=T-210 action=gate_recheck | IMPROVEMENT_PROPOSAL type=process priority=high owner=coordinator summary=Security先行の再検証手順を追加
- Bad:
改善します （type/priority/owner/summary が欠落）

## Self-Update Declaration Example
- Chat口上例:
`【稼働口上】殿、ただいま 家老 の coordinator/coordinator が「AgentTeams自己更新の反映」を務めます。検証完了後に commit/push を実施します。`
- Handoff memo 例:
`DECLARATION team=coordinator role=coordinator task=T-999 action=self_update_commit_push`
- Self-update command examples:
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\self-update-agentteams.ps1 -TaskFile .\.codex\states\TASK-00100-member-tier-adr.yaml -NoPush
```
```bash
bash ./scripts/self-update-agentteams.sh --task-file ./.codex/states/TASK-00100-member-tier-adr.yaml --no-push
```
- `logs/e2e-ai-log.md` には `【稼働口上】` と `DECLARATION team=coordinator role=coordinator task=<task_id> action=self_update_commit_push` を追加し、同一commitでstageする。
