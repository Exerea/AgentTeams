# ux-psychology-checklist

## Trigger
- `local_flags.ux_review_required=true`
- UI変更、導線変更、フォーム体験変更を含む task

## Checklist
1. 認知負荷: 一画面の選択肢が過剰でないか。
2. 視覚的階層: 重要要素が先に視認できるか。
3. 段階的開示: 初回に不要な情報を出し過ぎていないか。
4. 反応速度: 主要操作で体感遅延を許容していないか。
5. オンボーディング: 必要な瞬間だけガイドが出るか。
6. 行動誘導の倫理: 不当な圧力や誤認誘導がないか。

## Evidence Format
- `notes` に `ux_checklist:` セクションを記録する
- `handoffs` の `memo` に主要判断を1-2行で残す

## Output
- `pass` / `needs_fix` 判定
- 修正項目（優先度: high/medium/low）

