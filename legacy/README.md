# Legacy Archive

This directory stores static artifacts from the pre-v4 codex runtime.

## Archived Assets
- `legacy/codex-states/TASK-*.yaml`: immutable task history migrated from the previous runtime source.

## Policy
- Files here are **read-only historical records**.
- Runtime and CI must not depend on assets under `legacy/`.
- Active execution source of truth is `.takt/` only.
