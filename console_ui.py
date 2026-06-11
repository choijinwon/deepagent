import os
from dataclasses import dataclass

from app_closed import (
    build_agent,
    get_available_models,
    get_default_model,
    get_harness_skill_files,
    get_harness_skill_names,
    harness_skills_enabled,
)
from web_closed import format_agent_result, load_prompt_store, save_prompt_store, save_wiki_record


DEFAULT_PROMPT = "서버 접근권한 보안 점검 TODO 만들어줘."


@dataclass
class ConsoleState:
    model_name: str
    enable_multi_agent: bool = True
    prompt: str = DEFAULT_PROMPT


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
    print("=" * 72)
    print(" DeepAgents Qwen/vLLM Closed Network Console UI")
    print("=" * 72)
    print(f"Model           : {state.model_name}")
    print(f"Multi Agent     : {'ON' if state.enable_multi_agent else 'OFF'}")
    print(f"Harness Skills  : {'ON' if harness_skills_enabled() else 'OFF'}")
    print(f"Skill List      : {', '.join(get_harness_skill_names()) or 'none'}")
    print("-" * 72)


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


def show_prompt(state: ConsoleState) -> None:
    print("")
    print("[현재 프롬프트]")
    print("-" * 72)
    print(state.prompt)


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
    response = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            "files": get_harness_skill_files(),
        }
    )
    return format_agent_result(response)


def run_prompt(cache: ConsoleAgentCache, state: ConsoleState) -> None:
    if not state.prompt.strip():
        print("프롬프트가 비어 있습니다.")
        return

    print("")
    print("실행 중입니다. Qwen/vLLM 응답을 기다립니다...")
    try:
        result = invoke_agent(cache, state, state.prompt)
        wiki_path = save_wiki_record(
            prompt=state.prompt,
            result=result,
            model_name=state.model_name,
            enable_multi_agent=state.enable_multi_agent,
        )
        print("")
        print("[실행 결과]")
        print("-" * 72)
        print(result)
        print("-" * 72)
        print(f"위키 기록 저장: {wiki_path}")
    except Exception as exc:
        print(f"실행 실패: {exc}")


def test_model(cache: ConsoleAgentCache, state: ConsoleState) -> None:
    print("")
    print("모델 연결 테스트 중입니다...")
    previous_multi_agent = state.enable_multi_agent
    state.enable_multi_agent = False
    try:
        result = invoke_agent(cache, state, "연결 테스트입니다. 'OK'와 현재 사용 모델명을 짧게 답하세요.")
        print("[연결 테스트 결과]")
        print(result)
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


def wait_enter() -> None:
    input("\n계속하려면 Enter를 누르세요.")


def main() -> None:
    state = ConsoleState(
        model_name=get_default_model(),
        enable_multi_agent=os.getenv("ENABLE_MULTI_AGENT", "true").lower() in ("1", "true", "yes", "y"),
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
        elif choice == "0":
            print("종료합니다.")
            break
        else:
            print("알 수 없는 메뉴입니다.")
            wait_enter()


if __name__ == "__main__":
    main()
