import shutil
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent


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
