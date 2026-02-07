# framework-antipattern-check

## Trigger
- `local_flags.tech_specialist_required=true`
- フレームワーク依存変更が発生した時

## Goal
フレームワークのアンチパターンを検出し、将来の負債化を防ぐ。

## Procedure
1. `task_file_path` と `target_stack.framework` を確認する。
2. 公式推奨パターンとの差分を抽出する。
3. アンチパターンと回避策を `notes` に記録する。
4. 影響範囲を handoff memo にまとめる。

## Output Format
- アンチパターン一覧
- 推奨修正方針
- 次 handoff（infra-sre-expert or code-critic）
