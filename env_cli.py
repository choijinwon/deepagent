from env_common import ensure_env_file, find_env_file, load_project_env
from ui_common import print_key_value_table, print_status_line


def main() -> None:
    env_path = find_env_file()
    created = False
    if env_path is None:
        env_path = ensure_env_file()
        created = True
    load_project_env()
    print_status_line(".env 파일을 확인했습니다.", "green")
    print_key_value_table(
        "Environment File",
        [
            ("Path", str(env_path)),
            ("Created", "yes" if created else "no"),
            ("Edit", "notepad .env"),
        ],
    )
    if created:
        print_status_line(".env.example을 복사해 .env를 만들었습니다. QWEN_API_KEY, QWEN_BASE_URL, QWEN_MODEL 값을 수정하세요.", "yellow")


if __name__ == "__main__":
    main()
