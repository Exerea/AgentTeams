# language-compat-and-performance-check

## Trigger
- `local_flags.tech_specialist_required=true`
- 言語仕様依存の変更が含まれる時

## Goal
言語仕様違反と性能劣化要因を早期に検出する。

## Procedure
1. `task_file_path` と `target_stack.language` を確認する。
2. 新規構文・破壊的仕様変更の互換性を点検する。
3. メモリ、並行処理、計算量観点でリスクを抽出する。
4. 必要な修正方針を `notes` に記録する。

## Output Format
- 互換性判定（pass/fail）
- 性能観点メモ
- 次 handoff（framework-specialist or code-critic）
