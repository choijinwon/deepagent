import os
import textwrap
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

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
  /folder               Show current workspace folder
  /folder <path>        Set workspace folder
  /tree [depth]         Show workspace file tree
  /read <path>          Print a workspace file
  /write <path>         Write a workspace file from pasted lines
  /add-file <path>      Attach a workspace file to agent context
  /files                List attached files
  /drop-file <path|all> Remove attached file context
  /plan new <title>     Start a plan
  /plan add <step>      Add a plan step
  /plan done <number>   Mark a plan step done
  /plan show            Show current plan
  /plan save [name]     Save current plan as Markdown
  /plan load <name>     Load a saved plan
  /plan clear           Clear current plan
  /plans                List saved plans
  /exit                 Quit

Input
  Type a message and press Enter to send.
  For multi-line input, type /paste, enter lines, then finish with a single dot (.).
"""


@dataclass
class ChatState:
    model_name: str
    enable_multi_agent: bool
    workspace_dir: Path
    plan_dir: Path
    messages: list[dict[str, str]] = field(default_factory=list)
    last_user_prompt: str = ""
    attached_files: dict[str, str] = field(default_factory=dict)
    plan_title: str = ""
    plan_steps: list[dict[str, str]] = field(default_factory=list)


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
    print(f"Workspace      : {state.workspace_dir}")
    print(f"Attached Files : {len(state.attached_files)}")
    print(f"Plan           : {state.plan_title or 'none'} ({len(state.plan_steps)} steps)")
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
    files = get_harness_skill_files()
    files.update(state.attached_files)
    response = agent.invoke(
        {
            "messages": state.messages,
            "files": files,
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


def resolve_workspace_path(state: ChatState, value: str) -> Path:
    if not value:
        raise ValueError("path is required")
    path = Path(value)
    if not path.is_absolute():
        path = state.workspace_dir / path
    return path.resolve()


def as_virtual_path(state: ChatState, path: Path) -> str:
    try:
        relative = path.relative_to(state.workspace_dir.resolve())
        return f"/workspace/{relative.as_posix()}"
    except ValueError:
        return f"/workspace_external/{path.name}"


def set_workspace(state: ChatState, args: str) -> None:
    if not args:
        print(f"Workspace: {state.workspace_dir}")
        return
    path = Path(args).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    path.mkdir(parents=True, exist_ok=True)
    state.workspace_dir = path.resolve()
    print(f"Workspace set: {state.workspace_dir}")


def show_tree(state: ChatState, args: str) -> None:
    depth = 2
    if args:
        if not args.isdigit():
            print("Usage: /tree [depth]")
            return
        depth = max(1, min(int(args), 5))

    root = state.workspace_dir
    root.mkdir(parents=True, exist_ok=True)
    print(f"{root.name}/")

    def walk(path: Path, current_depth: int, prefix: str = "") -> None:
        if current_depth > depth:
            return
        entries = sorted(path.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower()))
        for index, entry in enumerate(entries):
            connector = "└─ " if index == len(entries) - 1 else "├─ "
            print(f"{prefix}{connector}{entry.name}{'/' if entry.is_dir() else ''}")
            if entry.is_dir():
                extension = "   " if index == len(entries) - 1 else "│  "
                walk(entry, current_depth + 1, prefix + extension)

    walk(root, 1)


def read_workspace_file(state: ChatState, args: str) -> None:
    try:
        path = resolve_workspace_path(state, args)
    except ValueError as exc:
        print(exc)
        return
    if not path.exists() or not path.is_file():
        print(f"File not found: {path}")
        return
    content = path.read_text(encoding="utf-8")
    print("")
    print(f"[{path}]")
    print("-" * 78)
    print(content)


def write_workspace_file(state: ChatState, args: str) -> None:
    try:
        path = resolve_workspace_path(state, args)
    except ValueError as exc:
        print(exc)
        return
    print("Enter file content. Finish with a single dot (.) on its own line.")
    content = read_paste()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"File written: {path}")


def attach_file(state: ChatState, args: str) -> None:
    try:
        path = resolve_workspace_path(state, args)
    except ValueError as exc:
        print(exc)
        return
    if not path.exists() or not path.is_file():
        print(f"File not found: {path}")
        return
    content = path.read_text(encoding="utf-8")
    virtual_path = as_virtual_path(state, path)
    state.attached_files[virtual_path] = content
    print(f"Attached: {virtual_path}")


def list_attached_files(state: ChatState) -> None:
    if not state.attached_files:
        print("No attached files.")
        return
    for path in state.attached_files:
        print(f"- {path}")


def drop_file(state: ChatState, args: str) -> None:
    if args == "all":
        state.attached_files.clear()
        print("All attached files removed.")
        return
    if not args:
        print("Usage: /drop-file <path|all>")
        return
    if args in state.attached_files:
        del state.attached_files[args]
        print(f"Removed: {args}")
        return
    print(f"Attached file not found: {args}")


def render_plan_markdown(state: ChatState) -> str:
    title = state.plan_title or "Untitled Plan"
    lines = [
        f"# {title}",
        "",
        f"- Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- Model: {state.model_name}",
        f"- Multi Agent: {'enabled' if state.enable_multi_agent else 'disabled'}",
        f"- Harness Skills: {'enabled' if harness_skills_enabled() else 'disabled'}",
        "",
        "## Steps",
        "",
    ]
    if not state.plan_steps:
        lines.append("- [ ] No steps yet")
    else:
        for step in state.plan_steps:
            checked = "x" if step["status"] == "done" else " "
            lines.append(f"- [{checked}] {step['text']}")
    lines.append("")
    return "\n".join(lines)


def handle_plan_command(state: ChatState, args: str) -> None:
    command, _, value = args.partition(" ")
    command = command.lower().strip()
    value = value.strip()

    if command == "new":
        if not value:
            print("Usage: /plan new <title>")
            return
        state.plan_title = value
        state.plan_steps = []
        print(f"Plan started: {state.plan_title}")
    elif command == "add":
        if not value:
            print("Usage: /plan add <step>")
            return
        state.plan_steps.append({"status": "todo", "text": value})
        print(f"Plan step added: {value}")
    elif command == "done":
        if not value.isdigit():
            print("Usage: /plan done <number>")
            return
        index = int(value) - 1
        if index < 0 or index >= len(state.plan_steps):
            print("Step number out of range.")
            return
        state.plan_steps[index]["status"] = "done"
        print(f"Plan step done: {index + 1}")
    elif command == "show":
        print(render_plan_markdown(state))
    elif command == "save":
        save_plan(state, value)
    elif command == "load":
        load_plan(state, value)
    elif command == "clear":
        state.plan_title = ""
        state.plan_steps = []
        print("Plan cleared.")
    else:
        print("Usage: /plan new|add|done|show|save|load|clear")


def plan_slug(value: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in ("-", "_") else "-" for ch in value.strip())
    safe = "-".join(part for part in safe.split("-") if part)
    return safe[:80] or "plan"


def save_plan(state: ChatState, name: str = "") -> None:
    if not state.plan_title and not state.plan_steps:
        print("No current plan.")
        return
    state.plan_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{plan_slug(name or state.plan_title)}.md"
    path = state.plan_dir / filename
    path.write_text(render_plan_markdown(state), encoding="utf-8")
    print(f"Plan saved: {path}")


def list_plans(state: ChatState) -> None:
    state.plan_dir.mkdir(parents=True, exist_ok=True)
    plans = sorted(state.plan_dir.glob("*.md"))
    if not plans:
        print("No saved plans.")
        return
    for path in plans:
        print(f"- {path.stem}")


def load_plan(state: ChatState, name: str) -> None:
    if not name:
        print("Usage: /plan load <name>")
        return
    path = state.plan_dir / f"{plan_slug(name)}.md"
    if not path.exists():
        print(f"Plan not found: {path}")
        return
    content = path.read_text(encoding="utf-8")
    state.plan_title = name
    state.plan_steps = []
    for line in content.splitlines():
        if line.startswith("# "):
            state.plan_title = line[2:].strip()
        elif line.startswith("- ["):
            status = "done" if line.startswith("- [x]") else "todo"
            text = line[6:].strip()
            state.plan_steps.append({"status": status, "text": text})
    print(f"Plan loaded: {state.plan_title}")


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
    elif name == "/folder":
        set_workspace(state, args)
    elif name == "/tree":
        show_tree(state, args)
    elif name == "/read":
        read_workspace_file(state, args)
    elif name == "/write":
        write_workspace_file(state, args)
    elif name == "/add-file":
        attach_file(state, args)
    elif name == "/files":
        list_attached_files(state)
    elif name == "/drop-file":
        drop_file(state, args)
    elif name == "/plan":
        handle_plan_command(state, args)
    elif name == "/plans":
        list_plans(state)
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
        workspace_dir=Path(os.getenv("CHAT_WORKSPACE_DIR", "agent_workspace")).resolve(),
        plan_dir=Path(os.getenv("PLAN_DIR", "plans")).resolve(),
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
