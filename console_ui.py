import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from autofix_common import analyze_log_text, render_fix_report, save_fix_report
from app_closed import (
    build_agent,
    get_available_models,
    get_default_model,
    get_harness_skill_files,
    get_harness_skill_names,
    harness_skills_enabled,
)
from dev_common import (
    DevPatchCandidate,
    DevSession,
    apply_patch_candidates,
    generate_patch_candidates,
    list_dev_sessions,
    load_dev_session,
    render_dev_run_markdown,
    render_patch_candidates,
    run_development_command,
    save_dev_run,
    save_dev_session,
    save_patch_candidates,
    suggest_development_commands,
)
from fix_wizard import run_fix_wizard, render_wizard_result
from ops_common import session_dir
from project_wizard import run_project_wizard
from registration_wizard import run_registration_wizard
from scaffold_common import apply_scaffold, parse_scaffold_text, render_scaffold_summary
from web_closed import invoke_agent_text, load_prompt_store, save_prompt_store, save_wiki_record
from ui_common import MarkdownStream, print_key_value_table, print_markdown_result, print_status_line


DEFAULT_PROMPT = "서버 접근권한 보안 점검 TODO 만들어줘."


@dataclass
class ConsoleState:
    model_name: str
    enable_multi_agent: bool = True
    prompt: str = DEFAULT_PROMPT
    workspace_dir: Path = Path("agent_workspace")
    plan_dir: Path = Path("plans")
    last_dev_command: str = ""
    last_dev_log_path: Path | None = None
    last_dev_fix_path: Path | None = None
    last_dev_patch_path: Path | None = None
    last_dev_patch_candidates: list[DevPatchCandidate] = field(default_factory=list)


class ConsoleAgentCache:
    def __init__(self) -> None:
        self._agents = {}

    def get(self, state: ConsoleState):
        cache_key = (state.model_name, state.enable_multi_agent, harness_skills_enabled())
        if cache_key not in self._agents:
            self._agents[cache_key] = build_agent(
                model_name=state.model_name,
                enable_multi_agent=state.enable_multi_agent,
            )
        return self._agents[cache_key]


def print_header(state: ConsoleState) -> None:
    print("")
    print_status_line("DeepAgents Qwen/vLLM Closed Network Console UI", "bold cyan")
    print_key_value_table(
        "Runtime",
        [
            ("Model", state.model_name),
            ("Multi Agent", "ON" if state.enable_multi_agent else "OFF"),
            ("Harness Skills", "ON" if harness_skills_enabled() else "OFF"),
            ("Skill List", ", ".join(get_harness_skill_names()) or "none"),
            ("Workspace", str(state.workspace_dir)),
        ],
    )


def choose_model(state: ConsoleState) -> None:
    models = get_available_models()
    print("")
    print("등록 모델")
    for index, model in enumerate(models, start=1):
        print(f"{index}. {model}")

    selected = input("선택 번호: ").strip()
    if not selected.isdigit():
        print("숫자를 입력하세요.")
        return

    index = int(selected)
    if index < 1 or index > len(models):
        print("범위를 벗어난 번호입니다.")
        return

    state.model_name = models[index - 1]
    print(f"모델 변경: {state.model_name}")


def edit_prompt(state: ConsoleState) -> None:
    print("")
    print("프롬프트를 입력하세요. 빈 줄만 입력하면 종료합니다.")
    print("-" * 72)
    lines = []
    while True:
        line = input()
        if not line:
            break
        lines.append(line)

    if lines:
        state.prompt = "\n".join(lines)
        print("프롬프트가 변경되었습니다.")
    else:
        print("변경하지 않았습니다.")


def read_dot_paste() -> str:
    print_status_line("내용을 붙여넣고 마지막 줄에 점 하나(.)만 입력하세요.", "cyan")
    lines = []
    while True:
        line = input()
        if line == ".":
            break
        lines.append(line)
    return "\n".join(lines).strip()


def show_prompt(state: ConsoleState) -> None:
    print_markdown_result("현재 프롬프트", state.prompt, border_style="cyan")


