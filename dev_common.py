import difflib
import json
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from ops_common import slugify
from utils import file_date_string


@dataclass
class DevRunResult:
    command: str
    cwd: Path
    exit_code: int
    stdout: str
    stderr: str
    started_at: str
    finished_at: str
    timed_out: bool = False

    @property
    def output(self) -> str:
        parts = []
        if self.stdout:
            parts.extend(["## STDOUT", "", self.stdout.rstrip(), ""])
        if self.stderr:
            parts.extend(["## STDERR", "", self.stderr.rstrip(), ""])
        if not parts:
            parts.extend(["## Output", "", "(no output)", ""])
        return "\n".join(parts)


@dataclass
class DevPatchCandidate:
    id: str
    title: str
    target_path: Path
    reason: str
    diff_text: str
    new_content: str
    applyable: bool = True


@dataclass
class DevSession:
    name: str
    command: str
    cwd: Path
    log_path: Path | None = None
    fix_path: Path | None = None
    patch_path: Path | None = None
    exit_code: int | None = None
    status: str = "created"
    created_at: str = ""
    updated_at: str = ""


def dev_run_dir() -> Path:
    return Path(os.getenv("DEV_RUN_DIR", "dev_runs")).resolve()


def dev_session_dir() -> Path:
    return Path(os.getenv("DEV_SESSION_DIR", "dev_sessions")).resolve()


def dev_patch_dir() -> Path:
    return Path(os.getenv("DEV_PATCH_DIR", "dev_patches")).resolve()


def dev_command_timeout() -> int:
    try:
        return max(5, int(os.getenv("DEV_COMMAND_TIMEOUT", "120")))
    except ValueError:
        return 120


