#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys

try:
    import yaml  # type: ignore
except Exception:
    yaml = None


PRIMARY_CLI = "agentteams"
WINDOWS_COMPAT_CLI = r".\at.cmd"
UNIX_COMPAT_CLI = "./at"
TASK_FILE_PATTERN = "TASK-*.yaml"
TASK_STATUSES = {"todo", "in_progress", "in_review", "blocked", "done"}
REMOVED_COMMANDS = {"sync", "report-incident", "guard-chat"}


def cli_command(command: str, include_compat: bool = False) -> str:
    normalized = command.strip()
    primary = f"{PRIMARY_CLI} {normalized}".strip()
    if not include_compat:
        return primary
    compat_cli = WINDOWS_COMPAT_CLI if os.name == "nt" else UNIX_COMPAT_CLI
    return f"{primary} (compat: {compat_cli} {normalized})"


def usage() -> None:
    print("Usage:")
    print("  agentteams init [<git-url>] [-w|--workspace <path>] [--verbose]")
    print("  agentteams init --here [--verbose]")
    print("  agentteams doctor [--verbose]")
    print(
        "  agentteams orchestrate --task-file <.takt/tasks/TASK-*.yaml> "
        "[--provider codex|claude|mock] [--no-post-validate] [--verbose]"
    )
    print("  agentteams audit [--min-teams <n>] [--strict] [--verbose]")
    print("Compatibility aliases:")
    print("  at <same-subcommand> ...")


def fail(code: str, message: str, next_command: str | None = None) -> int:
    print(f"ERROR [{code}] {message}")
    if next_command:
        print(f"Next: {next_command}")
    return 1


def info(verbose: bool, message: str) -> None:
    if verbose:
        print(f"[at] {message}")


def run_cmd(
    cmd: list[str],
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    print_output: bool = True,
) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    output = proc.stdout.strip()
    if output and print_output:
        print_safe(output)
    return proc.returncode, output


def print_safe(message: str) -> None:
    try:
        print(message)
    except UnicodeEncodeError:
        encoding = sys.stdout.encoding or "utf-8"
        safe = message.encode(encoding, errors="replace").decode(encoding, errors="replace")
        print(safe)


def resolve_takt_command() -> str | None:
    candidates = ["takt"]
    if os.name == "nt":
        candidates = ["takt.cmd", "takt.exe", "takt.bat", "takt"]

    for candidate in candidates:
        found = shutil.which(candidate)
        if found:
            return candidate
    return None


def ensure_git_available() -> int:
    if shutil.which("git") is None:
        return fail(
            "PATH_LAYOUT_INVALID",
            "git command not found.",
            f"Install git, then retry: {cli_command('init --here', include_compat=True)}",
        )
    return 0


def resolve_repo_root() -> Path | None:
    code, output = run_cmd(["git", "rev-parse", "--show-toplevel"], print_output=False)
    if code != 0 or not output:
        return None
    return Path(output.splitlines()[-1]).resolve()


def repo_name_from_url(repo_url: str) -> str:
    trimmed = repo_url.strip().rstrip("/\\")
    if not trimmed:
        return ""
    leaf = trimmed.replace("\\", "/").split("/")[-1]
    if leaf.endswith(".git"):
        leaf = leaf[:-4]
    return leaf.strip()


def invoke_bootstrap(template_root: Path, target_root: Path, verbose: bool) -> int:
    if template_root.resolve() == target_root.resolve():
        info(verbose, "target root equals template root; bootstrap copy skipped.")
        return 0

    ps_script = template_root / "scripts" / "bootstrap-agent-teams.ps1"
    sh_script = template_root / "scripts" / "bootstrap-agent-teams.sh"

    if os.name == "nt":
        if not ps_script.exists():
            return fail("BOOTSTRAP_FAILED", f"missing script: {ps_script.as_posix()}")
        code, _ = run_cmd(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(ps_script),
                "--target",
                str(target_root),
            ]
        )
        if code != 0:
            return fail("BOOTSTRAP_FAILED", f"bootstrap failed: {target_root.as_posix()}")
        return 0

    if not sh_script.exists():
        return fail("BOOTSTRAP_FAILED", f"missing script: {sh_script.as_posix()}")

    code, _ = run_cmd(["bash", str(sh_script), "--target", str(target_root)])
    if code != 0:
        return fail("BOOTSTRAP_FAILED", f"bootstrap failed: {target_root.as_posix()}")
    return 0