def load_prompt(state: ConsoleState) -> None:
    prompts = load_prompt_store()
    if not prompts:
        print("저장된 프롬프트가 없습니다.")
        return

    print("")
    print("저장된 프롬프트")
    for index, item in enumerate(prompts, start=1):
        print(f"{index}. {item['name']}")

    selected = input("선택 번호: ").strip()
    if not selected.isdigit():
        print("숫자를 입력하세요.")
        return

    index = int(selected)
    if index < 1 or index > len(prompts):
        print("범위를 벗어난 번호입니다.")
        return

    state.prompt = prompts[index - 1]["content"]
    print(f"프롬프트 불러옴: {prompts[index - 1]['name']}")


def save_prompt(state: ConsoleState) -> None:
    name = input("저장할 프롬프트 이름: ").strip()
    if not name:
        print("이름이 필요합니다.")
        return
    if len(name) > 80:
        print("프롬프트 이름은 80자 이하로 입력하세요.")
        return

    prompts = [item for item in load_prompt_store() if item["name"] != name]
    prompts.append({"name": name, "content": state.prompt})
    save_prompt_store(prompts)
    print(f"프롬프트 저장됨: {name}")


def delete_prompt() -> None:
    prompts = load_prompt_store()
    if not prompts:
        print("저장된 프롬프트가 없습니다.")
        return

    print("")
    print("삭제할 프롬프트")
    for index, item in enumerate(prompts, start=1):
        print(f"{index}. {item['name']}")

    selected = input("삭제 번호: ").strip()
    if not selected.isdigit():
        print("숫자를 입력하세요.")
        return

    index = int(selected)
    if index < 1 or index > len(prompts):
        print("범위를 벗어난 번호입니다.")
        return

    deleted = prompts[index - 1]["name"]
    save_prompt_store([item for item in prompts if item["name"] != deleted])
    print(f"프롬프트 삭제됨: {deleted}")


def invoke_agent(cache: ConsoleAgentCache, state: ConsoleState, prompt: str) -> str:
    agent = cache.get(state)
    request = {
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
        "files": get_harness_skill_files(),
    }
    result, streamed = invoke_agent_text(agent, request)
    return result


def invoke_agent_interactive(cache: ConsoleAgentCache, state: ConsoleState, prompt: str) -> str:
    agent = cache.get(state)
    request = {
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
        "files": get_harness_skill_files(),
    }
    stream_view = MarkdownStream("실행 결과")
    with stream_view:
        result, streamed = invoke_agent_text(
            agent,
            request,
            on_delta=stream_view.append,
            on_status=lambda message: print_status_line(f"[status] {message}"),
        )
    if not streamed:
        print_markdown_result("실행 결과", result)
    return result


def run_prompt(cache: ConsoleAgentCache, state: ConsoleState) -> None:
    if not state.prompt.strip():
        print("프롬프트가 비어 있습니다.")
        return

    print_status_line("실행 중입니다. Qwen/vLLM 응답을 기다립니다...")
    try:
        result = invoke_agent_interactive(cache, state, state.prompt)
        wiki_path = save_wiki_record(
            prompt=state.prompt,
            result=result,
            model_name=state.model_name,
            enable_multi_agent=state.enable_multi_agent,
        )
        print_status_line(f"위키 기록 저장: {wiki_path}", "green")
    except Exception as exc:
        print(f"실행 실패: {exc}")


def test_model(cache: ConsoleAgentCache, state: ConsoleState) -> None:
    print("")
    print("모델 연결 테스트 중입니다...")
    previous_multi_agent = state.enable_multi_agent
    state.enable_multi_agent = False
    try:
        result = invoke_agent(cache, state, "연결 테스트입니다. 'OK'와 현재 사용 모델명을 짧게 답하세요.")
        print_markdown_result("연결 테스트 결과", result, border_style="cyan")
    except Exception as exc:
        print(f"연결 테스트 실패: {exc}")
    finally:
        state.enable_multi_agent = previous_multi_agent


