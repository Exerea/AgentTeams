# Handoff And Gates Policy

- handoff memo の先頭行は必ず `DECLARATION team=<team> role=<role> task=<task_id|N/A> action=<action>`
- blocked または unresolved warning がある場合は `IMPROVEMENT_PROPOSAL type=<...> priority=<...> owner=coordinator summary=<...>` を残す
- 作業は「実装 -> 奉行レビュー並列 -> 修正 -> 再レビュー」の循環で収束させる
- 最終承認は supervisor のみ