def parse_init_args(args: list[str]) -> tuple[str, bool, str, bool, int]:
    repo_url = ""
    use_here = False
    workspace = str(Path.cwd())
    verbose = False

    idx = 0
    while idx < len(args):
        token = args[idx]

        if token == "--here":
            use_here = True
            idx += 1
            continue
        if token in ("--workspace", "-w"):
            if idx + 1 >= len(args):
                return "", False, workspace, verbose, fail(
                    "PATH_LAYOUT_INVALID",
                    "--workspace requires a path value.",
                    "Usage: agentteams init [<git-url>] [-w|--workspace <path>]",
                )
            workspace = args[idx + 1]
            idx += 2
            continue
        if token == "--verbose":
            verbose = True
            idx += 1
            continue
        if token.startswith("-"):
            return "", False, workspace, verbose, fail(
                "PATH_LAYOUT_INVALID",
                f"unknown option for init: {token}",
                "Usage: agentteams init [<git-url>] [-w|--workspace <path>] [--here] [--verbose]",
            )

        if repo_url:
            return "", False, workspace, verbose, fail(
                "PATH_LAYOUT_INVALID",
                f"unexpected extra positional argument: {token}",
                "Usage: agentteams init [<git-url>] [-w|--workspace <path>]",
            )

        repo_url = token
        idx += 1

    if use_here and repo_url:
        return "", False, workspace, verbose, fail(
            "PATH_LAYOUT_INVALID",
            "cannot use --here with repository URL.",
            "Usage: agentteams init --here",
        )

    return repo_url, use_here, workspace, verbose, 0


def init_here(template_root: Path, verbose: bool) -> int:
    target_root = resolve_repo_root()
    if target_root is None:
        return fail(
            "PATH_LAYOUT_INVALID",
            "--here can only be used inside a git repository.",
            f"For clone mode: {cli_command('init <git-url>', include_compat=True)}",
        )

    info(verbose, f"target root: {target_root.as_posix()}")
    code = invoke_bootstrap(template_root, target_root, verbose)
    if code != 0:
        return code

    print(f"{PRIMARY_CLI} init completed: {target_root.as_posix()}")
    return 0


def init_with_clone(template_root: Path, repo_url: str, workspace: str, verbose: bool) -> int:
    workspace_root = Path(workspace).expanduser().resolve()
    workspace_root.mkdir(parents=True, exist_ok=True)

    repo_name = repo_name_from_url(repo_url)
    if not repo_name:
        return fail(
            "PATH_LAYOUT_INVALID",
            f"unable to derive repository name from URL: {repo_url}",
            "Example: agentteams init https://github.com/<org>/<repo>.git",
        )

    target_root = workspace_root / repo_name
    if target_root.exists():
        return fail(
            "PATH_LAYOUT_INVALID",
            f"target already exists: {target_root.as_posix()}",
            f"For existing clone: {cli_command('init --here', include_compat=True)}",
        )

    info(verbose, f"cloning {repo_url} -> {target_root.as_posix()}")
    code, _ = run_cmd(["git", "clone", repo_url, str(target_root)])
    if code != 0:
        return fail("GIT_CLONE_FAILED", f"git clone failed: {repo_url}")

    code = invoke_bootstrap(template_root, target_root, verbose)
    if code != 0:
        return code

    print(f"{PRIMARY_CLI} init completed: {target_root.as_posix()}")
    return 0


