# TAKT Orchestration Guide (v4 Canonical)

This is the only supported orchestration flow in AgentTeams v4.

## 1. Validate Environment

```bash
agentteams doctor
```

Doctor checks:

- git repository context
- `takt` command availability
- governance piece presence
- `.takt/tasks/TASK-*.yaml` validity

## 2. Prepare Task File

Create or update a task under `.takt/tasks/`:

```yaml
id: T-00140
title: final-code-review
status: todo
task: |
  Execute final governance review and close all open findings.
goal: "Release with full review evidence"
constraints: []
acceptance: []
flags:
  qa_required: true
  security_required: false
  ux_required: false
  docs_required: true
  research_required: false
warnings: []
handoffs: []
notes: ""
updated_at: 2026-02-10T00:00:00Z
```

## 3. Execute Orchestration

Default provider (`codex`):

```bash
agentteams orchestrate --task-file .takt/tasks/TASK-00140-final-code-review.yaml
```

Mock provider (CI/smoke):

```bash
agentteams orchestrate --task-file .takt/tasks/TASK-00140-final-code-review.yaml --provider mock --no-post-validate
```

## 4. Post Checks

If post-validation is enabled, CLI runs:

- `scripts/validate-takt-task.py`
- `scripts/validate-takt-evidence.py`

Manual governance audit:

```bash
agentteams audit --strict
```

## 5. Repository Validation

Linux:

```bash
bash ./scripts/validate-repo.sh
```

Windows:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate-repo.ps1
```

## Command Deprecation

The following commands are intentionally removed in v4 and return discontinued errors:

- `agentteams sync`
- `agentteams report-incident`
- `agentteams guard-chat`
