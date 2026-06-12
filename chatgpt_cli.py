from __future__ import annotations

import os
import traceback
from datetime import datetime
from queue import Empty, Queue
from pathlib import Path
from threading import Lock, Thread
from typing import Any

from env_common import load_project_env
from ui_common import console, print_markdown_result, print_status_line, rich_enabled


EXIT_INPUTS = {"q", "0", "quit", "exit", "/q", "/quit", "/exit", "종료", "종료하기", "/종료", "/종료하기"}


def load_chat_runtime() -> dict[str, Any]:
    try:
        from app_closed import get_default_model
        from chat_cli import (
            ChatAgentCache,
            ChatState,
            handle_scan_root_command,
            load_prompt,
            read_paste,
            run_chat_interactive,
            save_last_prompt,
        )
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
        "handle_scan_root_command": handle_scan_root_command,
        "last_error_path": None,
    }


def print_chatgpt_banner(state: Any) -> None:
    print_chat_shell_header(state)
    print_markdown_result(
        "사용 방법",
        "\n".join(
            [
                "# 프롬프트 작성",
                "",
                "- 짧은 질문은 바로 입력하세요.",
                "- 긴 프롬프트는 `p`를 누르고 여러 줄로 붙여넣으세요.",
                "- 답변 생성 중에 새 프롬프트를 입력하면 대기열에 들어가고 순서대로 실행됩니다.",
                "- `scan` 또는 `scan <폴더>`를 입력하면 Root 기준으로 파일을 스캔해 컨텍스트에 붙입니다.",
                "- 마지막 답변에 사용한 프롬프트는 `s`로 저장할 수 있습니다.",
                "- 종료는 `q`, `0`, `종료하기` 중 하나를 입력하세요.",
            ]
        ),
        border_style="cyan",
    )


def print_chat_shell_header(state: Any) -> None:
    if rich_enabled():
        from rich.panel import Panel
        from rich.table import Table

        table = Table.grid(expand=True)
        table.add_column(ratio=1)
        table.add_column(ratio=1)
        table.add_row("[bold]DeepAgent Chat[/bold]", f"[cyan]{state.model_name}[/cyan]")
        table.add_row("[dim]ChatGPT/Codex 스타일 터미널 챗봇[/dim]", f"Multi Agent: {'ON' if state.enable_multi_agent else 'OFF'}")
        table.add_row("[dim]Root Workspace[/dim]", str(state.workspace_dir))
        console.print(Panel(table, border_style="cyan", padding=(1, 2)))
        return

    print("")
    print("=" * 78)
    print("DeepAgent Chat - ChatGPT/Codex 스타일 터미널 챗봇")
    print(f"Model       : {state.model_name}")
    print(f"Workspace   : {state.workspace_dir}")
    print(f"Multi Agent : {'ON' if state.enable_multi_agent else 'OFF'}")
    print("=" * 78)


def print_command_bar(runner: "PromptQueueRunner") -> None:
    status = f"실행 중 · 대기 {runner.queue_size()}개" if runner.is_busy() else "대기 중"
    commands = "1 질문 | p 긴 프롬프트 | scan Root 스캔 | l 불러오기 | s 저장 | r 대기열 | x 비우기 | e 에러 | h 도움말 | q 종료"
    if rich_enabled():
        from rich.panel import Panel

        border_style = "yellow" if runner.is_busy() else "cyan"
        body = f"[bold]{status}[/bold]\n[dim]{commands}[/dim]"
        console.print(Panel(body, title="Chat Controls", border_style=border_style, padding=(0, 1), expand=False))
        return

    print("")
    print(f"[{status}]")
    print(commands)


def print_user_bubble(prompt: str, *, queued: bool) -> None:
    preview = prompt.strip()
    if len(preview) > 800:
        preview = preview[:800].rstrip() + "\n..."
    title = "사용자 프롬프트 · 대기열 추가" if queued else "사용자 프롬프트"
    if rich_enabled():
        from rich.panel import Panel

        console.print(Panel(preview, title=title, border_style="blue", padding=(1, 2), expand=False))
        return

    print("")
    print(f"{title}>")
    print("-" * 78)
    print(preview)
    print("-" * 78)


def chat_error_dir() -> Path:
    return Path(os.getenv("CHAT_ERROR_DIR", "chat_errors")).resolve()


def save_chat_error(exc: Exception, prompt: str, state: Any) -> Path:
    root = chat_error_dir()
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-chat-error.md"
    content = "\n".join(
        [
            "# DeepAgent Chat Error",
            "",
            f"- Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"- Model: {getattr(state, 'model_name', '')}",
            f"- Workspace: {getattr(state, 'workspace_dir', '')}",
            f"- Multi Agent: {getattr(state, 'enable_multi_agent', '')}",
            "",
            "## Prompt",
            "",
            "```text",
            prompt,
            "```",
            "",
            "## Error",
            "",
            "```text",
            str(exc),
            "```",
            "",
            "## Traceback",
            "",
            "```text",
            traceback.format_exc(),
            "```",
            "",
        ]
    )
    path.write_text(content, encoding="utf-8")
    return path


def show_last_error() -> None:
    root = chat_error_dir()
    logs = sorted(root.glob("*-chat-error.md")) if root.exists() else []
    if not logs:
        print_status_line("저장된 챗봇 에러 로그가 없습니다.", "yellow")
        return
    path = logs[-1]
    print_markdown_result(f"Last Chat Error - {path.name}", path.read_text(encoding="utf-8"), border_style="red")


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
                error_path = getattr(exc, "chat_error_path", None) or save_chat_error(exc, prompt, self.state)
                self.runtime["last_error_path"] = error_path
                print_status_line(f"실행 실패: {exc}", "red")
                print_status_line(f"에러 로그 저장: {error_path}", "yellow")
                print_status_line("마지막 에러를 보려면 `e` 또는 `/last-error`를 입력하세요.", "yellow")
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
    print_command_bar(runner)
    prompt_label = "대기열 입력> " if runner.is_busy() else "메시지 입력> "
    return input(prompt_label).strip()


def load_prompt_interactive(runtime: dict[str, Any]) -> str:
    name = input("불러올 프롬프트 이름: ").strip()
    return runtime["load_prompt"](name)


def save_prompt_interactive(state: Any, runtime: dict[str, Any]) -> None:
    name = input("저장할 프롬프트 이름: ").strip()
    runtime["save_last_prompt"](state, name)


def main() -> None:
    load_project_env()
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
        if choice.lower() in ("e", "/last-error", "last-error", "에러"):
            show_last_error()
            continue
        if choice.lower() == "s":
            save_prompt_interactive(state, runtime)
            continue
        if choice.lower() == "scan" or choice.lower().startswith("scan "):
            _, _, scan_path = choice.partition(" ")
            runtime["handle_scan_root_command"](state, scan_path.strip())
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
        print_user_bubble(prompt, queued=runner.is_busy())
        runner.submit(prompt)


if __name__ == "__main__":
    main()
