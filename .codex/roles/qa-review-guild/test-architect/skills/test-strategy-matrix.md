# test-strategy-matrix

## Trigger
- `local_flags.qa_review_required=true`
- 変更点に複数レイヤ（API/DB/UI）が含まれる時

## Goal
変更影響に応じた最小十分なテスト行列を定義する。

## Procedure
1. `task_file_path` と差分範囲を確認する。
2. 影響レイヤごとに test type を割り当てる。
3. 失敗時の影響度を基に優先順位を定義する。
4. 必須ケースを `notes` に記録する。

## Output Format
- test matrix（layer x test type）
- 優先度付き実行計画
- 残リスクメモ
