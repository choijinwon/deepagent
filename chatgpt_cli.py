from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from ui_common import print_key_value_table, print_markdown_result, print_status_line


EXIT_INPUTS = {"q", "0", "quit", "exit", "/q", "/quit", "/exit", "종료", "종료하기", "/종료", "/종료하기"}


def load_chat_runtime() -> dict[str, Any]:
    try:
        from app_closed import get_default_model
        from chat_cli import ChatAgentCache, ChatState, load_prompt, read_paste, run_chat_interactive, save_last_prompt
    except ModuleNotFoundError as exc:
        print_status_line("필수 패키지를 찾을 수 없습니다.", "red")
        print(f"누락 모듈: {exc.name}")
        print("")
        print("폐쇄망 PC에서는 아래 순서로 먼저 설치를 확인하세요.")
        print("1. .venv\\Scripts\\activate")
        print("2. .\\scripts\\install_offline.ps1")
        print("3. deepagent-doctor")
        raise SystemExit(1) from exc

    return {
        "ChatAgentCache": ChatAgentCache,
        "ChatState": ChatState,
        "get_default_model": get_default_model,
        "load_prompt": load_prompt,
        "read_paste": read_paste,
        "run_chat_interactive": run_chat_interactive,
        "save_last_prompt": save_last_prompt,
    }


def print_chatgpt_banner(state: Any) -> None:
    print_status_line("DeepAgent ChatGPT/Codex 스타일 채팅", "bold cyan")
    print_key_value_table(
        "현재 설정",
        [
            ("Model", state.model_name),
            ("Workspace", str(state.workspace_dir)),
            ("Multi Agent", "ON" if state.enable_multi_agent else "OFF"),
        ],
    )
    print_markdown_result(
        "사용 방법",
        "\n".join(
            [
                "# 프롬프트 작성",
                "",
                "- 짧은 질문은 바로 입력하세요.",
                "- 긴 프롬프트는 `p`를 누르고 여러 줄로 붙여넣으세요.",
                "- 마지막 답변에 사용한 프롬프트는 `s`로 저장할 수 있습니다.",
                "- 종료는 `q`, `0`, `종료하기` 중 하나를 입력하세요.",
            ]
        ),
        border_style="cyan",
    )


def prompt_menu() -> str:
    print("")
    print("1. 바로 질문 입력")
    print("p. 긴 프롬프트 붙여넣기")
    print("l. 저장 프롬프트 불러와 실행")
    print("s. 마지막 프롬프트 저장")
    print("c. 대화 초기화")
    print("h. 도움말")
    print("0. 종료하기")
    print("q. 종료하기")
    return input("선택 또는 바로 질문 입력> ").strip()


def run_loaded_prompt(cache: Any, state: Any, runtime: dict[str, Any]) -> None:
    name = input("불러올 프롬프트 이름: ").strip()
    prompt = runtime["load_prompt"](name)
    if prompt:
        runtime["run_chat_interactive"](cache, state, prompt)


def save_prompt_interactive(state: Any, runtime: dict[str, Any]) -> None:
    name = input("저장할 프롬프트 이름: ").strip()
    runtime["save_last_prompt"](state, name)


def main() -> None:
    load_dotenv()
    runtime = load_chat_runtime()
    state = runtime["ChatState"](
        model_name=runtime["get_default_model"](),
        enable_multi_agent=os.getenv("ENABLE_MULTI_AGENT", "true").lower() in ("1", "true", "yes", "y"),
        workspace_dir=Path(os.getenv("CHAT_WORKSPACE_DIR", "agent_workspace")).resolve(),
        plan_dir=Path(os.getenv("PLAN_DIR", "plans")).resolve(),
        goal_dir=Path(os.getenv("GOAL_DIR", "goals")).resolve(),
    )
    cache = runtime["ChatAgentCache"]()
    print_chatgpt_banner(state)

    while True:
        choice = prompt_menu()
        if not choice:
            continue
        if choice.lower() in EXIT_INPUTS:
            print_status_line("종료합니다.", "dim")
            return
        if choice.lower() == "h":
            print_chatgpt_banner(state)
            continue
        if choice.lower() == "c":
            state.messages.clear()
            print_status_line("대화를 초기화했습니다.", "green")
            continue
        if choice.lower() == "s":
            save_prompt_interactive(state, runtime)
            continue
        if choice.lower() == "l":
            run_loaded_prompt(cache, state, runtime)
            continue
        if choice.lower() == "p":
            prompt = runtime["read_paste"]()
        elif choice == "1":
            prompt = input("프롬프트> ").strip()
        else:
            prompt = choice
        if not prompt:
            continue
        try:
            runtime["run_chat_interactive"](cache, state, prompt)
        except Exception as exc:
            print_status_line(f"실행 실패: {exc}", "red")


if __name__ == "__main__":
    main()
