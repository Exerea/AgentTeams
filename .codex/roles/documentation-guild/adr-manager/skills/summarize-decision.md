# summarize-decision

## Trigger
- `task_file_path` の `local_flags.major_decision_required=true`

## Goal
採用案/却下案を比較し、実装前に ADR へ意思決定の証跡を残す。

## Procedure
1. `task_file_path` の `notes` と `handoffs` を確認する。
2. PR 要約から候補案と評価軸を抽出する。
3. ADR に以下を記録する。
- 採用案
- 却下案
- 理由（コスト、リスク、互換性）
- 影響範囲
- 証跡（task id, handoff timestamp）
4. 対象 task の `adr_refs` と `depends_on` を更新する。

## Output Format
- ADR ファイル更新
- 対象 task の `status` 更新
- handoff memo に `ADR gate satisfied` を明記
