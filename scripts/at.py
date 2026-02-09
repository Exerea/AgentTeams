#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


MANAGED_MARKER = "<!-- AGENTTEAMS_MANAGED:ENTRY v1 -->"
CHAT_LOG_RELATIVE_PATH = Path("logs") / "e2e-ai-log.md"
GLOBAL_KICKOFF = "殿のご命令と各AGENTS.mdに忠実に従う家臣たちが集まりました。──家臣たちが動きます！"

DEFAULT_INCIDENT_SOURCE = "https://github.com/Exerea/AgentTeams.git"
INCIDENT_CACHE_REGISTRY = Path(".codex") / "cache" / "incident-registry.yaml"
INCIDENT_CACHE_META = Path(".codex") / "cache" / "incident-registry.meta.yaml"
INCIDENT_CACHE_INCIDENTS_DIR = Path(".codex") / "cache" / "incidents"
INCIDENT_CANDIDATE_DIR = Path(".codex") / "cache" / "incident-candidates"
INCIDENT_CANDIDATE_INDEX = INCIDENT_CANDIDATE_DIR / "_index.yaml"
DEFAULT_TAKT_PIECE = Path(".takt") / "pieces" / "agentteams-governance.yaml"

TASK_FILE_NAME_PATTERN = re.compile(r"^TASK-\d{5}-[a-z0-9]+(?:-[a-z0-9]+)*\.yaml$")
WARNING_CODE_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]+$")
ALLOWED_WARNING_CODES = {
    "PROTO_SCHEMA_MISMATCH",
    "PROTO_FIELD_CASE_MISMATCH",
    "PROTO_REQUIRED_FIELD_MISSING",
    "PROTO_UNEXPECTED_FIELD",
    "PROTO_HANDOFF_CONTEXT_MISSING",
}

PRIMARY_CLI = "agentteams"
WINDOWS_COMPAT_CLI = r".\at.cmd"
UNIX_COMPAT_CLI = "./at"


def cli_command(command: str, include_compat: bool = False) -> str:
    normalized = command.strip()
    primary = f"{PRIMARY_CLI} {normalized}".strip()
    if not include_compat:
        return primary

    compat_cli = WINDOWS_COMPAT_CLI if os.name == "nt" else UNIX_COMPAT_CLI
    compat = f"{compat_cli} {normalized}".strip()
    return f"{primary} (compat: {compat})"


def usage() -> None:
    print("Usage:")
    print(
        "  agentteams init [<git-url>] [-w|--workspace <path>] "
        "[--agents-policy coexist|replace|keep] [--verbose]"
    )
    print("  agentteams init --here [--agents-policy coexist|replace|keep] [--verbose]")
    print("  agentteams doctor [--verbose]")
    print(
        "  agentteams sync [--source <git-url>] [--ref <tag|branch>] [--offline-ok] [--verbose]"
    )
    print(
        "  agentteams report-incident --task-file <path> --code <warning_code> "
        "--summary <text> --project <name> [--verbose]"
    )
    print(
        "  agentteams guard-chat --event <task_start|role_switch|gate> --team <team> "
        "--role <role> --task <task_id|N/A> --task-title <title> --message-file <path> "
        "--task-file <TASK-*.yaml> [--log <path>] [--emit-fixed-file <path>] [--verbose]"
    )
    print(
        "  agentteams orchestrate --task-file <TASK-*.yaml> "
        "[--piece <path>] [--provider <claude|codex|mock>] [--model <name>] "
        "[--with-git] [--no-post-validate] [--strict-operation-evidence] "
        "[--min-teams <n>] [--min-roles <n>] [--verbose]"
    )
    print("Compatibility aliases:")
    print(
        "  at init [<git-url>] [-w|--workspace <path>] "
        "[--agents-policy coexist|replace|keep] [--verbose]"
    )
    print("  at init --here [--agents-policy coexist|replace|keep] [--verbose]")
    print(
        "  at guard-chat --event <task_start|role_switch|gate> --team <team> "
        "--role <role> --task <task_id|N/A> --task-title <title> --message-file <path> "
        "--task-file <TASK-*.yaml> [--log <path>] [--emit-fixed-file <path>] [--verbose]"
    )
    print(
        "  at orchestrate --task-file <TASK-*.yaml> "
        "[--piece <path>] [--provider <claude|codex|mock>] [--model <name>] "
        "[--with-git] [--no-post-validate] [--strict-operation-evidence] "
        "[--min-teams <n>] [--min-roles <n>] [--verbose]"
    )
    if os.name == "nt":
        print("  .\\at.cmd <subcommand> ...")


def fail(code: str, message: str, next_command: str | None = None) -> int:
    print(f"ERROR [{code}] {message}")
    if next_command:
        print(f"Next: {next_command}")
    return 1


def warn(code: str, message: str, next_command: str | None = None) -> None:
    print(f"WARN [{code}] {message}")
    if next_command:
        print(f"Next: {next_command}")


def is_verbose_enabled(verbose: bool, message: str) -> None:
    if verbose:
        print(f"[at] {message}")


def print_safe(message: str) -> None:
    try:
        print(message)
    except UnicodeEncodeError:
        encoding = sys.stdout.encoding or "utf-8"
        safe = message.encode(encoding, errors="replace").decode(encoding, errors="replace")
        print(safe)


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sanitize_single_line(value: str, max_len: int = 240) -> str:
    text = (value or "").strip().replace("\r", " ").replace("\n", " ")
    text = text.replace("|", "/").replace(":", "：")
    text = re.sub(r"\s+", " ", text)
    if len(text) > max_len:
        text = text[: max_len - 3].rstrip() + "..."
    return text


def slugify(value: str, fallback: str = "incident") -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or fallback


def normalize_scalar(value: str) -> str:
    v = (value or "").strip()
    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
        v = v[1:-1]
    return v.strip()


def parse_int(value: str, fallback: int = 0) -> int:
    try:
        return int(normalize_scalar(value))
    except (TypeError, ValueError):
        return fallback


def parse_bool(value: str, fallback: bool = True) -> bool:
    normalized = normalize_scalar(value).lower()
    if normalized in {"true", "yes", "1"}:
        return True
    if normalized in {"false", "no", "0"}:
        return False
    return fallback


def ordered_unique(values: list[str]) -> list[str]:
    out: list[str] = []
    for value in values:
        cleaned = normalize_scalar(value)
        if cleaned and cleaned not in out:
            out.append(cleaned)
    return out


