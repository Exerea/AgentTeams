# TAKT Orchestration Guide

## 概要
AgentTeams の運用を手動分散から `takt` による YAML オーケストレーションへ移行するガイド。

参照:
- https://zenn.dev/nrs/articles/c6842288a526d7
- https://github.com/nrslib/takt

## TAKTでできること（本プロジェクトで使う範囲）
- piece（YAML）でロール遷移を固定化
- parallel movement で奉行レビューを同時実行
- `all("approved")` / `any("needs_fix")` で機械的に再ルーティング
- pipeline モードで非対話実行（CIにも同じフローを適用）
- persona / policy / knowledge / output-contract を分離し、ルール改定の反映先を一元化

## 現状課題（構造監査ベース）
監査コマンド:
```powershell
python .\scripts\audit-agentteams-structure.py --states-dir .\.codex\states --log .\logs\e2e-ai-log.md --min-teams 3 --min-roles 5 --output .\docs\guides\takt-gap-analysis.md
```

主な検出傾向:
1. task ごとの `unique teams` / `unique roles` がしきい値未満
2. `qa_review_required=true` に対して QA 証跡が不足する task がある
3. chat log に読取証跡（`.codex/AGENTS.md`, `docs/adr/`）が不足

## 置換方針
1. coordinator 手動判断のみだった配分を piece へ移す
2. specialist レビューを `parallel` 化し、判定を `approved|needs_fix|blocked` に統一
3. `needs_fix` は自動的に fix movement へ戻す
4. `blocked` は coordinator-reroute movement で再配分 + IMPROVEMENT_PROPOSAL を強制
5. 最後は supervisor movement の承認がない限り COMPLETE しない

## 実行
```powershell
agentteams sync
agentteams orchestrate --task-file .\.codex\states\TASK-00140-final-code-review.yaml
```

厳格運用（分散証跡不足も失敗扱い）:
```powershell
agentteams orchestrate --task-file .\.codex\states\TASK-00140-final-code-review.yaml --strict-operation-evidence
```

## 関連ファイル
- piece: `.takt/pieces/agentteams-governance.yaml`
- config: `.takt/config.yaml`
- 監査: `scripts/audit-agentteams-structure.py`
- 監査結果: `docs/guides/takt-gap-analysis.md`
