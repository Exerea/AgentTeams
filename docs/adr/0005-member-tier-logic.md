# ADR-0005: Member Tier Logic for VIP Feature

- Status: accepted
- Date: 2026-02-07
- Deciders: coordinator, documentation-guild/adr-manager
- Supersedes: none

## Context
会員ランク（VIP）機能の導入にあたり、将来のランク追加と特典拡張に耐えられるデータモデルが必要となった。

## Decision
`member_tiers` テーブルを導入し、ランク情報を正規化して API から取得可能にする。

## Consequences
- メリット: ランク追加時の変更コストを抑制できる。
- デメリット: マイグレーションと API 契約更新が必須となる。

## Alternatives Considered
1. ユーザーテーブルへ rank カラムを直接追加する。
2. ランクを固定 enum でアプリ内ハードコードする。
3. 別サービスへ分離する。

## References
- related specs: `docs/specs/0001-agentteams-as-is-operations.md`
- api contract: `docs/api/openapi.yaml`
- related ADRs: `docs/adr/0002-state-management-policy.md`
