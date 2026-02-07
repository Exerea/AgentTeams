# ADR-0002: Agent Collaboration State Policy (Atomic States)

- Status: accepted
- Date: 2026-02-07
- Deciders: coordinator
- Supersedes: none

## Context
複数エージェントが並行作業する際、単一巨大 state ファイルは誤更新と競合を誘発しやすい。  
また、担当外タスクの状態が同一ファイルに混在すると、ロール境界が崩れやすい。

## Decision
状態管理の正本を `.codex/states/` に移行し、`1タスク=1ファイル` の Atomic States を採用する。  
全体俯瞰は `.codex/states/_index.yaml`、詳細は `.codex/states/TASK-*.yaml` に分離する。  
`_index.yaml` は coordinator のみ更新可能、専門ロールは `task_file_path` で指定された task ファイルのみ更新可能とする。

## Consequences
- メリット: タスク間の誤更新リスクを物理的に遮断できる。並行作業時のコンフリクトが減る。
- メリット: task 単位の履歴追跡が容易になる。
- デメリット: coordinator に index 同期責務が集中するため、運用ルールの明文化が必須。

## Alternatives Considered
1. 単一巨大 state ファイルを継続運用する。
2. ロール別 state ファイルに分割する。
3. 外部タスク管理サービスを唯一の連携面にする。

## References
- canonical index: `.codex/states/_index.yaml`
- canonical task files: `.codex/states/TASK-*.yaml`
- coordinator rules: `.codex/coordinator.md`
