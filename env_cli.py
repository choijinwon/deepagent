import argparse
import os
from getpass import getpass

from env_common import ensure_env_file, find_env_file, is_placeholder_value, load_project_env, write_env_value
from ui_common import print_key_value_table, print_status_line


ENV_KEYS = ["QWEN_API_KEY", "QWEN_BASE_URL", "QWEN_MODEL", "QWEN_MODELS"]


def env_path_or_create():
    env_path = find_env_file()
    created = False
    if env_path is None:
        env_path = ensure_env_file()
        created = True
    load_project_env()
    return env_path, created


def masked(value: str) -> str:
    if not value:
        return "missing"
    if is_placeholder_value(value):
        return "placeholder"
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}***{value[-4:]}"


def show_env() -> None:
    env_path, created = env_path_or_create()
    rows = [
        ("Path", str(env_path)),
        ("Created", "yes" if created else "no"),
        ("Explicit", os.getenv("DEEPAGENT_ENV_FILE", "") or "not set"),
        ("Edit", "notepad .env"),
    ]
    rows.extend((key, masked(os.getenv(key, ""))) for key in ENV_KEYS)
    print_status_line(".env 파일을 확인했습니다.", "green")
    print_key_value_table("Environment File", rows)
    missing = [key for key in ENV_KEYS[:3] if is_placeholder_value(os.getenv(key, ""))]
    if missing:
        print_status_line(f"값을 입력해야 합니다: {', '.join(missing)}", "yellow")
        print_status_line("터미널에서 바로 설정하려면 `deepagent-env setup`을 실행하세요.", "yellow")


def ask_value(label: str, current: str = "", *, secret: bool = False) -> str:
    current_label = "현재값 있음" if current and not is_placeholder_value(current) else "비어 있음"
    prompt = f"{label} ({current_label}, Enter=유지): "
    if secret:
        value = getpass(prompt).strip()
    else:
        value = input(prompt).strip()
    return value


def setup_env() -> None:
    env_path, _ = env_path_or_create()
    print_status_line(f".env 설정 파일: {env_path}", "cyan")

    api_key = ask_value("QWEN_API_KEY", os.getenv("QWEN_API_KEY", ""), secret=True)
    if api_key:
        write_env_value(env_path, "QWEN_API_KEY", api_key)

    base_url = ask_value("QWEN_BASE_URL 예: http://10.0.0.1:8000/v1", os.getenv("QWEN_BASE_URL", ""))
    if base_url:
        write_env_value(env_path, "QWEN_BASE_URL", base_url)

    model = ask_value("QWEN_MODEL 예: qwen3.5", os.getenv("QWEN_MODEL", ""))
    if model:
        write_env_value(env_path, "QWEN_MODEL", model)

    models = ask_value("QWEN_MODELS 예: qwen3.5,gpt20,gamma", os.getenv("QWEN_MODELS", ""))
    if models:
        write_env_value(env_path, "QWEN_MODELS", models)

    load_project_env()
    print_status_line(".env 설정을 저장했습니다.", "green")
    show_env()


def set_env_value(key: str, value: str) -> None:
    env_path, _ = env_path_or_create()
    if not key:
        raise ValueError("KEY가 필요합니다. 예: deepagent-env set QWEN_API_KEY sk-...")
    write_env_value(env_path, key, value)
    load_project_env()
    print_status_line(f"{key} 값을 저장했습니다: {env_path}", "green")


def print_env_path() -> None:
    env_path, _ = env_path_or_create()
    print(str(env_path))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="deepagent-env", description=".env 파일을 생성하고 Qwen 설정을 확인/수정합니다.")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("show", help=".env 경로와 주요 설정 상태를 표시합니다.")
    subparsers.add_parser("path", help="로드되는 .env 파일 경로만 출력합니다.")
    subparsers.add_parser("setup", help="질문형으로 QWEN_API_KEY, QWEN_BASE_URL, QWEN_MODEL을 설정합니다.")
    set_parser = subparsers.add_parser("set", help=".env 값을 하나 설정합니다.")
    set_parser.add_argument("key")
    set_parser.add_argument("value")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "setup":
        setup_env()
    elif args.command == "set":
        set_env_value(args.key, args.value)
    elif args.command == "path":
        print_env_path()
    else:
        show_env()


if __name__ == "__main__":
    main()