def read_text_or_empty(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").lstrip("\ufeff")


def write_if_changed(path: Path, content: str) -> bool:
    current = read_text_or_empty(path)
    if current == content:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(content)
    return True


def repo_name_from_url(repo_url: str) -> str:
    trimmed = repo_url.strip().rstrip("/\\")
    if not trimmed:
        return ""
    leaf = trimmed.replace("\\", "/").split("/")[-1]
    if leaf.endswith(".git"):
        leaf = leaf[:-4]
    return leaf.strip()


def managed_agents_content() -> str:
    lines = [
        "# AGENTS.md (AgentTeams Entry + Minimum Runtime Contract)",
        "",
        MANAGED_MARKER,
        "This file is the AgentTeams entrypoint.",
        "",
        "## Canonical Rules",
        "- Source of truth: `.codex/AGENTS.md`",
        "- Optional local override backup: `.codex/AGENTS.local.md`",
        "- Read canonical rules first on task start.",
        "- PowerShell UTF-8 read example: `Get-Content .codex/AGENTS.md -Encoding utf8`",
        "",
        "## Task Start Contract (Chat)",
        "- Task開始時は `固定開始宣言 -> 【稼働口上】 -> DECLARATION` の順を必須化",
        "- 固定開始宣言: `殿のご命令と各AGENTS.mdに忠実に従う家臣たちが集まりました。──家臣たちが動きます！`",
        "- 口上テンプレ: `【稼働口上】殿、ただいま <家老|足軽> の <team>/<role> が「<task_title>」を務めます。<要旨>`",
        "- 機械可読: `DECLARATION team=<team> role=<role> task=<task_id|N/A> action=<action>`",
        "- 通常送信は `agentteams guard-chat` 経由で事前検証してからログ追記する",
        "",
        "## Coordinator Intake / Decomposition",
        "- coordinator accepts requests by default and decomposes by `Goal/Constraints/Acceptance`.",
        "- Work should proceed through `TASK-*.yaml` with explicit `task_file_path` handoff.",
    ]
    return "\n".join(lines)


def chat_log_template_content() -> str:
    lines = [
        "# E2E AI Log (v2.8)",
        "",
        "- declaration_protocol: Task開始時は「固定開始宣言 -> 稼働口上 -> DECLARATION」の3行を必須化",
        "",
        "## Entries",
        f"- 2026-01-01T00:00:00Z {GLOBAL_KICKOFF}",
        "- 2026-01-01T00:00:01Z 【稼働口上】殿、ただいま 家老 の coordinator/coordinator が「導入確認」を務めます。導入確認を開始します。",
        "- 2026-01-01T00:00:02Z DECLARATION team=coordinator role=coordinator task=N/A action=bootstrap_verification",
    ]
    return "\n".join(lines) + "\n"


def ensure_chat_log_template(target_root: Path, verbose: bool) -> None:
    log_path = target_root / CHAT_LOG_RELATIVE_PATH
    if log_path.exists():
        is_verbose_enabled(verbose, f"chat log already exists: {log_path.as_posix()}")
        return

    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(chat_log_template_content())
    is_verbose_enabled(verbose, f"created chat log template: {log_path.as_posix()}")


def backup_agents_to_local_if_needed(target_agents: Path, local_agents: Path) -> None:
    if not target_agents.exists():
        return
    target_content = read_text_or_empty(target_agents)
    if MANAGED_MARKER in target_content:
        return
    write_if_changed(local_agents, target_content)


def apply_agents_policy(target_root: Path, policy: str, verbose: bool) -> int:
    codex_agents = target_root / ".codex" / "AGENTS.md"
    if not codex_agents.exists():
        return fail(
            "BOOTSTRAP_FAILED",
            f"missing required file: {codex_agents.as_posix()}",
            f"Retry: {cli_command('init --here', include_compat=True)}",
        )

    target_agents = target_root / "AGENTS.md"
    local_agents = target_root / ".codex" / "AGENTS.local.md"
    managed_content = managed_agents_content()

    if policy == "keep":
        is_verbose_enabled(verbose, "agents-policy=keep: preserving existing AGENTS.md.")
        return 0

    if policy == "replace":
        backup_agents_to_local_if_needed(target_agents, local_agents)
        write_if_changed(target_agents, managed_content)
        is_verbose_enabled(verbose, "agents-policy=replace: AGENTS.md replaced with managed entry.")
        return 0

    if policy == "coexist":
        backup_agents_to_local_if_needed(target_agents, local_agents)
        write_if_changed(target_agents, managed_content)
        is_verbose_enabled(verbose, "agents-policy=coexist: AGENTS.md wrapped and local rules preserved.")
        return 0

    return fail(
        "AGENTS_CONFLICT",
        f"unsupported agents-policy: {policy}",
        "Allowed values: coexist | replace | keep",
    )


def run_cmd(cmd: list[str], cwd: Path | None = None, print_output: bool = True) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
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


def normalized_path(path: Path) -> str:
    resolved = path.resolve()
    text = resolved.as_posix()
    return text.lower() if os.name == "nt" else text


def paths_equal(left: Path, right: Path) -> bool:
    try:
        return left.resolve().samefile(right.resolve())
    except (FileNotFoundError, OSError):
        return normalized_path(left) == normalized_path(right)


def ensure_git_available() -> int:
    if shutil.which("git") is None:
        return fail(
            "PATH_LAYOUT_INVALID",
            "git command not found.",
            f"Install git, then retry: {cli_command('init <git-url>', include_compat=True)}",
        )
    return 0


def resolve_takt_command() -> str:
    for candidate in ("takt", "takt.cmd", "takt.exe"):
        path = shutil.which(candidate)
        if path:
            return path
    return ""


def resolve_repo_url_interactive(repo_url: str) -> tuple[str, int]:
    if repo_url:
        return repo_url, 0

    entered = ""
    if sys.stdin.isatty():
        try:
            entered = input("Repository URL: ").strip()
        except EOFError:
            entered = ""
    else:
        # Allow non-interactive callers to provide URL via stdin pipe/redirection.
        entered = sys.stdin.readline().strip()

    if not entered:
        return "", fail(
            "PATH_LAYOUT_INVALID",
            "repository url is required.",
            "Usage: agentteams init <git-url> | agentteams init --here",
        )
    return entered, 0


def invoke_bootstrap(template_root: Path, target_root: Path, verbose: bool = False) -> int:
    if paths_equal(template_root, target_root):
        is_verbose_enabled(
            verbose,
            "target root matches AgentTeams template root; skipping bootstrap copy step.",
        )
        return 0

    ps_bootstrap = template_root / "scripts" / "bootstrap-agent-teams.ps1"
    sh_bootstrap = template_root / "scripts" / "bootstrap-agent-teams.sh"

    if os.name == "nt":
        if not ps_bootstrap.exists():
            return fail(
                "BOOTSTRAP_FAILED",
                f"missing bootstrap script: {ps_bootstrap.as_posix()}",
                "Verify your AgentTeams checkout path.",
            )
        code, _ = run_cmd(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(ps_bootstrap),
                "--target",
                str(target_root),
            ]
        )
        if code != 0:
            return fail(
                "BOOTSTRAP_FAILED",
                f"bootstrap failed for target: {target_root.as_posix()}",
                f"Retry: {cli_command('init --here --agents-policy coexist', include_compat=True)}",
            )
        return 0

    if not sh_bootstrap.exists():
        return fail(
            "BOOTSTRAP_FAILED",
            f"missing bootstrap script: {sh_bootstrap.as_posix()}",
            "Verify your AgentTeams checkout path.",
        )
    code, _ = run_cmd(["bash", str(sh_bootstrap), "--target", str(target_root)])
    if code != 0:
        return fail(
            "BOOTSTRAP_FAILED",
            f"bootstrap failed for target: {target_root.as_posix()}",
            f"Retry: {cli_command('init --here --agents-policy coexist', include_compat=True)}",
        )
    return 0


def resolve_target_root_here() -> Path | None:
    code, output = run_cmd(["git", "rev-parse", "--show-toplevel"], print_output=False)
    if code != 0 or not output:
        return None
    return Path(output.splitlines()[-1]).resolve()


def doctor(verbose: bool) -> int:
    target_root = resolve_target_root_here()
    if target_root is None:
        print("ERROR [AGENT_CONTEXT_MISSING] current directory is not inside a git repository.")
        print(f"Next: {cli_command('init', include_compat=True)}")
        return 1

    print(f"OK [AGENT_CONTEXT_OK] git repository detected: {target_root.as_posix()}")

    codex_agents = target_root / ".codex" / "AGENTS.md"
    target_agents = target_root / "AGENTS.md"
    local_agents = target_root / ".codex" / "AGENTS.local.md"

    has_error = False
    has_warning = False

    if not codex_agents.exists():
        has_error = True
        print(f"ERROR [CODEX_RULES_MISSING] missing file: {codex_agents.as_posix()}")
    else:
        print(f"OK [CODEX_RULES_OK] found: {codex_agents.as_posix()}")

    if not target_agents.exists():
        has_error = True
        print(f"ERROR [AGENTS_WRAPPER_MISSING] missing file: {target_agents.as_posix()}")
    else:
        target_content = read_text_or_empty(target_agents)
        if MANAGED_MARKER in target_content:
            print(f"OK [AGENTS_WRAPPER_OK] managed marker found in: {target_agents.as_posix()}")
        else:
            has_warning = True
            print(
                f"WARN [AGENTS_WRAPPER_MISSING] managed marker not found in: {target_agents.as_posix()}"
            )

    if local_agents.exists():
        print(f"OK [AGENTS_LOCAL_PRESENT] local rules file present: {local_agents.as_posix()}")
    else:
        is_verbose_enabled(verbose, f"no local rules backup file: {local_agents.as_posix()}")

    takt_piece = target_root / DEFAULT_TAKT_PIECE
    if takt_piece.exists():
        print(f"OK [TAKT_PIECE_OK] found: {takt_piece.as_posix()}")
    else:
        has_warning = True
        print(
            f"WARN [TAKT_PIECE_MISSING] missing AgentTeams piece: {takt_piece.as_posix()}"
        )

    takt_command = resolve_takt_command()
    if takt_command:
        print(f"OK [TAKT_COMMAND_OK] takt command detected: {takt_command}")
    else:
        has_warning = True
        print(
            "WARN [TAKT_COMMAND_MISSING] takt command not found. Install with: npm install -g takt"
        )

    if has_error or has_warning:
        print(f"Next: {cli_command('init --here', include_compat=True)}")
        return 1

    print(f"Next: {cli_command('init --here', include_compat=True)}")
    return 0


