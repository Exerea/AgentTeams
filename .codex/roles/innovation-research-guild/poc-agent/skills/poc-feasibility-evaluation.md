# poc-feasibility-evaluation

## Trigger
- `local_flags.research_track_enabled=true`
- trend-researcher から handoff を受けた時

## Goal
候補技術の適合性を小規模検証で判定する。

## Procedure
1. `task_file_path` の評価項目と制約を確認する。
2. 検証条件、比較対象、成功基準を定義する。
3. 検証を実施し、結果を `notes` に `poc_result` として記録する。
4. 本導入前提の追加タスク（ADR/QA）を整理する。

## Output Format
- poc_result（success/fail）
- measured metrics
- adoption recommendation
