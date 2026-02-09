# AgentTeams TAKT Configuration

このディレクトリは AgentTeams の実行オーケストレーションを TAKT で管理するための設定です。

## 目的
- タスク配分を手動から YAML オーケストレーションへ移行する
- 奉行レビュー（Security / UX / Protocol / Docs / QA / Role Gap）を並列で強制する
- 修正ループを経て、最終的にリーダー承認が出るまで完了しない

## 主要ファイル
- `config.yaml`: TAKT プロジェクト設定
- `pieces/agentteams-governance.yaml`: AgentTeams 専用 piece
- `personas/`: 役割別ペルソナ
- `policies/`: ルール束
- `knowledge/`: 参照知識
- `output-contracts/`: レポート形式

## 実行例
```bash
takt --pipeline --skip-git --piece .takt/pieces/agentteams-governance.yaml --task "<task instruction>"
```

実運用では `agentteams orchestrate --task-file <TASK-xxxxx-*.yaml>` を使用する。