def init_with_clone(
    template_root: Path,
    repo_url: str,
    workspace_path: str,
    policy: str,
    verbose: bool,
) -> int:
    workspace_root = Path(workspace_path).expanduser().resolve()
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

    is_verbose_enabled(verbose, f"cloning {repo_url} -> {target_root.as_posix()}")
    code, _ = run_cmd(["git", "clone", repo_url, str(target_root)])
    if code != 0:
        retry_cmd = f'init {repo_url} -w "{workspace_root.as_posix()}"'
        return fail(
            "GIT_CLONE_FAILED",
            f"git clone failed: {repo_url}",
            f"Check URL and retry: {cli_command(retry_cmd, include_compat=True)}",
        )

    code = invoke_bootstrap(template_root, target_root, verbose)
    if code != 0:
        return code

    code = apply_agents_policy(target_root, policy, verbose)
    if code != 0:
        return code

    ensure_chat_log_template(target_root, verbose)
    print(f"{PRIMARY_CLI} init completed: {target_root.as_posix()}")
    return 0


def init_here(template_root: Path, policy: str, verbose: bool) -> int:
    target_root = resolve_target_root_here()
    if target_root is None:
        return fail(
            "PATH_LAYOUT_INVALID",
            "--here can only be used inside a git repository.",
            f"For new setup: {cli_command('init <git-url>', include_compat=True)}",
        )

    is_verbose_enabled(verbose, f"target root: {target_root.as_posix()}")
    effective_policy = policy
    if paths_equal(template_root, target_root):
        if policy != "keep":
            is_verbose_enabled(
                verbose,
                "target root is AgentTeams template root; forcing agents-policy=keep to avoid mutating template files.",
            )
        effective_policy = "keep"

    code = invoke_bootstrap(template_root, target_root, verbose)
    if code != 0:
        return code

    code = apply_agents_policy(target_root, effective_policy, verbose)
    if code != 0:
        return code

    ensure_chat_log_template(target_root, verbose)
    print(f"{PRIMARY_CLI} init completed: {target_root.as_posix()}")
    return 0


def parse_init_args(args: list[str]) -> tuple[str, bool, str, str, bool, int]:
    repo_url = ""
    use_here = False
    workspace = str(Path.cwd())
    policy = "coexist"
    verbose = False

    idx = 0
    while idx < len(args):
        token = args[idx]

        if token == "--":
            idx += 1
            continue
        if token == "--here":
            use_here = True
            idx += 1
            continue
        if token in ("--workspace", "-w"):
            if idx + 1 >= len(args):
                return "", False, "", "", False, fail(
                    "PATH_LAYOUT_INVALID",
                    f"{token} requires a path value.",
                    "Usage: agentteams init <git-url> -w <path>",
                )
            workspace = args[idx + 1]
            idx += 2
            continue
        if token == "--agents-policy":
            if idx + 1 >= len(args):
                return "", False, "", "", False, fail(
                    "AGENTS_CONFLICT",
                    "--agents-policy requires a value.",
                    "Allowed values: coexist | replace | keep",
                )
            policy = args[idx + 1]
            idx += 2
            continue
        if token == "--verbose":
            verbose = True
            idx += 1
            continue
        if token.startswith("-"):
            return "", False, "", "", False, fail(
                "PATH_LAYOUT_INVALID",
                f"unknown option: {token}",
                "Usage: agentteams init <git-url> | agentteams init --here",
            )
        if repo_url:
            return "", False, "", "", False, fail(
                "PATH_LAYOUT_INVALID",
                f"multiple repository urls provided: {repo_url}, {token}",
                "Usage: agentteams init <git-url>",
            )
        repo_url = token
        idx += 1

    if policy not in {"coexist", "replace", "keep"}:
        return "", False, "", "", False, fail(
            "AGENTS_CONFLICT",
            f"invalid --agents-policy: {policy}",
            "Allowed values: coexist | replace | keep",
        )

    if use_here and repo_url:
        return "", False, "", "", False, fail(
            "PATH_LAYOUT_INVALID",
            "--here and <git-url> cannot be used together.",
            "New setup: agentteams init <git-url> / Existing clone: agentteams init --here",
        )

    if use_here and workspace != str(Path.cwd()):
        return "", False, "", "", False, fail(
            "PATH_LAYOUT_INVALID",
            "--workspace cannot be used with --here.",
            f"For existing clone: {cli_command('init --here', include_compat=True)}",
        )

    return repo_url, use_here, workspace, policy, verbose, 0


def parse_sync_args(args: list[str]) -> tuple[str, str, bool, bool, int]:
    source = DEFAULT_INCIDENT_SOURCE
    ref = "main"
    offline_ok = False
    verbose = False

    idx = 0
    while idx < len(args):
        token = args[idx]
        if token == "--source":
            if idx + 1 >= len(args):
                return "", "", False, False, fail(
                    "PATH_LAYOUT_INVALID",
                    "--source requires a value.",
                    "Usage: agentteams sync --source <git-url> --ref <branch>",
                )
            source = args[idx + 1]
            idx += 2
            continue
        if token == "--ref":
            if idx + 1 >= len(args):
                return "", "", False, False, fail(
                    "PATH_LAYOUT_INVALID",
                    "--ref requires a value.",
                    "Usage: agentteams sync --ref <tag|branch>",
                )
            ref = args[idx + 1]
            idx += 2
            continue
        if token == "--offline-ok":
            offline_ok = True
            idx += 1
            continue
        if token == "--verbose":
            verbose = True
            idx += 1
            continue
        return "", "", False, False, fail(
            "PATH_LAYOUT_INVALID",
            f"unknown option for sync: {token}",
            "Usage: agentteams sync [--source <git-url>] [--ref <tag|branch>] [--offline-ok] [--verbose]",
        )

    if not source.strip():
        return "", "", False, False, fail(
            "PATH_LAYOUT_INVALID",
            "source must not be empty.",
            "Usage: agentteams sync --source <git-url>",
        )
    if not ref.strip():
        return "", "", False, False, fail(
            "PATH_LAYOUT_INVALID",
            "ref must not be empty.",
            "Usage: agentteams sync --ref <tag|branch>",
        )

    return source.strip(), ref.strip(), offline_ok, verbose, 0


def parse_report_incident_args(args: list[str]) -> tuple[str, str, str, str, bool, int]:
    task_file = ""
    warning_code = ""
    summary = ""
    project = ""
    verbose = False

    idx = 0
    while idx < len(args):
        token = args[idx]
        if token == "--task-file":
            if idx + 1 >= len(args):
                return "", "", "", "", False, fail(
                    "PATH_LAYOUT_INVALID",
                    "--task-file requires a value.",
                    "Usage: agentteams report-incident --task-file <path> --code <warning_code> --summary <text> --project <name>",
                )
            task_file = args[idx + 1]
            idx += 2
            continue
        if token == "--code":
            if idx + 1 >= len(args):
                return "", "", "", "", False, fail(
                    "PATH_LAYOUT_INVALID",
                    "--code requires a value.",
                    "Usage: agentteams report-incident --code <warning_code>",
                )
            warning_code = args[idx + 1]
            idx += 2
            continue
        if token == "--summary":
            if idx + 1 >= len(args):
                return "", "", "", "", False, fail(
                    "PATH_LAYOUT_INVALID",
                    "--summary requires a value.",
                    "Usage: agentteams report-incident --summary <text>",
                )
            summary = args[idx + 1]
            idx += 2
            continue
        if token == "--project":
            if idx + 1 >= len(args):
                return "", "", "", "", False, fail(
                    "PATH_LAYOUT_INVALID",
                    "--project requires a value.",
                    "Usage: agentteams report-incident --project <name>",
                )
            project = args[idx + 1]
            idx += 2
            continue
        if token == "--verbose":
            verbose = True
            idx += 1
            continue
        return "", "", "", "", False, fail(
            "PATH_LAYOUT_INVALID",
            f"unknown option for report-incident: {token}",
            "Usage: agentteams report-incident --task-file <path> --code <warning_code> --summary <text> --project <name> [--verbose]",
        )

    if not task_file:
        return "", "", "", "", False, fail(
            "PATH_LAYOUT_INVALID",
            "--task-file is required.",
            "Usage: agentteams report-incident --task-file <path> --code <warning_code> --summary <text> --project <name>",
        )
    if not warning_code:
        return "", "", "", "", False, fail(
            "PATH_LAYOUT_INVALID",
            "--code is required.",
            "Usage: agentteams report-incident --task-file <path> --code <warning_code> --summary <text> --project <name>",
        )
    if not summary:
        return "", "", "", "", False, fail(
            "PATH_LAYOUT_INVALID",
            "--summary is required.",
            "Usage: agentteams report-incident --task-file <path> --code <warning_code> --summary <text> --project <name>",
        )
    if not project:
        return "", "", "", "", False, fail(
            "PATH_LAYOUT_INVALID",
            "--project is required.",
            "Usage: agentteams report-incident --task-file <path> --code <warning_code> --summary <text> --project <name>",
        )

    return task_file, warning_code, summary, project, verbose, 0


