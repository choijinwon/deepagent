import os
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ops_common import slugify


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


def dev_run_dir() -> Path:
    return Path(os.getenv("DEV_RUN_DIR", "dev_runs")).resolve()


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