def run_python_script(repo_root: Path, script_rel: str, args: list[str]) -> int:
    script = repo_root / script_rel
    if not script.exists():
        return fail("PATH_LAYOUT_INVALID", f"missing script: {script.as_posix()}")

    code, _ = run_cmd([sys.executable, str(script), *args], cwd=repo_root)
    if code != 0:
        return fail("VALIDATION_FAILED", f"script failed: {script_rel}")
    return 0


def doctor(verbose: bool) -> int:
    repo_root = resolve_repo_root()
    if repo_root is None:
        return fail(
            "AGENT_CONTEXT_MISSING",
            "current directory is not inside a git repository.",
            f"Next: {cli_command('init', include_compat=True)}",
        )

    print(f"OK [AGENT_CONTEXT_OK] git repository detected: {repo_root.as_posix()}")

    takt_cmd = resolve_takt_command()
    if takt_cmd is None:
        return fail(
            "TAKT_NOT_FOUND",
            "takt command not found.",
            "Install takt and retry: npm install -g takt",
        )
    print(f"OK [TAKT_AVAILABLE] takt command found ({takt_cmd})")

    piece = repo_root / ".takt" / "pieces" / "agentteams-governance.yaml"
    if not piece.exists():
        return fail("TAKT_PIECE_MISSING", f"missing piece: {piece.as_posix()}")
    print(f"OK [TAKT_PIECE_OK] found: {piece.as_posix()}")

    tasks_dir = repo_root / ".takt" / "tasks"
    if not tasks_dir.exists():
        return fail("TAKT_TASK_DIR_MISSING", f"missing tasks dir: {tasks_dir.as_posix()}")

    task_files = sorted(tasks_dir.glob(TASK_FILE_PATTERN))
    if not task_files:
        return fail("TAKT_TASKS_EMPTY", f"no task files under: {tasks_dir.as_posix()}")
    print(f"OK [TAKT_TASKS_FOUND] count={len(task_files)}")

    code = run_python_script(repo_root, "scripts/validate-takt-task.py", ["--path", ".takt/tasks"])
    if code != 0:
        return code

    info(verbose, "doctor checks completed")
    return 0


def require_yaml() -> int:
    if yaml is not None:
        return 0
    return fail(
        "PYTHON_DEP_MISSING",
        "PyYAML is required for task parsing.",
        "Install dependency: python -m pip install pyyaml",
    )


