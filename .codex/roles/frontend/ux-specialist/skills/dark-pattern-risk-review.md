# dark-pattern-risk-review

## Trigger
- 課金導線、登録導線、解約導線、通知同意導線を含む task

## Review Points
1. 強制: 不要な同意や操作を強要していないか。
2. 誤認誘導: ボタン文言/強調で誤解を生む設計がないか。
3. 過度な希少性煽り: 根拠のない限定表示がないか。
4. 解約阻害: 開始より解約が過度に難しくないか。
5. デフォルト設定: 利用者不利な初期値を隠していないか。

## Output
- リスク一覧（none/low/medium/high）
- 必要な修正提案
- `notes` に `dark_pattern_risk:` を記録

