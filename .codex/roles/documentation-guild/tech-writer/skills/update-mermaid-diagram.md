# update-mermaid-diagram

## Trigger
- `task_file_path` の `local_flags.documentation_sync_required=true`
- 構造変更を含む差分（新規テーブル、新規 API フロー等）

## Goal
実装と同じ情報構造を図として反映し、変更理解のコストを下げる。

## Procedure
1. 対象 task の notes/handoffs と OpenAPI から変更点を抽出する。
2. `docs/guides/architecture.md` の Mermaid 図を更新する。
3. README の関連セクションに図またはリンクを追加する。
4. 図のノード名を実際のエンティティ/エンドポイント名に揃える。

## Output Format
- 更新した Mermaid 図
- 変更理由の短い説明
- handoff memo（更新対象ファイル一覧）