def compile_orchestration_prompt(task_file: Path, task: dict) -> str:
    def as_list(values: object) -> list[str]:
        if isinstance(values, list):
            return [str(v) for v in values]
        return []

    def as_dict_list(values: object) -> list[dict]:
        if not isinstance(values, list):
            return []
        out: list[dict] = []
        for item in values:
            if isinstance(item, dict):
                out.append(item)
        return out

    flags = task.get("flags") if isinstance(task.get("flags"), dict) else {}
    lines = [
        "You are executing an AgentTeams v4 governance task.",
        f"Task file: {task_file.as_posix()}",
        f"Task ID: {task.get('id', '')}",
        f"Title: {task.get('title', '')}",
        f"Status: {task.get('status', '')}",
        "",
        "Task body:",
        str(task.get("task", "")).strip(),
        "",
        f"Goal: {task.get('goal', '')}",
        "",
        "Constraints:",
    ]
    constraints = as_list(task.get("constraints"))
    if constraints:
        lines.extend([f"- {item}" for item in constraints])
    else:
        lines.append("- (none)")

    lines.append("")
    lines.append("Acceptance:")
    acceptance = as_list(task.get("acceptance"))
    if acceptance:
        lines.extend([f"- {item}" for item in acceptance])
    else:
        lines.append("- (none)")

    lines.append("")
    lines.append("Flags:")
    for key in [
        "qa_required",
        "security_required",
        "ux_required",
        "docs_required",
        "research_required",
    ]:
        value = bool(flags.get(key, False)) if isinstance(flags, dict) else False
        lines.append(f"- {key}: {str(value).lower()}")

    declarations = as_dict_list(task.get("declarations"))
    lines.append("")
    lines.append("Declarations (who does what):")
    if declarations:
        for declaration in declarations:
            at = str(declaration.get("at", "")).strip()
            team = str(declaration.get("team", "")).strip()
            role = str(declaration.get("role", "")).strip()
            action = str(declaration.get("action", "")).strip()
            what = str(declaration.get("what", "")).strip()
            controls = declaration.get("controlled_by")
            if isinstance(controls, list) and controls:
                controlled_by = ", ".join(str(v) for v in controls)
            else:
                controlled_by = "(none)"
            lines.append(
                f"- at={at} team={team} role={role} action={action} do={what} controlled_by={controlled_by}"
            )
    else:
        lines.append("- (none)")

    handoffs = as_dict_list(task.get("handoffs"))
    lines.append("")
    lines.append("Handoffs (task passing events):")
    if handoffs:
        for handoff in handoffs:
            at = str(handoff.get("at", "")).strip()
            src = str(handoff.get("from", "")).strip()
            dst = str(handoff.get("to", "")).strip()
            memo = str(handoff.get("memo", "")).strip()
            lines.append(f"- at={at} from={src} to={dst} memo={memo}")
    else:
        lines.append("- (none)")

    notes = str(task.get("notes", "")).strip()
    if notes:
        lines.append("")
        lines.append("Notes:")
        lines.append(notes)

    lines.append("")
    lines.append("Return reviewer and leader-ready output with explicit evidence.")
    return "\n".join(lines).strip()


def parse_orchestrate_args(args: list[str]) -> tuple[str, str, bool, bool, int]:
    task_file = ""
    provider = "codex"
    no_post_validate = False
    verbose = False

    idx = 0
    while idx < len(args):
        token = args[idx]
        if token == "--task-file":
            if idx + 1 >= len(args):
                return "", provider, no_post_validate, verbose, fail(
                    "PATH_LAYOUT_INVALID",
                    "--task-file requires a value.",
                    "Usage: agentteams orchestrate --task-file .takt/tasks/TASK-xxxxx-slug.yaml",
                )
            task_file = args[idx + 1]
            idx += 2
            continue

        if token == "--provider":
            if idx + 1 >= len(args):
                return "", provider, no_post_validate, verbose, fail(
                    "PATH_LAYOUT_INVALID",
                    "--provider requires a value.",
                    "Allowed values: codex | claude | mock",
                )
            provider = args[idx + 1].strip().lower()
            idx += 2
            continue

        if token == "--no-post-validate":
            no_post_validate = True
            idx += 1
            continue

        if token == "--verbose":
            verbose = True
            idx += 1
            continue

        return "", provider, no_post_validate, verbose, fail(
            "PATH_LAYOUT_INVALID",
            f"unknown option for orchestrate: {token}",
            "Usage: agentteams orchestrate --task-file <path> [--provider codex|claude|mock] [--no-post-validate] [--verbose]",
        )

    if not task_file:
        return "", provider, no_post_validate, verbose, fail(
            "PATH_LAYOUT_INVALID",
            "--task-file is required.",
            "Usage: agentteams orchestrate --task-file .takt/tasks/TASK-xxxxx-slug.yaml",
        )

    if provider not in {"codex", "claude", "mock"}:
        return "", provider, no_post_validate, verbose, fail(
            "PATH_LAYOUT_INVALID",
            f"unsupported provider: {provider}",
            "Allowed values: codex | claude | mock",
        )

    return task_file, provider, no_post_validate, verbose, 0


