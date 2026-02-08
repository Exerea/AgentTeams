#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys


MANAGED_MARKER = "<!-- AGENTTEAMS_MANAGED:ENTRY v1 -->"
CHAT_LOG_RELATIVE_PATH = Path("logs") / "e2e-ai-log.md"


def usage() -> None:
    print("Usage:")
    print(
        "  at init [<git-url>] [-w|--workspace <path>] "
        "[--agents-policy coexist|replace|keep] [--verbose]"
    )
    print("  at init --here [--agents-policy coexist|replace|keep] [--verbose]")
    print("  at doctor [--verbose]")


def fail(code: str, message: str, next_command: str | None = None) -> int:
    print(f"ERROR [{code}] {message}")
    if next_command:
        print(f"Next: {next_command}")
    return 1


def is_verbose_enabled(verbose: bool, message: str) -> None:
    if verbose:
        print(f"[at] {message}")


def read_text_or_empty(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


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
        "# AGENTS.md (AgentTeams Entry)",
        "",
        MANAGED_MARKER,
        "This file is the AgentTeams entrypoint.",
        "Resolution order:",
        "1. `.codex/AGENTS.md` (AgentTeams canonical rules)",
        "2. `.codex/AGENTS.local.md` (previous local rules, optional)",
    ]
    return "\n".join(lines)


def chat_log_template_content() -> str:
    lines = [
        "# E2E AI Log (v2.8)",
        "",
        "- declaration_protocol: Task開始時は「固定開始宣言 -> 稼働口上 -> DECLARATION」の3行を必須化",
        "",
        "## Entries",
        "- 2026-01-01T00:00:00Z 殿のご命令と各AGENTS.mdに忠実に従う家臣たちが集まりました。──家臣たちが動きます！",
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
            "Retry: at init --here",
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
        print(output)
    return proc.returncode, output


def ensure_git_available() -> int:
    if shutil.which("git") is None:
        return fail(
            "PATH_LAYOUT_INVALID",
            "git command not found.",
            "Install git, then retry: at init <git-url>",
        )
    return 0


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
            "Usage: at init <git-url> | at init --here",
        )
    return entered, 0


def invoke_bootstrap(template_root: Path, target_root: Path) -> int:
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
                "Retry: at init --here --agents-policy coexist",
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
            "Retry: at init --here --agents-policy coexist",
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
        print("Next: at init")
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

    if has_error or has_warning:
        print("Next: at init --here")
        return 1

    print("Next: at init --here")
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
            "Example: at init https://github.com/<org>/<repo>.git",
        )

    target_root = workspace_root / repo_name
    if target_root.exists():
        return fail(
            "PATH_LAYOUT_INVALID",
            f"target already exists: {target_root.as_posix()}",
            "For existing clone: at init --here",
        )

    is_verbose_enabled(verbose, f"cloning {repo_url} -> {target_root.as_posix()}")
    code, _ = run_cmd(["git", "clone", repo_url, str(target_root)])
    if code != 0:
        return fail(
            "GIT_CLONE_FAILED",
            f"git clone failed: {repo_url}",
            f'Check URL and retry: at init {repo_url} -w "{workspace_root.as_posix()}"',
        )

    code = invoke_bootstrap(template_root, target_root)
    if code != 0:
        return code

    code = apply_agents_policy(target_root, policy, verbose)
    if code != 0:
        return code

    ensure_chat_log_template(target_root, verbose)
    print(f"at init completed: {target_root.as_posix()}")
    return 0


def init_here(template_root: Path, policy: str, verbose: bool) -> int:
    target_root = resolve_target_root_here()
    if target_root is None:
        return fail(
            "PATH_LAYOUT_INVALID",
            "--here can only be used inside a git repository.",
            "For new setup: at init <git-url>",
        )

    is_verbose_enabled(verbose, f"target root: {target_root.as_posix()}")

    code = invoke_bootstrap(template_root, target_root)
    if code != 0:
        return code

    code = apply_agents_policy(target_root, policy, verbose)
    if code != 0:
        return code

    ensure_chat_log_template(target_root, verbose)
    print(f"at init completed: {target_root.as_posix()}")
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
                    "Usage: at init <git-url> -w <path>",
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
                "Usage: at init <git-url> | at init --here",
            )
        if repo_url:
            return "", False, "", "", False, fail(
                "PATH_LAYOUT_INVALID",
                f"multiple repository urls provided: {repo_url}, {token}",
                "Usage: at init <git-url>",
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
            "New setup: at init <git-url> / Existing clone: at init --here",
        )

    if use_here and workspace != str(Path.cwd()):
        return "", False, "", "", False, fail(
            "PATH_LAYOUT_INVALID",
            "--workspace cannot be used with --here.",
            "For existing clone: at init --here",
        )

    return repo_url, use_here, workspace, policy, verbose, 0


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

    if command not in {"init", "doctor"}:
        usage()
        return fail(
            "PATH_LAYOUT_INVALID",
            f"unknown subcommand: {command}",
            "Usage: at init [<git-url>] | at init --here | at doctor",
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
                "Usage: at doctor [--verbose]",
            )
        code = ensure_git_available()
        if code != 0:
            return code
        return doctor(verbose)

    code = ensure_git_available()
    if code != 0:
        return code

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


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
