# Architecture Guide

## Purpose
AgentTeams v2.3 の実装・通信・品質・研究・バックエンドセキュリティ連携フローを示す。

## Multi-Guild Flow (Mermaid)
```mermaid
flowchart LR
  USER[User Request] --> COORD[coordinator]
  COORD --> TASK[TASK-*.yaml]

  TASK --> IMPL[Implementation Roles]
  IMPL --> WARN{Protocol Warning?}
  WARN -- Yes --> PROTO_AUDIT[protocol-team/interaction-auditor]
  PROTO_AUDIT --> PROTO_ARCH[protocol-team/protocol-architect]
  PROTO_ARCH --> PROTO_OPT[protocol-team/prompt-optimizer]
  WARN -- No --> TECH

  PROTO_OPT --> TECH[tech-specialist-guild]
  TECH --> BSEC[backend/security-expert]
  BSEC --> QA[qa-review-guild/code-critic + test-architect]
  QA --> COMP[qa-review-guild/compliance-officer]

  TASK --> RND{research_track_enabled?}
  RND -- Yes --> TREND[innovation-research-guild/trend-researcher]
  TREND --> POC[innovation-research-guild/poc-agent]
  POC --> ADR[documentation-guild/adr-manager]
  RND -- No --> ADR

  ADR --> API[documentation-guild/api-spec-owner]
  API --> DOC[documentation-guild/tech-writer]
  COMP --> COORD
  DOC --> COORD
  COORD --> INDEX[_index.yaml]
```

## State Topology
- 全体俯瞰: `.codex/states/_index.yaml`
- task 詳細: `.codex/states/TASK-*.yaml`
- 警告証跡: `warnings[]`
- 技術ルーティング: `target_stack.*`
- バックエンドセキュリティゲート: `local_flags.backend_security_required`

## Notes
- API 契約の正本は `docs/api/openapi.yaml`
- 通信規約の正本は `docs/guides/communication-protocol.md`
- `qa_review_required=true` の task は QA 完了前に `done` 不可
- `backend_security_required=true` の task は `backend/security-expert` 完了前に `done` 不可
- バックエンド実装は `Security先行 -> QA` を基本順序とする
- `research_track_enabled=true` の採用判断は `poc_result + ADR承認` が必須
