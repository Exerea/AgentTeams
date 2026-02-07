# scan-trends-and-cves

## Trigger
- `local_flags.research_track_enabled=true`
- 新規導入候補の検討開始時

## Goal
導入候補の技術的価値とリスクを可視化する。

## Procedure
1. `task_file_path` と `target_stack` を確認する。
2. 候補技術の変更点、CVE、採用実績を調査する。
3. 効果（速度/開発効率）とリスク（互換/運用負荷）を整理する。
4. PoC 実施条件を `notes` に記載する。

## Output Format
- trend summary
- cve risk summary
- PoC 実施提案