def extract_task_metadata(task_path: Path) -> tuple[str, str]:
    task_id = "N/A"
    title = task_path.name
    for line in read_text_or_empty(task_path).splitlines():
        m_id = re.match(r"^id\s*:\s*(.+)$", line)
        if m_id:
            task_id = normalize_scalar(m_id.group(1)) or task_id
            continue
        m_title = re.match(r"^title\s*:\s*(.+)$", line)
        if m_title:
            title = normalize_scalar(m_title.group(1)) or title
    return task_id, title


def build_orchestrate_task_prompt(task_rel: str, task_id: str, title: str) -> str:
    safe_task_rel = sanitize_single_line(task_rel, max_len=280)
    safe_task_id = sanitize_single_line(task_id, max_len=80)
    safe_title = sanitize_single_line(title, max_len=200)
    lines = [
        "AgentTeams TAKT orchestration task.",
        f"Target task file: {safe_task_rel}",
        f"Task ID: {safe_task_id}",
        f"Task title: {safe_title}",
        "",
        "Mission:",
        "- Execute the task using AgentTeams governance rules with strict role distribution.",
        "- Continue review/fix loops until specialist reviewers and leader supervisor approve.",
        "",
        "Required reads (before decision):",
        "- .codex/AGENTS.md",
        "- .codex/coordinator.md",
        "- docs/guides/communication-protocol.md",
        "- docs/guides/request-routing-scenarios.md",
        "",
        "Execution requirements:",
        "- Decompose into Goal/Constraints/Acceptance and record in task notes.",
        "- Maintain DECLARATION format in handoff memo first line.",
        "- Respect local_flags and warnings for gate decisions.",
        "- For blocked or unresolved warnings, add IMPROVEMENT_PROPOSAL evidence.",
        "- Keep edits scoped to this task and required implementation/doc files.",
        "",
        "Validation requirements:",
        "- Ensure validate-task-state passes for the target task.",
        "- Keep reviewer evidence explicit (Security/UX/Protocol/Docs/QA/Role Gap).",
        "",
        "Output:",
        "- Complete with all specialist approvals and final leader approval, or abort with concrete blockers.",
    ]
    return "\n".join(lines)


def parse_orchestrate_args(
    args: list[str],
) -> tuple[str, str, str, str, bool, bool, bool, int, int, bool, int]:
    task_file = ""
    piece = DEFAULT_TAKT_PIECE.as_posix()
    provider = ""
    model = ""
    skip_git = True
    post_validate = True
    strict_operation_evidence = False
    min_teams = 3
    min_roles = 5
    verbose = False

    idx = 0
    while idx < len(args):
        token = args[idx]
        if token == "--task-file":
            if idx + 1 >= len(args):
                return "", "", "", "", True, True, False, 3, 5, False, fail(
                    "PATH_LAYOUT_INVALID",
                    "--task-file requires a value.",
                    "Usage: agentteams orchestrate --task-file <TASK-*.yaml>",
                )
            task_file = args[idx + 1]
            idx += 2
            continue
        if token == "--piece":
            if idx + 1 >= len(args):
                return "", "", "", "", True, True, False, 3, 5, False, fail(
                    "PATH_LAYOUT_INVALID",
                    "--piece requires a value.",
                    "Usage: agentteams orchestrate --piece <path>",
                )
            piece = args[idx + 1]
            idx += 2
            continue
        if token == "--provider":
            if idx + 1 >= len(args):
                return "", "", "", "", True, True, False, 3, 5, False, fail(
                    "PATH_LAYOUT_INVALID",
                    "--provider requires a value.",
                    "Usage: agentteams orchestrate --provider <claude|codex|mock>",
                )
            provider = args[idx + 1].strip()
            idx += 2
            continue
        if token == "--model":
            if idx + 1 >= len(args):
                return "", "", "", "", True, True, False, 3, 5, False, fail(
                    "PATH_LAYOUT_INVALID",
                    "--model requires a value.",
                    "Usage: agentteams orchestrate --model <name>",
                )
            model = args[idx + 1].strip()
            idx += 2
            continue
        if token == "--with-git":
            skip_git = False
            idx += 1
            continue
        if token == "--skip-git":
            skip_git = True
            idx += 1
            continue
        if token == "--no-post-validate":
            post_validate = False
            idx += 1
            continue
        if token == "--strict-operation-evidence":
            strict_operation_evidence = True
            idx += 1
            continue
        if token == "--min-teams":
            if idx + 1 >= len(args):
                return "", "", "", "", True, True, False, 3, 5, False, fail(
                    "PATH_LAYOUT_INVALID",
                    "--min-teams requires a value.",
                    "Usage: agentteams orchestrate --min-teams <n>",
                )
            min_teams = parse_int(args[idx + 1], fallback=-1)
            idx += 2
            continue
        if token == "--min-roles":
            if idx + 1 >= len(args):
                return "", "", "", "", True, True, False, 3, 5, False, fail(
                    "PATH_LAYOUT_INVALID",
                    "--min-roles requires a value.",
                    "Usage: agentteams orchestrate --min-roles <n>",
                )
            min_roles = parse_int(args[idx + 1], fallback=-1)
            idx += 2
            continue
        if token == "--verbose":
            verbose = True
            idx += 1
            continue
        return "", "", "", "", True, True, False, 3, 5, False, fail(
            "PATH_LAYOUT_INVALID",
            f"unknown option for orchestrate: {token}",
            "Usage: agentteams orchestrate --task-file <TASK-*.yaml> [--piece <path>] [--provider <claude|codex|mock>] [--model <name>] [--with-git] [--no-post-validate] [--strict-operation-evidence] [--min-teams <n>] [--min-roles <n>] [--verbose]",
        )

    if not task_file:
        return "", "", "", "", True, True, False, 3, 5, False, fail(
            "PATH_LAYOUT_INVALID",
            "--task-file is required.",
            "Usage: agentteams orchestrate --task-file <TASK-*.yaml>",
        )
    if min_teams < 1:
        return "", "", "", "", True, True, False, 3, 5, False, fail(
            "PATH_LAYOUT_INVALID",
            "--min-teams must be >= 1.",
            "Usage: agentteams orchestrate --min-teams <n>",
        )
    if min_roles < 1:
        return "", "", "", "", True, True, False, 3, 5, False, fail(
            "PATH_LAYOUT_INVALID",
            "--min-roles must be >= 1.",
            "Usage: agentteams orchestrate --min-roles <n>",
        )

    return (
        task_file,
        piece,
        provider,
        model,
        skip_git,
        post_validate,
        strict_operation_evidence,
        min_teams,
        min_roles,
        verbose,
        0,
    )


def run_task_state_validation(
    template_root: Path,
    target_root: Path,
    task_path: Path,
    verbose: bool,
) -> int:
    if os.name == "nt":
        validator = template_root / "scripts" / "validate-task-state.ps1"
        if not validator.exists():
            return fail("PATH_LAYOUT_INVALID", f"missing validator script: {validator.as_posix()}")
        code, _ = run_cmd(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(validator),
                "-Path",
                str(task_path),
            ],
            cwd=target_root,
        )
        if code != 0:
            return fail(
                "TAKT_POST_VALIDATE_FAILED",
                f"validate-task-state failed: {task_path.as_posix()}",
                "Fix task file and retry orchestrate.",
            )
        return 0

    validator = template_root / "scripts" / "validate-task-state.sh"
    if not validator.exists():
        return fail("PATH_LAYOUT_INVALID", f"missing validator script: {validator.as_posix()}")
    code, _ = run_cmd(["bash", str(validator), str(task_path)], cwd=target_root)
    if code != 0:
        return fail(
            "TAKT_POST_VALIDATE_FAILED",
            f"validate-task-state failed: {task_path.as_posix()}",
            "Fix task file and retry orchestrate.",
        )
    is_verbose_enabled(verbose, "validate-task-state passed")
    return 0


def run_operation_evidence_validation(
    template_root: Path,
    target_root: Path,
    task_rel: str,
    min_teams: int,
    min_roles: int,
    strict: bool,
) -> int:
    validator = template_root / "scripts" / "validate-operation-evidence.py"
    if not validator.exists():
        if strict:
            return fail("PATH_LAYOUT_INVALID", f"missing validator script: {validator.as_posix()}")
        warn("PATH_LAYOUT_INVALID", f"operation validator is missing: {validator.as_posix()}")
        return 0

    code, _ = run_cmd(
        [
            sys.executable,
            str(validator),
            "--task-file",
            task_rel,
            "--log",
            CHAT_LOG_RELATIVE_PATH.as_posix(),
            "--min-teams",
            str(min_teams),
            "--min-roles",
            str(min_roles),
        ],
        cwd=target_root,
    )
    if code == 0:
        return 0

    message = (
        "validate-operation-evidence failed. "
        "This usually means role distribution or read/declaration evidence is insufficient."
    )
    if strict:
        return fail("TAKT_OPERATION_EVIDENCE_FAILED", message, "Fix evidence and retry orchestrate.")
    warn("TAKT_OPERATION_EVIDENCE_WARN", message, "Retry with --strict-operation-evidence to hard-fail.")
    return 0


