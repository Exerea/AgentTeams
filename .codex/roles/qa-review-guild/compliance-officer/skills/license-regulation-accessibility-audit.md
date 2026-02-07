# license-regulation-accessibility-audit

## Trigger
- 新規依存追加
- 規制対象機能または公開UI変更が含まれる時

## Goal
法務・規制・アクセシビリティ違反の持ち込みを防ぐ。

## Procedure
1. `task_file_path` の変更範囲と依存情報を確認する。
2. ライセンス適合性を確認する。
3. 規制・アクセシビリティ観点の逸脱を抽出する。
4. 是正要否を `notes` に明記する。

## Output Format
- compliance status（pass/fail）
- issue list
- required remediation
