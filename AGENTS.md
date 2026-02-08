# AGENTS.md (Compatibility Pointer)

## AGENTS.md (Compatibility Pointer) の参照
* **Good Result:** 常に `.codex/AGENTS.md` を運用ルールの正本として読み込み、最新の指示に従って行動している。PowerShell を使用する際は `-Encoding utf8` を付与して文字化けを防止している。
* **Bad Result:** リポジトリ直下の `AGENTS.md`（ポインタ）の内容だけで判断し、正本である `.codex/AGENTS.md` の詳細ルールを確認せずに作業を進める。