def orchestrate_task(
    template_root: Path,
    task_file: str,
    piece: str,
    provider: str,
    model: str,
    skip_git: bool,
    post_validate: bool,
    strict_operation_evidence: bool,
    min_teams: int,
    min_roles: int,
    verbose: bool,
) -> int:
    target_root = resolve_target_root_here()
    if target_root is None:
        return fail(
            "AGENT_CONTEXT_MISSING",
            "agentteams orchestrate must run inside a git repository.",
            f"Next: {cli_command('init', include_compat=True)}",
        )

    takt_command = resolve_takt_command()
    if not takt_command:
        return fail(
            "TAKT_COMMAND_MISSING",
            "takt command not found.",
            "Install TAKT first: npm install -g takt",
        )

    task_path = resolve_task_file_path(task_file, target_root)
    if not task_path.exists():
        return fail(
            "PATH_LAYOUT_INVALID",
            f"task file not found: {task_path.as_posix()}",
            "Retry: agentteams orchestrate --task-file ./.codex/states/TASK-xxxxx-your-task.yaml",
        )
    if not task_path.is_file():
        return fail("PATH_LAYOUT_INVALID", f"task path is not a file: {task_path.as_posix()}")
    if not task_path.is_relative_to(target_root):
        return fail("PATH_LAYOUT_INVALID", "task file must be inside current repository.")
    if not TASK_FILE_NAME_PATTERN.fullmatch(task_path.name):
        return fail(
            "PATH_LAYOUT_INVALID",
            f"task filename must match TASK-xxxxx-slug.yaml: {task_path.name}",
        )

    piece_input = normalize_scalar(piece) or DEFAULT_TAKT_PIECE.as_posix()
    piece_path = Path(piece_input).expanduser()
    if not piece_path.is_absolute():
        piece_path = (target_root / piece_path).resolve()
    if not piece_path.exists():
        return fail(
            "PATH_LAYOUT_INVALID",
            f"piece file not found: {piece_path.as_posix()}",
            "Retry: agentteams init --here",
        )
    if not piece_path.is_file():
        return fail("PATH_LAYOUT_INVALID", f"piece path is not a file: {piece_path.as_posix()}")

    task_rel = task_path.relative_to(target_root).as_posix()
    task_id, task_title = extract_task_metadata(task_path)
    task_prompt = build_orchestrate_task_prompt(task_rel, task_id, task_title)

    command = [
        takt_command,
        "--pipeline",
        "--task",
        task_prompt,
        "--piece",
        piece_path.as_posix(),
    ]
    if skip_git:
        command.append("--skip-git")
    if provider:
        command.extend(["--provider", provider])
    if model:
        command.extend(["--model", model])

    is_verbose_enabled(verbose, f"orchestrate command: {' '.join(command)}")
    code, _ = run_cmd(command, cwd=target_root)
    if code != 0:
        return fail(
            "TAKT_ORCHESTRATE_FAILED",
            "takt pipeline execution failed.",
            "Inspect TAKT output and retry orchestrate.",
        )

    if post_validate:
        code = run_task_state_validation(template_root, target_root, task_path, verbose)
        if code != 0:
            return code
        code = run_operation_evidence_validation(
            template_root,
            target_root,
            task_rel,
            min_teams,
            min_roles,
            strict_operation_evidence,
        )
        if code != 0:
            return code

    print(
        "OK [TAKT_ORCHESTRATE_OK] "
        f"task={task_id} piece={piece_path.as_posix()} post_validate={'yes' if post_validate else 'no'}"
    )
    print(f"Next: {cli_command('doctor', include_compat=True)}")
    return 0


def parse_incident_index(path: Path) -> list[dict[str, str]]:
    incidents: list[dict[str, str]] = []
    lines = read_text_or_empty(path).splitlines()
    section = ""
    in_item = False
    item: dict[str, str] = {}

    def flush_item() -> None:
        nonlocal in_item, item
        if in_item and item:
            incidents.append(item.copy())
        in_item = False
        item = {}

    for line in lines:
        m_top = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$", line)
        if m_top:
            key = m_top.group(1)
            if key == "incidents":
                section = "incidents"
            else:
                section = ""
                flush_item()
            continue

        if section != "incidents":
            continue

        m_item = re.match(r"^\s{2}-\s*(.*)$", line)
        if m_item:
            flush_item()
            in_item = True
            inline = m_item.group(1).strip()
            if inline:
                m_inline = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$", inline)
                if m_inline:
                    item[m_inline.group(1)] = normalize_scalar(m_inline.group(2))
            continue

        if not in_item:
            continue

        m_key = re.match(r"^\s{4}([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$", line)
        if m_key:
            item[m_key.group(1)] = normalize_scalar(m_key.group(2))

    flush_item()
    return incidents


def parse_incident_document(path: Path) -> dict[str, object]:
    data: dict[str, object] = {
        "id": "",
        "title": "",
        "fingerprint": {},
        "classification": {},
        "first_seen_at": "",
        "last_seen_at": "",
        "occurrence_count_global": "0",
        "projects_seen": [],
        "source_tasks": [],
        "suggested_root_actions": "",
        "status": "",
        "updated_at": "",
    }

    section = ""
    in_projects = False
    in_tasks = False
    for line in read_text_or_empty(path).splitlines():
        m_top = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$", line)
        if m_top:
            key = m_top.group(1)
            value = normalize_scalar(m_top.group(2))
            section = key
            in_projects = False
            in_tasks = False

            if key in {
                "id",
                "title",
                "first_seen_at",
                "last_seen_at",
                "occurrence_count_global",
                "suggested_root_actions",
                "status",
                "updated_at",
            }:
                data[key] = value
                continue

            if key == "projects_seen":
                if value == "[]":
                    data["projects_seen"] = []
                    section = ""
                else:
                    in_projects = True
                continue

            if key == "source_tasks":
                if value == "[]":
                    data["source_tasks"] = []
                    section = ""
                else:
                    in_tasks = True
                continue
            continue

        if section == "fingerprint":
            m_fp = re.match(r"^\s{2}([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$", line)
            if m_fp:
                fp = data["fingerprint"]
                assert isinstance(fp, dict)
                fp[m_fp.group(1)] = normalize_scalar(m_fp.group(2))
            continue

        if section == "classification":
            m_cls = re.match(r"^\s{2}([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$", line)
            if m_cls:
                cls = data["classification"]
                assert isinstance(cls, dict)
                cls[m_cls.group(1)] = normalize_scalar(m_cls.group(2))
            continue

        if section == "projects_seen" and in_projects:
            m_project = re.match(r"^\s{2}-\s*(.+)$", line)
            if m_project:
                projects = data["projects_seen"]
                assert isinstance(projects, list)
                projects.append(normalize_scalar(m_project.group(1)))
                continue
            in_projects = False
            continue

        if section == "source_tasks" and in_tasks:
            m_task = re.match(r"^\s{2}-\s*(.+)$", line)
            if m_task:
                tasks = data["source_tasks"]
                assert isinstance(tasks, list)
                tasks.append(normalize_scalar(m_task.group(1)))
                continue
            in_tasks = False
            continue

    return data


