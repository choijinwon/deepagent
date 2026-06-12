from __future__ import annotations

import os
from queue import Empty, Queue
from pathlib import Path
from threading import Lock, Thread
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
                "- 답변 생성 중에 새 프롬프트를 입력하면 대기열에 들어가고 순서대로 실행됩니다.",
                "- 마지막 답변에 사용한 프롬프트는 `s`로 저장할 수 있습니다.",
                "- 종료는 `q`, `0`, `종료하기` 중 하나를 입력하세요.",
            ]
        ),
        border_style="cyan",
    )


class PromptQueueRunner:
    def __init__(self, cache: Any, state: Any, runtime: dict[str, Any]) -> None:
        self.cache = cache
        self.state = state
        self.runtime = runtime
        self.queue: Queue[str] = Queue()
        self.lock = Lock()
        self.worker: Thread | None = None
        self.running = False

    def is_busy(self) -> bool:
        with self.lock:
            return self.running or not self.queue.empty()

    def queue_size(self) -> int:
        return self.queue.qsize()

    def submit(self, prompt: str) -> None:
        was_busy = self.is_busy()
        self.queue.put(prompt)
        if was_busy:
            print_status_line(f"대기열에 추가했습니다. 남은 프롬프트: {self.queue.qsize()}", "cyan")
        else:
            print_status_line("프롬프트 실행을 시작합니다.", "cyan")
        self.start_worker()

    def start_worker(self) -> None:
        with self.lock:
            if self.worker and self.worker.is_alive():
                return
            self.running = True
            self.worker = Thread(target=self.run_loop, name="deepagent-prompt-queue")
            self.worker.start()

    def run_loop(self) -> None:
        while True:
            try:
                prompt = self.queue.get_nowait()
            except Empty:
                with self.lock:
                    self.running = False
                print_status_line("대기열 실행이 모두 끝났습니다.", "green")
                return

            remaining = self.queue.qsize()
            print_status_line(f"대기열 프롬프트 실행 중... 남은 대기: {remaining}", "cyan")
            try:
                self.runtime["run_chat_interactive"](self.cache, self.state, prompt)
            except Exception as exc:
                print_status_line(f"실행 실패: {exc}", "red")
            finally:
                self.queue.task_done()

    def clear_pending(self) -> int:
        with self.queue.mutex:
            count = len(self.queue.queue)
            self.queue.queue.clear()
            self.queue.unfinished_tasks = max(0, self.queue.unfinished_tasks - count)
            self.queue.all_tasks_done.notify_all()
            return count

    def wait_until_finished(self) -> None:
        worker = self.worker
        if worker and worker.is_alive():
            worker.join()


def prompt_menu(runner: PromptQueueRunner) -> str:
    print("")
    if runner.is_busy():
        print(f"[실행 중] 새 프롬프트는 대기열에 추가됩니다. 대기: {runner.queue_size()}")
    print("1. 바로 질문 입력")
    print("p. 긴 프롬프트 붙여넣기")
    print("l. 저장 프롬프트 불러와 실행")
    print("s. 마지막 프롬프트 저장")
    print("r. 대기열 상태 보기")
    print("x. 대기열 비우기")
    print("c. 대화 초기화")
    print("h. 도움말")
    print("0. 종료하기")
    print("q. 종료하기")
    return input("선택 또는 바로 질문 입력> ").strip()


def load_prompt_interactive(runtime: dict[str, Any]) -> str:
    name = input("불러올 프롬프트 이름: ").strip()
    return runtime["load_prompt"](name)


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
    runner = PromptQueueRunner(cache, state, runtime)
    print_chatgpt_banner(state)

    while True:
        choice = prompt_menu(runner)
        if not choice:
            continue
        if choice.lower() in EXIT_INPUTS:
            cleared = runner.clear_pending()
            if runner.is_busy():
                print_status_line(
                    f"종료 요청을 받았습니다. 대기열 {cleared}개를 비우고 현재 실행이 끝날 때까지 기다립니다.",
                    "yellow",
                )
                runner.wait_until_finished()
            print_status_line("종료합니다.", "dim")
            return
        if choice.lower() == "h":
            print_chatgpt_banner(state)
            continue
        if choice.lower() == "c":
            if runner.is_busy():
                print_status_line("실행 중에는 대화 초기화를 잠시 보류하세요. 현재 실행이 끝난 뒤 다시 시도하세요.", "yellow")
                continue
            state.messages.clear()
            print_status_line("대화를 초기화했습니다.", "green")
            continue
        if choice.lower() == "r":
            status = "실행 중" if runner.is_busy() else "대기 없음"
            print_status_line(f"대기열 상태: {status}, 남은 프롬프트 {runner.queue_size()}개", "cyan")
            continue
        if choice.lower() == "x":
            cleared = runner.clear_pending()
            print_status_line(f"대기 중인 프롬프트 {cleared}개를 비웠습니다.", "yellow")
            continue
        if choice.lower() == "s":
            save_prompt_interactive(state, runtime)
            continue
        if choice.lower() == "l":
            prompt = load_prompt_interactive(runtime)
            if prompt:
                runner.submit(prompt)
            continue
        if choice.lower() == "p":
            prompt = runtime["read_paste"]()
        elif choice == "1":
            prompt = input("프롬프트> ").strip()
        else:
            prompt = choice
        if not prompt:
            continue
        runner.submit(prompt)


if __name__ == "__main__":
    main()