def toggle_multi_agent(state: ConsoleState) -> None:
    state.enable_multi_agent = not state.enable_multi_agent
    print(f"멀티에이전트: {'ON' if state.enable_multi_agent else 'OFF'}")


def toggle_harness_skills() -> None:
    next_value = not harness_skills_enabled()
    os.environ["ENABLE_HARNESS_SKILLS"] = "true" if next_value else "false"
    print(f"하네스 스킬: {'ON' if next_value else 'OFF'}")


def run_project_console(state: ConsoleState, *, preview: bool = False) -> None:
    try:
        spec, _, result, summary = run_project_wizard(
            workspace_dir=state.workspace_dir,
            plan_dir=state.plan_dir,
            session_path=session_dir(),
            model_name=state.model_name,
            enable_multi_agent=state.enable_multi_agent,
            write_files=not preview,
        )
    except Exception as exc:
        print(f"프로젝트 생성 실패: {exc}")
        return

    print_markdown_result("프로젝트 미리보기" if preview else "프로젝트 생성", summary, border_style="cyan")
    if not preview:
        print_status_line(f"프로젝트 생성 완료: {spec.name}", "green")
        if result.summary_path:
            print_status_line(f"요약 파일: {result.summary_path}", "green")


def run_scaffold_console(state: ConsoleState, *, preview: bool = False) -> None:
    text = read_dot_paste()
    if not text:
        print("입력 내용이 비어 있습니다.")
        return
    try:
        spec = parse_scaffold_text(text)
        result = apply_scaffold(
            spec,
            state.workspace_dir,
            plan_dir=state.plan_dir,
            session_dir=session_dir(),
            model_name=state.model_name,
            enable_multi_agent=state.enable_multi_agent,
            write_files=not preview,
        )
    except Exception as exc:
        print(f"작업 생성 실패: {exc}")
        return

    print_markdown_result("작업 생성 미리보기" if preview else "작업 생성", render_scaffold_summary(spec, result), border_style="cyan")
    if not preview and result.summary_path:
        print_status_line(f"요약 파일: {result.summary_path}", "green")


def dev_session_name(command: str) -> str:
    head = command.strip().split()[0] if command.strip() else "command"
    return f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{head}"


def save_console_dev_session(state: ConsoleState, *, status: str, exit_code: int | None = None) -> None:
    if not state.last_dev_command:
        return
    save_dev_session(
        DevSession(
            name=dev_session_name(state.last_dev_command),
            command=state.last_dev_command,
            cwd=state.workspace_dir,
            log_path=state.last_dev_log_path,
            fix_path=state.last_dev_fix_path,
            patch_path=state.last_dev_patch_path,
            exit_code=exit_code,
            status=status,
        )
    )


def update_console_patch_candidates(state: ConsoleState, report: dict, source_name: str) -> None:
    candidates = generate_patch_candidates(report, state.workspace_dir)
    patch_path = save_patch_candidates(candidates, source_name)
    state.last_dev_patch_candidates = candidates
    state.last_dev_patch_path = patch_path


def choose_dev_command(state: ConsoleState) -> str:
    suggestions = suggest_development_commands(state.workspace_dir)
    print("")
    print("실행할 개발 명령")
    if suggestions:
        for index, item in enumerate(suggestions, start=1):
            print(f"{index}. {item['label']}: {item['command']}")
    print("0. 직접 입력")
    selected = input("선택 번호: ").strip()
    if selected == "0" or not selected:
        return input("실행 명령: ").strip()
    if not selected.isdigit():
        print("숫자를 입력하세요.")
        return ""
    index = int(selected)
    if index < 1 or index > len(suggestions):
        print("범위를 벗어난 번호입니다.")
        return ""
    return suggestions[index - 1]["command"]