def render_incident_document(data: dict[str, object]) -> str:
    fingerprint = data.get("fingerprint", {})
    classification = data.get("classification", {})
    projects_seen = ordered_unique(
        [str(v) for v in (data.get("projects_seen", []) if isinstance(data.get("projects_seen"), list) else [])]
    )
    source_tasks = ordered_unique(
        [str(v) for v in (data.get("source_tasks", []) if isinstance(data.get("source_tasks"), list) else [])]
    )

    fp_warning = normalize_scalar(str(fingerprint.get("warning_code", ""))) if isinstance(fingerprint, dict) else ""
    fp_role_pair = normalize_scalar(str(fingerprint.get("role_pair", ""))) if isinstance(fingerprint, dict) else ""
    fp_gate = normalize_scalar(str(fingerprint.get("gate", ""))) if isinstance(fingerprint, dict) else ""
    fp_keywords = normalize_scalar(str(fingerprint.get("keywords", ""))) if isinstance(fingerprint, dict) else ""
    cls_non_malicious = "true"
    if isinstance(classification, dict):
        cls_non_malicious = "true" if parse_bool(str(classification.get("non_malicious", "true"))) else "false"

    lines = [
        f"id: {normalize_scalar(str(data.get('id', '')))}",
        f"title: {sanitize_single_line(str(data.get('title', '')), max_len=180)}",
        "fingerprint:",
        f"  warning_code: {fp_warning}",
        f"  role_pair: {fp_role_pair}",
        f"  gate: {fp_gate}",
        f"  keywords: {fp_keywords}",
        "classification:",
        f"  non_malicious: {cls_non_malicious}",
        f"first_seen_at: {normalize_scalar(str(data.get('first_seen_at', '')))}",
        f"last_seen_at: {normalize_scalar(str(data.get('last_seen_at', '')))}",
        f"occurrence_count_global: {parse_int(str(data.get('occurrence_count_global', '1')), fallback=1)}",
        "projects_seen:",
    ]
    if projects_seen:
        lines.extend(f"  - {project}" for project in projects_seen)
    else:
        lines.append("  - unknown-project")

    lines.append("source_tasks:")
    if source_tasks:
        lines.extend(f"  - {task}" for task in source_tasks)
    else:
        lines.append("  - T-UNKNOWN")

    lines.extend(
        [
            f"suggested_root_actions: {normalize_scalar(str(data.get('suggested_root_actions', 'process')))}",
            f"status: {normalize_scalar(str(data.get('status', 'open')))}",
            f"updated_at: {normalize_scalar(str(data.get('updated_at', now_utc_iso())))}",
        ]
    )
    return "\n".join(lines) + "\n"


def render_incident_candidate_index(candidates: list[dict[str, str]], updated_at: str) -> str:
    lines = [
        "version: v1",
        f"updated_at: {updated_at}",
        "candidates:",
    ]
    for candidate in candidates:
        lines.extend(
            [
                f"  - id: {candidate.get('id', '')}",
                f"    file: {candidate.get('file', '')}",
                f"    warning_code: {candidate.get('warning_code', '')}",
                f"    role_pair: {candidate.get('role_pair', '')}",
                f"    status: {candidate.get('status', '')}",
                f"    updated_at: {candidate.get('updated_at', '')}",
            ]
        )
    return "\n".join(lines) + "\n"


def build_sync_meta(source: str, ref: str, commit: str, synced_at: str) -> str:
    lines = [
        "version: v1",
        f"source: {source}",
        f"ref: {ref}",
        f"commit: {commit}",
        f"synced_at: {synced_at}",
    ]
    return "\n".join(lines) + "\n"


def parse_warning_entries(lines: list[str], section_start: int, section_end: int) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    header_line = lines[section_start]
    if "[]" in header_line:
        return entries

    current: dict[str, str] = {}
    for line in lines[section_start + 1 : section_end]:
        m_item = re.match(r"^\s{2}-\s*(.*)$", line)
        if m_item:
            if current:
                entries.append(current.copy())
            current = {}
            inline = m_item.group(1).strip()
            if inline:
                m_inline = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$", inline)
                if m_inline:
                    current[m_inline.group(1)] = normalize_scalar(m_inline.group(2))
            continue

        m_key = re.match(r"^\s{4}([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$", line)
        if m_key:
            current[m_key.group(1)] = normalize_scalar(m_key.group(2))
    if current:
        entries.append(current.copy())
    return entries


def find_top_level_key_index(lines: list[str], key: str) -> int:
    pattern = re.compile(rf"^{re.escape(key)}\s*:")
    for idx, line in enumerate(lines):
        if pattern.match(line):
            return idx
    return -1


def find_top_level_range(lines: list[str], key: str) -> tuple[int, int]:
    start = find_top_level_key_index(lines, key)
    if start < 0:
        return -1, -1
    end = len(lines)
    for idx in range(start + 1, len(lines)):
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*\s*:", lines[idx]):
            end = idx
            break
    return start, end


def resolve_task_file_path(task_file: str, repo_root: Path) -> Path:
    input_path = Path(task_file).expanduser()
    if input_path.is_absolute():
        return input_path.resolve()

    candidate_cwd = (Path.cwd() / input_path).resolve()
    if candidate_cwd.exists():
        return candidate_cwd

    candidate_repo = (repo_root / input_path).resolve()
    return candidate_repo


def collect_candidate_index_entries(candidate_dir: Path) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for candidate_file in sorted(candidate_dir.glob("INC-*.yaml")):
        data = parse_incident_document(candidate_file)
        fingerprint = data.get("fingerprint", {})
        if not isinstance(fingerprint, dict):
            fingerprint = {}
        entries.append(
            {
                "id": normalize_scalar(str(data.get("id", candidate_file.stem))),
                "file": candidate_file.as_posix(),
                "warning_code": normalize_scalar(str(fingerprint.get("warning_code", ""))),
                "role_pair": normalize_scalar(str(fingerprint.get("role_pair", ""))),
                "status": normalize_scalar(str(data.get("status", ""))),
                "updated_at": normalize_scalar(str(data.get("updated_at", ""))),
            }
        )
    return entries


def sync_incident_registry(
    template_root: Path,
    source: str,
    ref: str,
    offline_ok: bool,
    verbose: bool,
) -> int:
    target_root = resolve_target_root_here()
    if target_root is None:
        return fail(
            "AGENT_CONTEXT_MISSING",
            "agentteams sync must run inside a git repository.",
            f"Next: {cli_command('init', include_compat=True)}",
        )

    source_input = source.strip()
    source_path = Path(source_input).expanduser()
    source_resolved = str(source_path.resolve()) if source_path.exists() else source_input

    cache_registry = target_root / INCIDENT_CACHE_REGISTRY
    cache_meta = target_root / INCIDENT_CACHE_META
    cache_incidents_dir = target_root / INCIDENT_CACHE_INCIDENTS_DIR
    cache_incidents_dir.mkdir(parents=True, exist_ok=True)

    tmp_root = Path(tempfile.mkdtemp(prefix="agentteams-sync-"))
    clone_root = tmp_root / "source"
    source_repo_root: Path | None = None
    commit = "unknown"
    try:
        local_source_index = source_path.resolve() / "knowledge" / "incidents" / "_index.yaml"
        if source_path.exists() and local_source_index.exists():
            source_repo_root = source_path.resolve()
            is_verbose_enabled(verbose, f"sync using local source repository: {source_repo_root.as_posix()}")
            commit_code, commit_output = run_cmd(
                ["git", "rev-parse", "HEAD"],
                cwd=source_repo_root,
                print_output=False,
            )
            if commit_code == 0 and commit_output:
                commit = commit_output.splitlines()[-1].strip()
        else:
            clone_cmd = [
                "git",
                "clone",
                "--depth",
                "1",
                "--single-branch",
                "--branch",
                ref,
                source_resolved,
                str(clone_root),
            ]
            is_verbose_enabled(verbose, f"sync clone command: {' '.join(clone_cmd)}")
            clone_code, clone_output = run_cmd(clone_cmd, print_output=verbose)
            if clone_code != 0:
                if offline_ok:
                    warn(
                        "INCIDENT_SYNC_FAILED",
                        f"sync skipped (offline-ok): failed to clone source '{source_resolved}' ref '{ref}'.",
                        "agentteams report-incident --task-file <path> --code <warning_code> --summary <text> --project <name>",
                    )
                    if verbose and clone_output:
                        print(clone_output)
                    return 0
                return fail(
                    "INCIDENT_SYNC_FAILED",
                    f"failed to clone source '{source_resolved}' ref '{ref}'.",
                    "Retry: agentteams sync --source <git-url> --ref <branch>",
                )
            source_repo_root = clone_root
            commit_code, commit_output = run_cmd(
                ["git", "rev-parse", "HEAD"],
                cwd=clone_root,
                print_output=False,
            )
            if commit_code == 0 and commit_output:
                commit = commit_output.splitlines()[-1].strip()

        assert source_repo_root is not None
        source_registry_root = source_repo_root / "knowledge" / "incidents"
        source_index = source_registry_root / "_index.yaml"
        if not source_index.exists():
            return fail(
                "INCIDENT_SYNC_FAILED",
                f"source registry index missing: {source_index.as_posix()}",
                "Check source repository layout and retry: agentteams sync --source <git-url>",
            )

        registry_validator = template_root / "scripts" / "validate-incident-registry.py"
        if registry_validator.exists():
            code, _ = run_cmd(
                [sys.executable, str(registry_validator), "--root", str(source_registry_root)],
                print_output=verbose,
            )
            if code != 0:
                return fail(
                    "INCIDENT_SYNC_FAILED",
                    "source incident registry validation failed.",
                    "Fix source registry, then retry: agentteams sync --source <git-url>",
                )
        else:
            is_verbose_enabled(
                verbose,
                f"incident registry validator not found, skipping validation: {registry_validator.as_posix()}",
            )

        index_entries = parse_incident_index(source_index)
        if not index_entries:
            return fail(
                "INCIDENT_SYNC_FAILED",
                "source incident index has no incidents.",
                "Update source registry and retry: agentteams sync --source <git-url>",
            )

        copied_files = 0
        expected_incident_files: set[str] = set()
        for entry in index_entries:
            incident_id = normalize_scalar(entry.get("id", ""))
            incident_file_rel = normalize_scalar(entry.get("file", ""))
            if not incident_id:
                return fail(
                    "INCIDENT_SYNC_FAILED",
                    "incident index entry is missing id.",
                    "Fix source incident index and retry: agentteams sync --source <git-url>",
                )

            source_file = (source_repo_root / incident_file_rel).resolve() if incident_file_rel else Path("")
            if not source_file.exists():
                fallback_source_file = source_registry_root / f"{incident_id}.yaml"
                if fallback_source_file.exists():
                    source_file = fallback_source_file.resolve()
                else:
                    return fail(
                        "INCIDENT_SYNC_FAILED",
                        f"incident file missing for id={incident_id}: {incident_file_rel}",
                        "Fix source registry and retry: agentteams sync --source <git-url>",
                    )

            destination_file = cache_incidents_dir / f"{incident_id}.yaml"
            expected_incident_files.add(destination_file.name)
            source_content = read_text_or_empty(source_file)
            if write_if_changed(destination_file, source_content):
                copied_files += 1

        removed_files = 0
        for existing in cache_incidents_dir.glob("INC-*.yaml"):
            if existing.name in expected_incident_files:
                continue
            existing.unlink()
            removed_files += 1

        index_changed = write_if_changed(cache_registry, read_text_or_empty(source_index))

        synced_at = now_utc_iso()
        meta_changed = write_if_changed(cache_meta, build_sync_meta(source_input, ref, commit, synced_at))

        print(
            "OK [INCIDENT_SYNC_OK] "
            f"source={source_input} ref={ref} commit={commit} "
            f"index_changed={'yes' if index_changed else 'no'} "
            f"incident_files_changed={copied_files} incident_files_removed={removed_files} "
            f"meta_changed={'yes' if meta_changed else 'no'}"
        )
        print(
            "Next: agentteams report-incident --task-file <path> --code <warning_code> "
            "--summary <text> --project <name>"
        )
        return 0
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)


