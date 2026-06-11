from __future__ import annotations

import sys

from ui_common import print_markdown_result, print_status_line, rich_enabled


MENU = [
    ("1", "chat", "챗봇형 CLI", "deepagent-chat", "chat_cli"),
    ("2", "web", "웹 UI", "deepagent-web", "web_closed"),
    ("3", "console", "메뉴형 콘솔 UI", "deepagent-console", "console_ui"),
    ("4", "scaffold", "아이디어로 폴더/파일 생성", "deepagent-scaffold", "scaffold_cli"),
    ("5", "doctor", "폐쇄망 환경 진단", "deepagent-doctor", "doctor"),
    ("6", "run", "기본 단발 실행 테스트", "deepagent-run", "app_closed"),
]


def render_menu() -> None:
    if rich_enabled():
        from rich.table import Table
        from ui_common import console

        table = Table(title="DeepAgent Launcher", show_lines=True)
        table.add_column("번호", justify="center", style="bold cyan", no_wrap=True)
        table.add_column("선택어", style="bold green", no_wrap=True)
        table.add_column("기능")
        table.add_column("직접 명령")
        for number, alias, title, command, _ in MENU:
            table.add_row(number, alias, title, command)
        console.print(table)
        console.print("[dim]번호나 선택어를 입력하세요. 종료는 q 입니다.[/dim]")
        return

    print("")
    print("=" * 78)
    print(" DeepAgent Launcher")
    print("=" * 78)
    for number, alias, title, command, _ in MENU:
        print(f"{number}. {title:<24} ({alias})  -> {command}")
    print("q. 종료")


def module_for_choice(value: str) -> tuple[str, str] | None:
    selected = value.strip().lower()
    if not selected:
        return None
    for number, alias, title, command, module_name in MENU:
        if selected in (number, alias, command):
            return title, module_name
    return None


def dispatch(module_name: str) -> None:
    if module_name == "chat_cli":
        from chat_cli import main
    elif module_name == "web_closed":
        from web_closed import main
    elif module_name == "console_ui":
        from console_ui import main
    elif module_name == "scaffold_cli":
        from scaffold_cli import main
    elif module_name == "doctor":
        from doctor import main
    elif module_name == "app_closed":
        from app_closed import main
    else:
        raise ValueError(f"unknown launcher module: {module_name}")
    main()


def main() -> None:
    args = [item.strip() for item in sys.argv[1:] if item.strip()]
    if args:
        choice = module_for_choice(args[0])
        if not choice:
            print_status_line(f"알 수 없는 선택입니다: {args[0]}", "red")
            render_menu()
            raise SystemExit(1)
        _, module_name = choice
        dispatch(module_name)
        return

    while True:
        render_menu()
        selected = input("\n선택: ").strip()
        if selected.lower() in ("q", "quit", "exit", "0"):
            print_status_line("종료합니다.", "dim")
            return
        choice = module_for_choice(selected)
        if not choice:
            print_status_line("선택을 찾을 수 없습니다. 번호 또는 선택어를 입력하세요.", "red")
            continue
        title, module_name = choice
        print_markdown_result("선택됨", f"**{title}** 실행", border_style="cyan")
        dispatch(module_name)
        return


if __name__ == "__main__":
    main()