def run_development_command(command: str, cwd: Path) -> DevRunResult:
    command = command.strip()
    if not command:
        raise ValueError("command is required")
    cwd = cwd.resolve()
    cwd.mkdir(parents=True, exist_ok=True)
    started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            shell=True,
            text=True,
            capture_output=True,
            timeout=dev_command_timeout(),
        )
        return DevRunResult(
            command=command,
            cwd=cwd,
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            started_at=started_at,
            finished_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
    except subprocess.TimeoutExpired as exc:
        return DevRunResult(
            command=command,
            cwd=cwd,
            exit_code=124,
            stdout=exc.stdout or "",
            stderr=exc.stderr or f"Command timed out after {dev_command_timeout()} seconds.",
            started_at=started_at,
            finished_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            timed_out=True,
        )


def quote_command_arg(value: str) -> str:
    if os.name == "nt":
        return subprocess.list2cmdline([value])
    return "'" + value.replace("'", "'\"'\"'") + "'"


def iter_project_files(root: Path, suffix: str, *, limit: int = 120) -> list[Path]:
    ignored = {
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        "offline_packages",
        "offline_bundle",
        "external_sources",
        "node_modules",
        "dist",
        "build",
    }
    files: list[Path] = []
    for path in root.rglob(f"*{suffix}"):
        if any(part in ignored for part in path.parts):
            continue
        if path.is_file():
            files.append(path)
        if len(files) >= limit:
            break
    return sorted(files)


def suggest_development_commands(cwd: Path) -> list[dict[str, str]]:
    cwd = cwd.resolve()
    suggestions: list[dict[str, str]] = []
    py_files = iter_project_files(cwd, ".py", limit=80)
    if py_files:
        relative_files = [quote_command_arg(str(path.relative_to(cwd))) for path in py_files]
        suggestions.append(
            {
                "name": "python-compile",
                "label": "Python 문법 검사",
                "command": "python -m py_compile " + " ".join(relative_files),
            }
        )
    if (cwd / "tests").exists() or list(cwd.glob("test_*.py")) or list(cwd.glob("*_test.py")):
        suggestions.append({"name": "pytest", "label": "Python 테스트 실행", "command": "python -m pytest"})
    if (cwd / "package.json").exists():
        suggestions.append({"name": "npm-test", "label": "Node 테스트 실행", "command": "npm test"})
    if (cwd / "app.py").exists():
        suggestions.append({"name": "python-app", "label": "app.py 실행", "command": "python app.py"})
    if (cwd / "main.py").exists():
        suggestions.append({"name": "python-main", "label": "main.py 실행", "command": "python main.py"})
    return suggestions


def render_dev_run_markdown(result: DevRunResult) -> str:
    lines = [
        f"# Dev Run - {result.command}",
        "",
        f"- Started: {result.started_at}",
        f"- Finished: {result.finished_at}",
        f"- Working Directory: {result.cwd}",
        f"- Exit Code: {result.exit_code}",
        f"- Timed Out: {'yes' if result.timed_out else 'no'}",
        "",
        "## Command",
        "",
        "```text",
        result.command,
        "```",
        "",
        result.output,
    ]
    return "\n".join(lines).rstrip() + "\n"


def save_dev_run(result: DevRunResult) -> Path:
    directory = dev_run_dir() / datetime.now().strftime("%Y-%m-%d")
    directory.mkdir(parents=True, exist_ok=True)
    filename = f"{datetime.now().strftime('%H%M%S')}-{slugify(result.command, 'command')}.md"
    path = directory / filename
    path.write_text(render_dev_run_markdown(result), encoding="utf-8")
    return path


def session_to_payload(session: DevSession) -> dict[str, Any]:
    return {
        "name": session.name,
        "command": session.command,
        "cwd": str(session.cwd),
        "log_path": str(session.log_path) if session.log_path else "",
        "fix_path": str(session.fix_path) if session.fix_path else "",
        "patch_path": str(session.patch_path) if session.patch_path else "",
        "exit_code": session.exit_code,
        "status": session.status,
        "created_at": session.created_at,
        "updated_at": session.updated_at,
    }


def payload_to_session(payload: dict[str, Any]) -> DevSession:
    return DevSession(
        name=str(payload.get("name") or "dev-session"),
        command=str(payload.get("command") or ""),
        cwd=Path(payload.get("cwd") or ".").resolve(),
        log_path=Path(payload["log_path"]).resolve() if payload.get("log_path") else None,
        fix_path=Path(payload["fix_path"]).resolve() if payload.get("fix_path") else None,
        patch_path=Path(payload["patch_path"]).resolve() if payload.get("patch_path") else None,
        exit_code=payload.get("exit_code"),
        status=str(payload.get("status") or "created"),
        created_at=str(payload.get("created_at") or ""),
        updated_at=str(payload.get("updated_at") or ""),
    )


def save_dev_session(session: DevSession) -> Path:
    directory = dev_session_dir()
    directory.mkdir(parents=True, exist_ok=True)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if not session.created_at:
        session.created_at = now
    session.updated_at = now
    path = directory / f"{slugify(session.name, 'dev-session')}.json"
    path.write_text(json.dumps(session_to_payload(session), ensure_ascii=False, indent=2), encoding="utf-8")
    latest = directory / "latest.json"
    latest.write_text(json.dumps(session_to_payload(session), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_dev_session(name: str = "latest") -> DevSession:
    directory = dev_session_dir()
    path = directory / ("latest.json" if name in ("", "latest") else f"{slugify(name, 'dev-session')}.json")
    if not path.exists():
        raise FileNotFoundError(path)
    return payload_to_session(json.loads(path.read_text(encoding="utf-8")))


def list_dev_sessions() -> list[str]:
    directory = dev_session_dir()
    directory.mkdir(parents=True, exist_ok=True)
    return [path.stem for path in sorted(directory.glob("*.json")) if path.stem != "latest"]


def safe_target_path(cwd: Path, value: str) -> Path:
    raw = Path(value)
    path = raw if raw.is_absolute() else cwd / raw
    path = path.resolve()
    try:
        path.relative_to(cwd.resolve())
    except ValueError as exc:
        raise ValueError(f"Patch target escapes workspace: {path}") from exc
    return path


def build_unified_diff(path: Path, old_content: str, new_content: str) -> str:
    return "".join(
        difflib.unified_diff(
            old_content.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile=f"a/{path.name}",
            tofile=f"b/{path.name}",
        )
    )


def generate_patch_candidates(report: dict[str, Any], cwd: Path) -> list[DevPatchCandidate]:
    candidates: list[DevPatchCandidate] = []
    cwd = cwd.resolve()
    requirements_candidates = [
        cwd / "requirements.lock.txt",
        cwd / "requirements.txt",
    ]
    requirements_path = next((path for path in requirements_candidates if path.exists()), cwd / "requirements.txt")

    for index, finding in enumerate(report.get("findings", []), start=1):
        if finding.get("type") != "missing_package":
            continue
        evidence = str(finding.get("evidence") or "")
        module = ""
        marker = "No module named"
        if marker in evidence:
            module = evidence.split(marker, 1)[1].strip().strip("'\"` ")
        if not module:
            continue
        old_content = requirements_path.read_text(encoding="utf-8") if requirements_path.exists() else ""
        lines = [line.strip().lower() for line in old_content.splitlines()]
        if module.lower() in lines:
            continue
        separator = "" if not old_content or old_content.endswith("\n") else "\n"
        new_content = f"{old_content}{separator}{module}\n"
        diff_text = build_unified_diff(requirements_path, old_content, new_content)
        candidates.append(
            DevPatchCandidate(
                id=f"patch-{index}",
                title=f"Add missing package `{module}`",
                target_path=requirements_path,
                reason=str(finding.get("recommendation") or finding.get("cause") or ""),
                diff_text=diff_text,
                new_content=new_content,
            )
        )
    return candidates


def render_patch_candidates(candidates: list[DevPatchCandidate]) -> str:
    if not candidates:
        return "# Patch Candidates\n\nNo automatically applyable patch candidates were found.\n"
    lines = ["# Patch Candidates", ""]
    for index, candidate in enumerate(candidates, start=1):
        lines.extend(
            [
                f"## {index}. {candidate.title}",
                "",
                f"- Target: {candidate.target_path}",
                f"- Applyable: {'yes' if candidate.applyable else 'no'}",
                f"- Reason: {candidate.reason}",
                "",
                "```diff",
                candidate.diff_text.rstrip(),
                "```",
                "",
            ]
        )
    return "\n".join(lines)


def save_patch_candidates(candidates: list[DevPatchCandidate], source_name: str) -> Path:
    directory = dev_patch_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{file_date_string()}-{slugify(source_name, 'patch')}.md"
    path.write_text(render_patch_candidates(candidates), encoding="utf-8")
    return path


def apply_patch_candidates(candidates: list[DevPatchCandidate]) -> list[Path]:
    applied: list[Path] = []
    for candidate in candidates:
        if not candidate.applyable:
            continue
        candidate.target_path.parent.mkdir(parents=True, exist_ok=True)
        candidate.target_path.write_text(candidate.new_content, encoding="utf-8")
        applied.append(candidate.target_path)
    return applied
