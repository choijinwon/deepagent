from __future__ import annotations

import sys

from ui_common import print_markdown_result, print_status_line, rich_enabled


MENU = [
    ("1", "chat", "ChatGPT/Codex 스타일 채팅", "deepagent-chatgpt", "chatgpt_cli"),
    ("2", "cli", "고급 챗봇형 CLI", "deepagent-chat", "chat_cli"),
    ("3", "project", "질문형 프로젝트 생성", "deepagent-project", "project_wizard"),
    ("4", "web", "웹 UI", "deepagent-web", "web_closed"),
    ("5", "console", "메뉴형 콘솔 UI", "deepagent-console", "console_ui"),
    ("6", "scaffold", "아이디어로 폴더/파일 생성", "deepagent-scaffold", "scaffold_cli"),
    ("7", "register", "AI Studio 등록 위자드", "deepagent-register-wizard", "registration_wizard"),
    ("8", "fix", "AI Studio 오류수정 위자드", "deepagent-fix-wizard", "fix_wizard"),
    ("9", "env", ".env 생성/경로 확인", "deepagent-env", "env_cli"),
    ("10", "doctor", "폐쇄망 환경 진단", "deepagent-doctor", "doctor"),
    ("11", "run", "기본 단발 실행 테스트", "deepagent-run", "app_closed"),
]

ONBOARDING = [
    (
        "1",
        "register",
        "모델 프로젝트를 AI Studio에 등록하고 싶어요",
        "registration_wizard",
        "프로젝트 분석, 점검표, MLflow/AI Studio Queue/리소스 질문, 등록 패키지 생성",
    ),
    (
        "2",
        "fix",
        "학습 Job 오류를 고치고 싶어요",
        "fix_wizard",
        "오류 로그 파일 경로를 입력하면 원인/조치/패치 후보/재검증 명령 생성",
    ),
    (
        "3",
        "env",
        "폐쇄망 Python/ML 환경을 점검하고 싶어요",
        "doctor",
        ".env 생성/경로 확인, Qwen/vLLM, 필수 패키지, 내부 API 연결 상태 진단",
    ),
    (
        "4",
        "api",
        "모델 API 연결을 테스트하고 싶어요",
        "app_closed",
        "Qwen/vLLM OpenAI 호환 API와 Tool Calling 기본 실행 테스트",
    ),
    (
        "5",
        "develop",
        "아이디어로 프로젝트를 만들고 개발하고 싶어요",
        "chatgpt_cli",
        "ChatGPT/Codex 스타일 채팅에서 아이디어를 쓰고 프로젝트 생성/수정 요청",
    ),
    (
        "6",
        "web",
        "브라우저 화면에서 사용하고 싶어요",
        "web_closed",
        "웹 UI에서 모델 선택, 등록 분석, 패키지 생성, 프롬프트/위키 관리",
    ),
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


def render_onboarding() -> None:
    if rich_enabled():
        from rich.table import Table
        from ui_common import console

        table = Table(title="처음 사용하는 분을 위한 DeepAgent 시작", show_lines=True)
        table.add_column("번호", justify="center", style="bold cyan", no_wrap=True)
        table.add_column("하고 싶은 일", style="bold green")
        table.add_column("설명")
        for number, _, title, _, description in ONBOARDING:
            table.add_row(number, title, description)
        table.add_row("m", "전체 메뉴 보기", "기존 deepagent 상세 메뉴를 봅니다.")
        table.add_row("q", "종료", "아무 작업도 실행하지 않습니다.")
        console.print(table)
        console.print("[dim]번호를 입력하세요. 잘 모르겠으면 1번을 추천합니다.[/dim]")
        return

    print("")
    print("=" * 78)
    print(" 처음 사용하는 분을 위한 DeepAgent 시작")
    print("=" * 78)
    for number, _, title, _, description in ONBOARDING:
        print(f"{number}. {title}")
        print(f"   - {description}")
    print("m. 전체 메뉴 보기")
    print("q. 종료")


def module_for_choice(value: str) -> tuple[str, str] | None:
    selected = value.strip().lower()
    if not selected:
        return None
    for number, alias, title, command, module_name in MENU:
        if selected in (number, alias, command):
            return title, module_name
    return None


def module_for_onboarding_choice(value: str) -> tuple[str, str] | None:
    selected = value.strip().lower()
    if not selected:
        return None
    for number, alias, title, module_name, _ in ONBOARDING:
        if selected in (number, alias):
            return title, module_name
    return None


def dispatch(module_name: str) -> None:
    if module_name == "chat_cli":
        from chat_cli import main
    elif module_name == "chatgpt_cli":
        from chatgpt_cli import main
    elif module_name == "web_closed":
        from web_closed import main
    elif module_name == "console_ui":
        from console_ui import main
    elif module_name == "project_wizard":
        from project_wizard import main
    elif module_name == "scaffold_cli":
        from scaffold_cli import main
    elif module_name == "registration_wizard":
        from registration_wizard import main
    elif module_name == "fix_wizard":
        from fix_wizard import main
    elif module_name == "doctor":
        from doctor import main
    elif module_name == "env_cli":
        from env_cli import main
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

    render_onboarding()
    selected = input("\n무엇을 하고 싶나요?: ").strip()
    if selected.lower() in ("q", "quit", "exit", "0"):
        print_status_line("종료합니다.", "dim")
        return
    if selected.lower() not in ("m", "menu", "전체", "전체메뉴"):
        choice = module_for_onboarding_choice(selected)
        if choice:
            title, module_name = choice
            print_markdown_result("시작", f"**{title}** 실행", border_style="cyan")
            dispatch(module_name)
            return
        print_status_line("선택을 찾을 수 없어 전체 메뉴를 표시합니다.", "yellow")

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
