# ADR-0001: Use React Query for Server State

- Status: accepted
- Date: 2026-02-07
- Deciders: frontend/ui-designer, frontend/code-reviewer
- Supersedes: none

## Context
クライアント側で API データ取得ロジックが各画面に分散し、ローディング・エラーハンドリング・再取得戦略が不統一だった。

## Decision
サーバー状態管理は React Query を標準採用する。`fetch + useState` の個別実装は新規導入しない。

## Consequences
- メリット: キャッシュ戦略、再試行、バックグラウンド更新を統一できる。
- デメリット: 学習コストが増える。クエリキー設計を誤ると不整合が起きる。

## Alternatives Considered
1. SWR
2. Redux Toolkit Query
3. 自前実装

## References
- related specs: `docs/specs/0000-system-spec-template.md`
