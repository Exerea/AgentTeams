# Architecture Guide

## Purpose
AgentTeams の運用制御、役割連携、主要ゲートを俯瞰する。

## Multi-Guild Flow (Mermaid)
```mermaid
flowchart LR
  USER[User Request] --> COORD[coordinator]
  COORD --> TASK[TASK-*.yaml]

  TASK --> UID[frontend/ui-designer]
  UID --> UX[frontend/ux-specialist]
  UX --> FSEC{frontend security required?}
  FSEC -- yes --> FSECR[frontend/security-expert]
  FSEC -- no --> QA1
  FSECR --> QA1[qa-review-guild/code-critic]
  QA1 --> QA2[qa-review-guild/test-architect]

  TASK --> BAPI[backend/api-architect]
  BAPI --> BDB[backend/db-specialist]
  BDB --> BSEC[backend/security-expert]
  BSEC --> QA1

  TASK --> WARN{Protocol Warning?}
  WARN -- yes --> IA[protocol-team/interaction-auditor]
  IA --> PA[protocol-team/protocol-architect]
  PA --> PO[protocol-team/prompt-optimizer]
  PO --> DOCADR

  TASK --> DOCADR[documentation-guild/adr-manager]
  DOCADR --> DOCAPI[documentation-guild/api-spec-owner]
  DOCAPI --> DOCTW[documentation-guild/tech-writer]
  QA2 --> DOCTW
  DOCTW --> COORD

  TASK --> RND{research_track_enabled?}
  RND -- yes --> TREND[innovation-research-guild/trend-researcher]
  TREND --> POC[innovation-research-guild/poc-agent]
  POC --> DOCADR

  COORD --> INDEX[_index.yaml (coordinator only)]
  COORD --> RG[_role-gap-index.yaml (coordinator only)]
```

## State Topology
- 全体一覧: `.codex/states/_index.yaml`
- task 詳細: `.codex/states/TASK-*.yaml`
- ロール不足管理: `.codex/states/_role-gap-index.yaml`
- 警告管理: `warnings[]`
- ルーティング: `target_stack.*`
- ゲート制御: `local_flags.*`

## Key Gates
- `Documentation Sync Gate`: `local_flags.documentation_sync_required`
- `QA Gate`: `local_flags.qa_review_required`
- `Backend Security Gate`: `local_flags.backend_security_required`
- `UX Gate`: `local_flags.ux_review_required`
- `Research Gate`: `local_flags.research_track_enabled`
- `Protocol Gate`: `warnings.status=open`
- `Secret Scan Gate`: `validate-secrets` 最新成功必須
- `Role Gap Review Gate`: `validate-role-gap-review` 成功必須

## Notes
- API仕様の正本は `docs/api/openapi.yaml`。
- 通信規約の正本は `docs/guides/communication-protocol.md`。
- `_index.yaml` と `_role-gap-index.yaml` の更新者は coordinator のみ。

