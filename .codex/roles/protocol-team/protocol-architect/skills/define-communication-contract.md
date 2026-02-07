# define-communication-contract

## Trigger
- `warnings.status=open` の通信不整合が発生した時
- 同種 warning が繰り返し検知された時

## Goal
通信仕様の曖昧さを排除し、再発しない契約へ明文化する。

## Procedure
1. `task_file_path` の `warnings`, `handoffs`, `notes` から失敗パターンを抽出する。
2. warning code ごとに禁止事項と許可事項を定義する。
3. 変更案を `.codex/AGENTS.md` と `docs/guides/communication-protocol.md` に反映する。
4. 影響ロールを列挙し、`prompt-optimizer` task の入力条件を作る。
5. coordinator 承認を受けるまで `proposed` 扱いで運用する。

## Output Format
- 更新規約の差分
- 影響ロール一覧
- 移行手順（旧仕様からの置換条件）