def report_incident(
    task_file: str,
    warning_code_raw: str,
    summary_raw: str,
    project_raw: str,
    verbose: bool,
) -> int:
    target_root = resolve_target_root_here()
    if target_root is None:
        return fail(
            "AGENT_CONTEXT_MISSING",
            "agentteams report-incident must run inside a git repository.",
            f"Next: {cli_command('init', include_compat=True)}",
        )

    normalized_code = re.sub(r"[^A-Z0-9_]", "_", warning_code_raw.strip().upper()).strip("_")
    if not WARNING_CODE_PATTERN.fullmatch(normalized_code):
        return fail(
            "INCIDENT_REPORT_FAILED",
            f"warning code format is invalid: {warning_code_raw}",
            "Use an uppercase code such as PROTO_FIELD_CASE_MISMATCH",
        )
    if normalized_code not in ALLOWED_WARNING_CODES:
        allowed = ", ".join(sorted(ALLOWED_WARNING_CODES))
        return fail(
            "INCIDENT_REPORT_FAILED",
            f"unsupported warning code: {normalized_code}",
            f"Allowed codes: {allowed}",
        )

    summary = sanitize_single_line(summary_raw, max_len=180)
    project = sanitize_single_line(project_raw, max_len=80)
    if not summary:
        return fail(
            "INCIDENT_REPORT_FAILED",
            "summary is empty after normalization.",
            "Use --summary with meaningful text.",
        )
    if not project:
        return fail(
            "INCIDENT_REPORT_FAILED",
            "project is empty after normalization.",
            "Use --project with project identifier.",
        )

    task_path = resolve_task_file_path(task_file, target_root)
    if not task_path.exists():
        return fail(
            "SELF_UPDATE_TASK_PATH_INVALID",
            f"task file not found: {task_path.as_posix()}",
            "Retry: agentteams report-incident --task-file ./.codex/states/TASK-xxxxx-your-task.yaml --code <warning_code> --summary <text> --project <name>",
        )
    if not task_path.is_file():
        return fail(
            "SELF_UPDATE_TASK_PATH_INVALID",
            f"task path is not a file: {task_path.as_posix()}",
            "Retry with a TASK-*.yaml file path.",
        )
    if not task_path.is_relative_to(target_root):
        return fail(
            "SELF_UPDATE_TASK_SCOPE_INVALID",
            "task file must be inside current repository.",
            "Retry with a repository-local TASK-*.yaml path.",
        )
    if not TASK_FILE_NAME_PATTERN.fullmatch(task_path.name):
        return fail(
            "SELF_UPDATE_TASK_PATH_INVALID",
            f"task filename must match TASK-xxxxx-slug.yaml: {task_path.name}",
            "Retry with a valid task file path.",
        )

    timestamp = now_utc_iso()
    lines = read_text_or_empty(task_path).splitlines()
    task_id_idx = find_top_level_key_index(lines, "id")
    if task_id_idx < 0:
        return fail(
            "INCIDENT_REPORT_FAILED",
            f"task file is missing 'id': {task_path.as_posix()}",
            "Repair task file format, then retry.",
        )
    task_id = normalize_scalar(lines[task_id_idx].split(":", 1)[1] if ":" in lines[task_id_idx] else "")
    if not task_id:
        return fail(
            "INCIDENT_REPORT_FAILED",
            f"task id is empty: {task_path.as_posix()}",
            "Set task id, then retry.",
        )

    warnings_start, warnings_end = find_top_level_range(lines, "warnings")
    if warnings_start < 0:
        return fail(
            "INCIDENT_REPORT_FAILED",
            f"task file is missing 'warnings' section: {task_path.as_posix()}",
            "Repair task file format, then retry.",
        )
    notes_idx = find_top_level_key_index(lines, "notes")
    if notes_idx < 0:
        return fail(
            "INCIDENT_REPORT_FAILED",
            f"task file is missing 'notes': {task_path.as_posix()}",
            "Repair task file format, then retry.",
        )
    updated_at_idx = find_top_level_key_index(lines, "updated_at")
    if updated_at_idx < 0:
        return fail(
            "INCIDENT_REPORT_FAILED",
            f"task file is missing 'updated_at': {task_path.as_posix()}",
            "Repair task file format, then retry.",
        )

    existing_warnings = parse_warning_entries(lines, warnings_start, warnings_end)
    role_pair = "coordinator/coordinator->coordinator/coordinator"
    for warning in existing_warnings:
        code = normalize_scalar(warning.get("code", ""))
        source_role = normalize_scalar(warning.get("source_role", ""))
        target_role = normalize_scalar(warning.get("target_role", ""))
        if code == normalized_code and source_role and target_role:
            role_pair = f"{source_role}->{target_role}"
            break

    warning_added = False
    duplicate_warning = False
    for warning in existing_warnings:
        if (
            normalize_scalar(warning.get("code", "")) == normalized_code
            and normalize_scalar(warning.get("summary", "")) == summary
            and normalize_scalar(warning.get("detected_by", "")) == "at-report-incident"
        ):
            duplicate_warning = True
            break

    if not duplicate_warning:
        warning_id = f"W-INC-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        warning_lines = [
            f"  - id: {warning_id}",
            "    level: warning",
            f"    code: {normalized_code}",
            "    detected_by: at-report-incident",
            "    source_role: coordinator/coordinator",
            "    target_role: coordinator/coordinator",
            f"    detected_at: {timestamp}",
            f"    summary: {summary}",
            "    status: triaged",
            "    resolution_task_ids: []",
            f"    updated_at: {timestamp}",
        ]
        if "[]" in lines[warnings_start]:
            lines[warnings_start : warnings_start + 1] = ["warnings:", *warning_lines]
            delta = len(warning_lines)
            if notes_idx > warnings_start:
                notes_idx += delta
            if updated_at_idx > warnings_start:
                updated_at_idx += delta
        else:
            insertion_idx = warnings_end
            lines[insertion_idx:insertion_idx] = warning_lines
            delta = len(warning_lines)
            if notes_idx >= insertion_idx:
                notes_idx += delta
            if updated_at_idx >= insertion_idx:
                updated_at_idx += delta
        warning_added = True
        is_verbose_enabled(verbose, f"added warning entry for task {task_id}")
    else:
        is_verbose_enabled(verbose, f"warning already present for task {task_id}; skipping warning append")

    incident_note = f"INCIDENT_REPORT code={normalized_code} project={project} summary={summary}"
    notes_line = lines[notes_idx]
    notes_value = normalize_scalar(notes_line.split(":", 1)[1] if ":" in notes_line else "")
    notes_added = False
    if incident_note not in notes_value:
        updated_notes = f"{notes_value} | {incident_note}" if notes_value else incident_note
        lines[notes_idx] = f"notes: {updated_notes}"
        notes_added = True
        is_verbose_enabled(verbose, f"appended incident evidence to notes for task {task_id}")
    else:
        is_verbose_enabled(verbose, f"incident evidence already exists in notes for task {task_id}")

    task_changed = warning_added or notes_added
    if task_changed:
        lines[updated_at_idx] = f"updated_at: {timestamp}"
        updated_text = "\n".join(lines).rstrip("\n") + "\n"
        write_if_changed(task_path, updated_text)
    else:
        is_verbose_enabled(verbose, f"task file already up to date for incident report: {task_path.as_posix()}")

    registry_entries = parse_incident_index(target_root / INCIDENT_CACHE_REGISTRY)
    matched_registry_entry: dict[str, str] | None = None
    for entry in registry_entries:
        if (
            normalize_scalar(entry.get("fingerprint_warning_code", "")) == normalized_code
            and normalize_scalar(entry.get("fingerprint_role_pair", "")) == role_pair
        ):
            matched_registry_entry = entry
            break
    if matched_registry_entry is None:
        for entry in registry_entries:
            if normalize_scalar(entry.get("fingerprint_warning_code", "")) == normalized_code:
                matched_registry_entry = entry
                break

    if matched_registry_entry is not None:
        incident_id = normalize_scalar(matched_registry_entry.get("id", ""))
    else:
        incident_id = f"INC-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{slugify(f'{normalized_code}-{project}')}"

    if not incident_id:
        return fail(
            "INCIDENT_REPORT_FAILED",
            "unable to determine incident id.",
            "Retry: agentteams report-incident --task-file <path> --code <warning_code> --summary <text> --project <name>",
        )

    candidate_dir = target_root / INCIDENT_CANDIDATE_DIR
    candidate_dir.mkdir(parents=True, exist_ok=True)
    candidate_file = candidate_dir / f"{incident_id}.yaml"

    candidate_data = parse_incident_document(candidate_file) if candidate_file.exists() else {}
    if not candidate_data:
        cached_incident_file = target_root / INCIDENT_CACHE_INCIDENTS_DIR / f"{incident_id}.yaml"
        if cached_incident_file.exists():
            candidate_data = parse_incident_document(cached_incident_file)
        else:
            candidate_data = {}

    base_projects = (
        [str(v) for v in candidate_data.get("projects_seen", [])]
        if isinstance(candidate_data.get("projects_seen"), list)
        else []
    )
    base_tasks = (
        [str(v) for v in candidate_data.get("source_tasks", [])]
        if isinstance(candidate_data.get("source_tasks"), list)
        else []
    )

    occurrence_count = parse_int(str(candidate_data.get("occurrence_count_global", "0")), fallback=0)
    occurrence_count = max(occurrence_count, 0) + 1

    fingerprint_base = candidate_data.get("fingerprint", {})
    if not isinstance(fingerprint_base, dict):
        fingerprint_base = {}
    classification_base = candidate_data.get("classification", {})
    if not isinstance(classification_base, dict):
        classification_base = {}

    default_status = "open"
    if matched_registry_entry is not None and normalize_scalar(matched_registry_entry.get("status", "")):
        default_status = normalize_scalar(matched_registry_entry.get("status", ""))

    candidate_payload: dict[str, object] = {
        "id": incident_id,
        "title": normalize_scalar(str(candidate_data.get("title", "")))
        or f"Recurring incident candidate: {normalized_code} ({project})",
        "fingerprint": {
            "warning_code": normalized_code,
            "role_pair": role_pair,
            "gate": normalize_scalar(str(fingerprint_base.get("gate", ""))) or "Protocol Gate",
            "keywords": normalize_scalar(str(fingerprint_base.get("keywords", "")))
            or f"{slugify(normalized_code)}|{slugify(project)}|incident-report",
        },
        "classification": {
            "non_malicious": parse_bool(str(classification_base.get("non_malicious", "true")), fallback=True)
        },
        "first_seen_at": normalize_scalar(str(candidate_data.get("first_seen_at", ""))) or timestamp,
        "last_seen_at": timestamp,
        "occurrence_count_global": str(occurrence_count),
        "projects_seen": ordered_unique(base_projects + [project]),
        "source_tasks": ordered_unique(base_tasks + [task_id]),
        "suggested_root_actions": normalize_scalar(str(candidate_data.get("suggested_root_actions", "")))
        or "process",
        "status": normalize_scalar(str(candidate_data.get("status", ""))) or default_status,
        "updated_at": timestamp,
    }
    write_if_changed(candidate_file, render_incident_document(candidate_payload))

    candidate_index_entries = collect_candidate_index_entries(candidate_dir)
    write_if_changed(
        target_root / INCIDENT_CANDIDATE_INDEX,
        render_incident_candidate_index(candidate_index_entries, timestamp),
    )

    print(
        "OK [INCIDENT_REPORTED] "
        f"task={task_id} code={normalized_code} project={project} "
        f"task_updated={'yes' if task_changed else 'no'} candidate={candidate_file.as_posix()}"
    )
    print(f"Next: {cli_command('doctor', include_compat=True)}")
    return 0


