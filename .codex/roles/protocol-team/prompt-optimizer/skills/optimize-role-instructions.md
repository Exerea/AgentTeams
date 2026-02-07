# optimize-role-instructions

## Trigger
- `protocol-architect` の規約変更案が coordinator 承認された時
- 同一 warning code が繰り返し発生した時

## Goal
対象ロールの指示書を改善し、通信エラーを事前に防ぐ。

## Procedure
1. task の対象ロール一覧を確認する（範囲外は更新禁止）。
2. 対象ロール `instructions.md` に以下を追記する。  
- 通信出力前チェック  
- warning 記録手順  
- handoff 必須情報
3. 変更前後で規約との差分を確認する。
4. handoff memo に更新対象ファイル一覧を記録する。

## Output Format
- 更新した `instructions.md` 一覧
- 変更理由
- 影響範囲とロール別注意点