def orchestrate(task_file: str, provider: str, no_post_validate: bool, verbose: bool) -> int:
    repo_root = resolve_repo_root()
    if repo_root is None:
        return fail(
            "AGENT_CONTEXT_MISSING",
            "agentteams orchestrate must run inside a git repository.",
            f"Next: {cli_command('init --here', include_compat=True)}",
        )

    if require_yaml() != 0:
        return 1

    piece_file = repo_root / ".takt" / "pieces" / "agentteams-governance.yaml"
    if not piece_file.exists():
        return fail("TAKT_PIECE_MISSING", f"missing piece: {piece_file.as_posix()}")

    task_path = Path(task_file)
    if not task_path.is_absolute():
        task_path = (repo_root / task_path).resolve()

    if not task_path.exists() or not task_path.is_file():
        return fail("TAKT_TASK_MISSING", f"task file not found: {task_path.as_posix()}")

    canonical_tasks_dir = (repo_root / ".takt" / "tasks").resolve()
    try:
        task_path.relative_to(canonical_tasks_dir)
    except ValueError:
        return fail(
            "TAKT_TASK_SCOPE_INVALID",
            f"task file must be under {canonical_tasks_dir.as_posix()}",
            "Use: agentteams orchestrate --task-file .takt/tasks/TASK-xxxxx-slug.yaml",
        )

    raw = yaml.safe_load(task_path.read_text(encoding="utf-8")) if yaml is not None else None
    if not isinstance(raw, dict):
        return fail("TAKT_TASK_INVALID", f"failed to parse YAML object: {task_path.as_posix()}")

    status = str(raw.get("status", ""))
    if status not in TASK_STATUSES:
        return fail("TAKT_TASK_INVALID", f"invalid status in task file: {status}")

    compiled_prompt = compile_orchestration_prompt(task_path, raw)

    takt_cmd = resolve_takt_command()
    if takt_cmd is None:
        return fail(
            "TAKT_NOT_FOUND",
            "takt command not found.",
            "Install takt and retry: npm install -g takt",
        )

    if provider == "mock":
        info(verbose, "provider=mock: verifying TAKT binary and generating mock evidence")
        code, _ = run_cmd([takt_cmd, "--version"], cwd=repo_root)
        if code != 0:
            return fail("ORCHESTRATE_FAILED", "failed to verify TAKT in mock mode.")

        logs_dir = repo_root / ".takt" / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        evidence = logs_dir / f"mock-orchestrate-{task_path.stem}.log"
        evidence.write_text(
            "mode=mock\n"
            f"task_file={task_path.as_posix()}\n"
            f"provider={provider}\n"
            "result=simulated_success\n",
            encoding="utf-8",
        )
        code = 0
    else:
        cmd = [
            takt_cmd,
            "--pipeline",
            "--piece",
            str(piece_file),
            "--task",
            compiled_prompt,
            "--provider",
            provider,
        ]
        info(verbose, f"running takt command: {' '.join(cmd)}")
        code, _ = run_cmd(cmd, cwd=repo_root, env=os.environ.copy())

    if code != 0:
        return fail("ORCHESTRATE_FAILED", "takt execution failed.")

    if not no_post_validate:
        code = run_python_script(repo_root, "scripts/validate-takt-task.py", ["--file", str(task_path)])
        if code != 0:
            return code
        code = run_python_script(repo_root, "scripts/validate-takt-evidence.py", [])
        if code != 0:
            return code

    print(f"OK [ORCHESTRATE_DONE] task={task_path.as_posix()} provider={provider}")
    return 0


