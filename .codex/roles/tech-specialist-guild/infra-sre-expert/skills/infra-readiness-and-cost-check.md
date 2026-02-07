# infra-readiness-and-cost-check

## Trigger
- `target_stack.infra` が設定された task
- インフラ定義やデプロイ経路の変更時

## Goal
本番運用の準備度とコスト妥当性を事前評価する。

## Procedure
1. `task_file_path` の infra 条件を確認する。
2. 可用性、監視、ロールバック手順を点検する。
3. コスト増分と削減余地を記録する。
4. リリース可否の観点を `notes` に残す。

## Output Format
- readiness 判定（ready/not-ready）
- コスト影響メモ
- 次 handoff（test-architect / compliance-officer）
