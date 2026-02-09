# Operations Knowledge

推奨実行順:
1. `agentteams sync`
2. `agentteams orchestrate --task-file <TASK-*.yaml>`
3. `powershell -NoProfile -ExecutionPolicy Bypass -File .\\scripts\\validate-repo.ps1`

追加検証:
- `python .\\scripts\\validate-operation-evidence.py --task-file <task> --min-teams 3 --min-roles 5`
- `python .\\scripts\\validate-role-gap-review.py`
- `python .\\scripts\\validate-chat-guard-usage.py`
