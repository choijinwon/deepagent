import os
import textwrap
from dataclasses import dataclass, field

from app_closed import (
    build_agent,
    get_available_models,
    get_default_model,
    get_harness_skill_files,
    get_harness_skill_names,
    harness_skills_enabled,
)
from web_closed import format_agent_result, load_prompt_store, save_prompt_store, save_wiki_record


HELP_TEXT = """
Commands
  /help                 Show commands
  /status               Show model and runtime status
  /model                List registered models
  /model <name>         Switch model
  /multi on|off         Toggle multi-agent mode
  /skills on|off        Toggle harness skills for this session
  /prompts              List saved prompts
  /load <name>          Load a saved prompt into chat
  /save <name>          Save the last user prompt
  /clear                Clear chat memory
  /test                 Test selected model connection
  /exit                 Quit

Input
  Type a message and press Enter to send.
  For multi-line input, type /paste, enter lines, then finish with a single dot (.).
"""


@dataclass
class ChatState:
    model_name: str
    enable_multi_agent: bool
    messages: list[dict[str, str]] = field(default_factory=list)
    last_user_prompt: str = ""


class ChatAgentCache:
    def __init__(self) -> None:
        self._agents = {}

    def get(self, state: ChatState):
        cache_key = (state.model_name, state.enable_multi_agent, harness_skills_enabled())
        if cache_key not in self._agents:
            self._agents[cache_key] = build_agent(
                model_name=state.model_name,
                enable_multi_agent=state.enable_multi_agent,
            )
        return self._agents[cache_key]


def print_banner(state: ChatState) -> None:
    print("")
    print("=" * 78)
    print(" DeepAgents Chat CLI - Qwen/vLLM Closed Network")
    print("=" * 78)
    print("Type /help for commands. Type /exit to quit.")
    print_status(state)


def print_status(state: ChatState) -> None:
    print("-" * 78)
    print(f"Model          : {state.model_name}")
    print(f"Multi Agent    : {'ON' if state.enable_multi_agent else 'OFF'}")
    print(f"Harness Skills : {'ON' if harness_skills_enabled() else 'OFF'}")
    print(f"Skill List     : {', '.join(get_harness_skill_names()) or 'none'}")
    print(f"Turns          : {len([m for m in state.messages if m['role'] == 'user'])}")
    print("-" * 78)


def read_paste() -> str:
    print("Paste multi-line prompt. Finish with a single dot (.) on its own line.")
    lines = []
    while True:
        line = input()
        if line == ".":
            break
        lines.append(line)
    return "\n".join(lines).strip()


def wrap_print(text: str) -> None:
    print("")
    print("assistant>")
    print("-" * 78)
    for paragraph in str(text).splitlines():
        if not paragraph:
            print("")
            continue
        print(textwrap.fill(paragraph, width=100, replace_whitespace=False))
    print("-" * 78)


def invoke_chat(cache: ChatAgentCache, state: ChatState, prompt: str) -> str:
    state.messages.append({"role": "user", "content": prompt})
    state.last_user_prompt = prompt

    agent = cache.get(state)
    response = agent.invoke(
        {
            "messages": state.messages,
            "files": get_harness_skill_files(),
        }
    )
    result = format_agent_result(response)
    state.messages.append({"role": "assistant", "content": result})

    save_wiki_record(
        prompt=prompt,
        result=result,
        model_name=state.model_name,
        enable_multi_agent=state.enable_multi_agent,
    )
    return result


def handle_model_command(state: ChatState, args: str) -> None:
    models = get_available_models()
    if not args:
        print("Registered models:")
        for model in models:
            marker = "*" if model == state.model_name else " "
            print(f" {marker} {model}")
        return

    if args not in models:
        print(f"Unknown model: {args}")
        print(f"Available: {', '.join(models)}")
        return

    state.model_name = args
    state.messages.clear()
    print(f"Model switched to {state.model_name}. Chat memory cleared.")