def run_dev_console(state: ConsoleState, *, analyze_failure: bool = False) -> None:
    command = choose_dev_command(state)
    if not command:
        return
    print_status_line(f"[dev] 실행: {command}", "cyan")
    result = run_development_command(command, state.workspace_dir)
    log_path = save_dev_run(result)
    state.last_dev_command = command
    state.last_dev_log_path = log_path
    print_markdown_result("Dev Run", render_dev_run_markdown(result), border_style="green" if result.exit_code == 0 else "red")
    print_status_line(f"실행 로그 저장: {log_path}", "green" if result.exit_code == 0 else "yellow")

    if analyze_failure or result.exit_code != 0:
        report = analyze_log_text(render_dev_run_markdown(result), source_name=log_path.name)
        fix_path = save_fix_report(report)
        state.last_dev_fix_path = fix_path
        update_console_patch_candidates(state, report, log_path.name)
        print_markdown_result("Auto Fix Plan", render_fix_report(report), border_style="yellow")
        print_markdown_result("Patch Candidates", render_patch_candidates(state.last_dev_patch_candidates), border_style="yellow")
        print_status_line(f"수정 리포트 저장: {fix_path}", "green")
        if state.last_dev_patch_path:
            print_status_line(f"패치 후보 저장: {state.last_dev_patch_path}", "green")

    save_console_dev_session(state, status="passed" if result.exit_code == 0 else "fix-plan", exit_code=result.exit_code)


def apply_dev_patch_console(state: ConsoleState) -> None:
    if not state.last_dev_patch_candidates:
        print("적용할 패치 후보가 없습니다. 먼저 개발 실행/오류 분석을 실행하세요.")
        return
    print_markdown_result("Patch Candidates", render_patch_candidates(state.last_dev_patch_candidates), border_style="yellow")
    answer = input("위 패치를 적용하려면 YES 입력: ").strip()
    if answer != "YES":
        print("패치 적용을 취소했습니다.")
        return
    try:
        applied = apply_patch_candidates(state.last_dev_patch_candidates)
    except Exception as exc:
        print(f"패치 적용 실패: {exc}")
        return
    save_console_dev_session(state, status="patched")
    print("적용된 파일")
    for path in applied:
        print(f"- {path}")


def retest_dev_console(state: ConsoleState) -> None:
    if not state.last_dev_command:
        try:
            session = load_dev_session("latest")
        except FileNotFoundError:
            print("재실행할 개발 명령이 없습니다.")
            return
        state.workspace_dir = session.cwd
        state.last_dev_command = session.command
    print_status_line(f"[dev] 재테스트: {state.last_dev_command}", "cyan")
    result = run_development_command(state.last_dev_command, state.workspace_dir)
    log_path = save_dev_run(result)
    state.last_dev_log_path = log_path
    print_markdown_result("Dev Retest", render_dev_run_markdown(result), border_style="green" if result.exit_code == 0 else "red")
    save_console_dev_session(state, status="passed" if result.exit_code == 0 else "failed", exit_code=result.exit_code)


def recover_dev_console(state: ConsoleState) -> None:
    names = list_dev_sessions()
    print("")
    print("개발 세션")
    print("0. latest")
    for index, name in enumerate(names, start=1):
        print(f"{index}. {name}")
    selected = input("복구할 세션 번호: ").strip() or "0"
    if selected == "0":
        name = "latest"
    elif selected.isdigit() and 1 <= int(selected) <= len(names):
        name = names[int(selected) - 1]
    else:
        print("범위를 벗어난 번호입니다.")
        return
    try:
        session = load_dev_session(name)
    except FileNotFoundError as exc:
        print(f"개발 세션을 찾지 못했습니다: {exc}")
        return
    state.workspace_dir = session.cwd
    state.last_dev_command = session.command
    state.last_dev_log_path = session.log_path
    state.last_dev_fix_path = session.fix_path
    state.last_dev_patch_path = session.patch_path
    print(f"복구 완료: {session.name}")
    print(f"작업 폴더: {state.workspace_dir}")
    print(f"최근 명령: {state.last_dev_command}")


def run_registration_wizard_console() -> None:
    try:
        profile, _, summary = run_registration_wizard(write_files=True, create_package=True)
    except Exception as exc:
        print(f"등록 위자드 실패: {exc}")
        return
    print_markdown_result("AI Studio 등록 위자드", summary, border_style="cyan")
    print_status_line(f"등록 위자드 완료: {profile.get('project_name')}", "green")