def parse_audit_args(args: list[str]) -> tuple[int, bool, bool, int]:
    min_teams = 3
    strict = False
    verbose = False

    idx = 0
    while idx < len(args):
        token = args[idx]
        if token == "--min-teams":
            if idx + 1 >= len(args):
                return min_teams, strict, verbose, fail(
                    "PATH_LAYOUT_INVALID",
                    "--min-teams requires a numeric value.",
                    "Usage: agentteams audit [--min-teams <n>] [--strict] [--verbose]",
                )
            try:
                min_teams = int(args[idx + 1])
                if min_teams <= 0:
                    raise ValueError
            except ValueError:
                return min_teams, strict, verbose, fail(
                    "PATH_LAYOUT_INVALID",
                    f"invalid --min-teams value: {args[idx + 1]}",
                    "--min-teams must be an integer >= 1",
                )
            idx += 2
            continue
        if token == "--strict":
            strict = True
            idx += 1
            continue
        if token == "--verbose":
            verbose = True
            idx += 1
            continue

        return min_teams, strict, verbose, fail(
            "PATH_LAYOUT_INVALID",
            f"unknown option for audit: {token}",
            "Usage: agentteams audit [--min-teams <n>] [--strict] [--verbose]",
        )

    return min_teams, strict, verbose, 0


def audit(min_teams: int, strict: bool, verbose: bool) -> int:
    repo_root = resolve_repo_root()
    if repo_root is None:
        return fail(
            "AGENT_CONTEXT_MISSING",
            "agentteams audit must run inside a git repository.",
            f"Next: {cli_command('init --here', include_compat=True)}",
        )

    script = repo_root / "scripts" / "audit-takt-governance.py"
    if not script.exists():
        return fail("PATH_LAYOUT_INVALID", f"missing script: {script.as_posix()}")

    cmd = [sys.executable, str(script), "--min-teams", str(min_teams)]
    if strict:
        cmd.append("--strict")
    if verbose:
        cmd.append("--verbose")

    code, _ = run_cmd(cmd, cwd=repo_root)
    return code


def init_command(template_root: Path, args: list[str]) -> int:
    repo_url, use_here, workspace, verbose, parse_code = parse_init_args(args)
    if parse_code != 0:
        return parse_code

    if use_here:
        return init_here(template_root, verbose)

    if not repo_url:
        auto_root = resolve_repo_root()
        if auto_root is not None:
            info(verbose, "no URL provided; running --here mode in current repository")
            return init_here(template_root, verbose)
        return fail(
            "PATH_LAYOUT_INVALID",
            "repository URL is required outside git repositories.",
            "Usage: agentteams init <git-url> or agentteams init --here",
        )

    return init_with_clone(template_root, repo_url, workspace, verbose)


def main(argv: list[str]) -> int:
    args = [arg for arg in argv if arg is not None]
    template_root = Path(__file__).resolve().parent.parent

    if not args:
        usage()
        return 1

    command = args[0]
    command_args = args[1:]

    if command in REMOVED_COMMANDS:
        return fail(
            "LEGACY_COMMAND_REMOVED",
            f"`{PRIMARY_CLI} {command}` は v4 で廃止済みです。",
            "利用可能: agentteams init | doctor | orchestrate | audit",
        )

    if command not in {"init", "doctor", "orchestrate", "audit"}:
        usage()
        return fail(
            "PATH_LAYOUT_INVALID",
            f"unknown subcommand: {command}",
            "Usage: agentteams init|doctor|orchestrate|audit",
        )

    code = ensure_git_available()
    if code != 0:
        return code

    if command == "init":
        return init_command(template_root, command_args)

    if command == "doctor":
        verbose = False
        for token in command_args:
            if token == "--verbose":
                verbose = True
                continue
            return fail(
                "PATH_LAYOUT_INVALID",
                f"unknown option for doctor: {token}",
                "Usage: agentteams doctor [--verbose]",
            )
        return doctor(verbose)

    if command == "orchestrate":
        task_file, provider, no_post_validate, verbose, parse_code = parse_orchestrate_args(command_args)
        if parse_code != 0:
            return parse_code
        return orchestrate(task_file, provider, no_post_validate, verbose)

    min_teams, strict, verbose, parse_code = parse_audit_args(command_args)
    if parse_code != 0:
        return parse_code
    return audit(min_teams, strict, verbose)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
