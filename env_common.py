import shutil
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent
PLACEHOLDER_VALUES = {
    "",
    "your-internal-qwen-key",
    "your-api-key",
    "changeme",
    "change-me",
    "none",
    "null",
}


def env_candidates(start: Path | None = None) -> list[Path]:
    roots = []
    if start:
        roots.append(start.resolve())
    roots.extend([Path.cwd().resolve(), PROJECT_ROOT])
    for parent in PROJECT_ROOT.parents:
        roots.append(parent)

    seen = set()
    candidates = []
    for root in roots:
        if root in seen:
            continue
        seen.add(root)
        candidates.append(root / ".env")
    return candidates


def find_env_file(start: Path | None = None) -> Path | None:
    for path in env_candidates(start):
        if path.exists() and path.is_file():
            return path
    return None


def ensure_env_file() -> Path:
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        return env_path
    example_path = PROJECT_ROOT / ".env.example"
    if not example_path.exists():
        env_path.write_text("", encoding="utf-8")
        return env_path
    shutil.copyfile(example_path, env_path)
    return env_path


def load_project_env() -> Path | None:
    env_path = find_env_file()
    if env_path:
        load_dotenv(env_path, override=True)
        return env_path
    load_dotenv()
    return None


def is_placeholder_value(value: str | None) -> bool:
    normalized = str(value or "").strip().strip('"').strip("'").lower()
    return normalized in PLACEHOLDER_VALUES or "xxx.xxx" in normalized or normalized.startswith("http://xxx")


def read_env_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    return path.read_text(encoding="utf-8").splitlines()


def write_env_value(path: Path, key: str, value: str) -> None:
    key = key.strip()
    lines = read_env_lines(path)
    updated = False
    output = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#") or "=" not in line:
            output.append(line)
            continue
        current_key, _ = line.split("=", 1)
        if current_key.strip() == key:
            output.append(f"{key}={value}")
            updated = True
        else:
            output.append(line)
    if not updated:
        output.append(f"{key}={value}")
    path.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")