def run_fix_wizard_console() -> None:
    try:
        report, fix_path, patch_path = run_fix_wizard()
    except Exception as exc:
        print(f"오류수정 위자드 실패: {exc}")
        return
    print_markdown_result("Auto Fix Plan", render_fix_report(report), border_style="yellow")
    print_markdown_result("Patch Candidates", patch_path.read_text(encoding="utf-8"), border_style="yellow")
    print_markdown_result("AI Studio 오류수정 위자드", render_wizard_result(report, fix_path, patch_path), border_style="cyan")


def wait_enter() -> None:
    input("\n계속하려면 Enter를 누르세요.")


def main() -> None:
    state = ConsoleState(
        model_name=get_default_model(),
        enable_multi_agent=os.getenv("ENABLE_MULTI_AGENT", "true").lower() in ("1", "true", "yes", "y"),
        workspace_dir=Path(os.getenv("CHAT_WORKSPACE_DIR", "agent_workspace")).resolve(),
        plan_dir=Path(os.getenv("PLAN_DIR", "plans")).resolve(),
    )
    cache = ConsoleAgentCache()

    while True:
        print_header(state)
        print("1. 모델 선택")
        print("2. 프롬프트 입력/수정")
        print("3. 현재 프롬프트 보기")
        print("4. 저장된 프롬프트 불러오기")
        print("5. 현재 프롬프트 저장")
        print("6. 저장된 프롬프트 삭제")
        print("7. 멀티에이전트 ON/OFF")
        print("8. 하네스 스킬 ON/OFF")
        print("9. 모델 연결 테스트")
        print("10. 실행")
        print("11. 질문형 프로젝트 생성")
        print("12. 질문형 프로젝트 미리보기")
        print("13. 아이디어 붙여넣기로 폴더/파일 생성")
        print("14. 아이디어 생성 미리보기")
        print("15. 생성 코드 실행/오류 자동 분석")
        print("16. 수정 후보 패치 승인 적용")
        print("17. 테스트 재실행")
        print("18. 개발 세션 복구")
        print("19. AI Studio 등록 위자드")
        print("20. AI Studio 오류수정 위자드")
        print("0. 종료")

        choice = input("\n선택: ").strip()
        if choice == "1":
            choose_model(state)
            wait_enter()
        elif choice == "2":
            edit_prompt(state)
            wait_enter()
        elif choice == "3":
            show_prompt(state)
            wait_enter()
        elif choice == "4":
            load_prompt(state)
            wait_enter()
        elif choice == "5":
            save_prompt(state)
            wait_enter()
        elif choice == "6":
            delete_prompt()
            wait_enter()
        elif choice == "7":
            toggle_multi_agent(state)
            wait_enter()
        elif choice == "8":
            toggle_harness_skills()
            wait_enter()
        elif choice == "9":
            test_model(cache, state)
            wait_enter()
        elif choice == "10":
            run_prompt(cache, state)
            wait_enter()
        elif choice == "11":
            run_project_console(state, preview=False)
            wait_enter()
        elif choice == "12":
            run_project_console(state, preview=True)
            wait_enter()
        elif choice == "13":
            run_scaffold_console(state, preview=False)
            wait_enter()
        elif choice == "14":
            run_scaffold_console(state, preview=True)
            wait_enter()
        elif choice == "15":
            run_dev_console(state, analyze_failure=True)
            wait_enter()
        elif choice == "16":
            apply_dev_patch_console(state)
            wait_enter()
        elif choice == "17":
            retest_dev_console(state)
            wait_enter()
        elif choice == "18":
            recover_dev_console(state)
            wait_enter()
        elif choice == "19":
            run_registration_wizard_console()
            wait_enter()
        elif choice == "20":
            run_fix_wizard_console()
            wait_enter()
        elif choice == "0":
            print("종료합니다.")
            break
        else:
            print("알 수 없는 메뉴입니다.")
            wait_enter()


if __name__ == "__main__":
    main()