def handle_multi_command(state: ChatState, args: str) -> None:
    if args not in ("on", "off"):
        print("Usage: /multi on|off")
        return
    state.enable_multi_agent = args == "on"
    print(f"Multi Agent: {'ON' if state.enable_multi_agent else 'OFF'}")


def handle_skills_command(args: str) -> None:
    if args not in ("on", "off"):
        print("Usage: /skills on|off")
        return
    os.environ["ENABLE_HARNESS_SKILLS"] = "true" if args == "on" else "false"
    print(f"Harness Skills: {'ON' if args == 'on' else 'OFF'}")


def list_prompts() -> None:
    prompts = load_prompt_store()
    if not prompts:
        print("No saved prompts.")
        return
    for item in prompts:
        print(f"- {item['name']}")


def load_prompt(name: str) -> str | None:
    if not name:
        print("Usage: /load <name>")
        return None
    for item in load_prompt_store():
        if item["name"] == name:
            return item["content"]
    print(f"Saved prompt not found: {name}")
    return None


def save_last_prompt(state: ChatState, name: str) -> None:
    if not name:
        print("Usage: /save <name>")
        return
    if not state.last_user_prompt:
        print("No last user prompt to save.")
        return
    prompts = [item for item in load_prompt_store() if item["name"] != name]
    prompts.append({"name": name, "content": state.last_user_prompt})
    save_prompt_store(prompts)
    print(f"Saved prompt: {name}")


def test_model(cache: ChatAgentCache, state: ChatState) -> None:
    previous_multi_agent = state.enable_multi_agent
    previous_messages = list(state.messages)
    state.enable_multi_agent = False
    state.messages = []
    try:
        result = invoke_chat(cache, state, "연결 테스트입니다. 'OK'와 현재 사용 모델명을 짧게 답하세요.")
        wrap_print(result)
    except Exception as exc:
        print(f"Model test failed: {exc}")
    finally:
        state.enable_multi_agent = previous_multi_agent
        state.messages = previous_messages


def handle_command(command: str, cache: ChatAgentCache, state: ChatState) -> bool:
    name, _, args = command.partition(" ")
    name = name.lower()
    args = args.strip()

    if name in ("/exit", "/quit"):
        return False
    if name == "/help":
        print(HELP_TEXT)
    elif name == "/status":
        print_status(state)
    elif name == "/model":
        handle_model_command(state, args)
    elif name == "/multi":
        handle_multi_command(state, args.lower())
    elif name == "/skills":
        handle_skills_command(args.lower())
    elif name == "/prompts":
        list_prompts()
    elif name == "/load":
        prompt = load_prompt(args)
        if prompt:
            print("Loaded prompt. Sending...")
            try:
                wrap_print(invoke_chat(cache, state, prompt))
            except Exception as exc:
                print(f"Run failed: {exc}")
    elif name == "/save":
        save_last_prompt(state, args)
    elif name == "/clear":
        state.messages.clear()
        print("Chat memory cleared.")
    elif name == "/test":
        test_model(cache, state)
    elif name == "/paste":
        prompt = read_paste()
        if prompt:
            try:
                wrap_print(invoke_chat(cache, state, prompt))
            except Exception as exc:
                print(f"Run failed: {exc}")
    else:
        print(f"Unknown command: {name}. Type /help.")
    return True


def main() -> None:
    state = ChatState(
        model_name=get_default_model(),
        enable_multi_agent=os.getenv("ENABLE_MULTI_AGENT", "true").lower() in ("1", "true", "yes", "y"),
    )
    cache = ChatAgentCache()
    print_banner(state)

    while True:
        try:
            user_input = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if not user_input:
            continue

        if user_input.startswith("/"):
            if not handle_command(user_input, cache, state):
                print("Exiting.")
                break
            continue

        try:
            wrap_print(invoke_chat(cache, state, user_input))
        except Exception as exc:
            print(f"Run failed: {exc}")


if __name__ == "__main__":
    main()