def guard_chat(command_args: list[str]) -> int:
    repo_root = Path(__file__).resolve().parent.parent
    guard_script = repo_root / "scripts" / "guard-chat.py"
    if not guard_script.exists():
        return fail(
            "PATH_LAYOUT_INVALID",
            f"missing guard script: {guard_script.as_posix()}",
            "Reinstall AgentTeams and retry: agentteams init --here",
        )

    command = [sys.executable, str(guard_script), *command_args]
    code, _ = run_cmd(command)
    return code


def main(argv: list[str]) -> int:
    template_root = Path(__file__).resolve().parent.parent
    args = [arg for arg in argv if arg is not None]

    if not args:
        usage()
        return 1

    if args[0] == "--":
        args = args[1:]
        if not args:
            usage()
            return 1

    command = args[0]
    command_args = args[1:]

    if command not in {"init", "doctor", "sync", "report-incident", "guard-chat", "orchestrate"}:
        usage()
        return fail(
            "PATH_LAYOUT_INVALID",
            f"unknown subcommand: {command}",
            "Usage: agentteams init [<git-url>] | agentteams init --here | agentteams doctor | agentteams sync | agentteams report-incident | agentteams guard-chat | agentteams orchestrate",
        )

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
        code = ensure_git_available()
        if code != 0:
            return code
        return doctor(verbose)

    code = ensure_git_available()
    if code != 0:
        return code

    if command == "init":
        repo_url, use_here, workspace, policy, verbose, parse_code = parse_init_args(command_args)
        if parse_code != 0:
            return parse_code

        if use_here:
            return init_here(template_root, policy, verbose)

        if not repo_url and workspace == str(Path.cwd()):
            auto_target = resolve_target_root_here()
            if auto_target is not None:
                is_verbose_enabled(
                    verbose,
                    "no repository url provided; running --here mode in current git repository.",
                )
                return init_here(template_root, policy, verbose)

        repo_url, resolve_code = resolve_repo_url_interactive(repo_url)
        if resolve_code != 0:
            return resolve_code

        return init_with_clone(template_root, repo_url, workspace, policy, verbose)

    if command == "sync":
        source, ref, offline_ok, verbose, parse_code = parse_sync_args(command_args)
        if parse_code != 0:
            return parse_code
        return sync_incident_registry(template_root, source, ref, offline_ok, verbose)

    if command == "guard-chat":
        return guard_chat(command_args)

    if command == "orchestrate":
        (
            task_file,
            piece,
            provider,
            model,
            skip_git,
            post_validate,
            strict_operation_evidence,
            min_teams,
            min_roles,
            verbose,
            parse_code,
        ) = parse_orchestrate_args(command_args)
        if parse_code != 0:
            return parse_code
        return orchestrate_task(
            template_root,
            task_file,
            piece,
            provider,
            model,
            skip_git,
            post_validate,
            strict_operation_evidence,
            min_teams,
            min_roles,
            verbose,
        )

    task_file, warning_code, summary, project, verbose, parse_code = parse_report_incident_args(command_args)
    if parse_code != 0:
        return parse_code
    return report_incident(task_file, warning_code, summary, project, verbose)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
