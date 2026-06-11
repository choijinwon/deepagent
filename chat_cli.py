import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from autofix_common import analyze_log_file, render_fix_report, save_fix_report
from doctor import run_doctor
from ml_common import (
    ensure_model_catalog,
    save_experiment,
    save_model_catalog_markdown,
)
from ops_common import (
    goal_dir,
    goal_to_markdown,
    list_markdown_names,
    load_goal_markdown,
    load_session,
    save_goal_markdown,
    save_session,
    session_dir,
)
from registration_common import (
    render_registration_report,
    save_registration_profile,
    scan_project,
    scaffold_registered_workspace,
)
from scaffold_common import (
    SCAFFOLD_SAMPLE,
    apply_scaffold,
    parse_scaffold_text,
    render_scaffold_summary,
    scaffold_to_context_files,
)
from app_closed import (
    build_agent,
    get_available_models,
    get_default_model,
    get_harness_skill_files,
    get_harness_skill_names,
    harness_skills_enabled,
)
from web_closed import (
    invoke_agent_text,
    load_prompt_store,
    save_prompt_store,
    save_wiki_record,
)
from ui_common import MarkdownStream, print_key_value_table, print_markdown_result, print_status_line


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
  /goal new <title>     Start a goal
  /goal criteria <text> Add success criteria
  /goal constraint <t>  Add a constraint
  /goal note <text>     Add a goal note
  /goal show            Show current goal
  /goal save [name]     Save current goal as Markdown
  /goal load <name>     Load a saved goal
  /goal clear           Clear current goal
  /goals                List saved goals
  /session save <name>  Save session as JSON and Markdown
  /session load <name>  Load a saved session
  /sessions             List saved sessions
  /doctor               Run closed-network diagnostics
  /catalog              Create/show offline model catalog
  /experiment <models>  Run last prompt across comma-separated models
  /scaffold sample      Show paste scaffold sample
  /scaffold paste       Create folders/files/goals/plans from pasted text
  /scaffold file <path> Create scaffold from a workspace file
  /scaffold last        Show last scaffold result
  /scaffold attach      Attach last scaffold files to context
  /register scan <path> Analyze an ML project for platform registration
  /register scaffold <p> Generate standard registration workspace
  /register report <p> Save registration profile and report
  /register fix-log <p> Analyze job log and create fix plan
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
    goal_dir: Path
    messages: list[dict[str, str]] = field(default_factory=list)
    last_user_prompt: str = ""
    attached_files: dict[str, str] = field(default_factory=dict)
    plan_title: str = ""
    plan_steps: list[dict[str, str]] = field(default_factory=list)
    goal: dict = field(default_factory=lambda: {"title": "", "criteria": [], "constraints": [], "notes": []})
    last_scaffold_files: list[Path] = field(default_factory=list)
    last_scaffold_summary: str = ""


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
    print_status_line("DeepAgents Chat CLI - Qwen/vLLM Closed Network", "bold cyan")
    print_status_line("Type /help for commands. Type /exit to quit.", "dim")
    print_status(state)


def print_status(state: ChatState) -> None:
    print_key_value_table(
        "Runtime",
        [
            ("Model", state.model_name),
            ("Multi Agent", "ON" if state.enable_multi_agent else "OFF"),
            ("Harness Skills", "ON" if harness_skills_enabled() else "OFF"),
            ("Skill List", ", ".join(get_harness_skill_names()) or "none"),
            ("Workspace", str(state.workspace_dir)),
            ("Attached Files", str(len(state.attached_files))),
            ("Goal", str(state.goal.get("title") or "none")),
            ("Plan", f"{state.plan_title or 'none'} ({len(state.plan_steps)} steps)"),
            ("Turns", str(len([m for m in state.messages if m["role"] == "user"]))),
        ],
    )


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
    print_markdown_result("assistant", text)


def invoke_chat(
    cache: ChatAgentCache,
    state: ChatState,
    prompt: str,
    *,
    show_progress: bool = False,
    stream_to_console: bool = False,
) -> str:
    state.messages.append({"role": "user", "content": prompt})
    state.last_user_prompt = prompt

    if show_progress:
        print_status_line(f"[status] model={state.model_name}, multi_agent={'on' if state.enable_multi_agent else 'off'}")
        print_status_line("[status] 에이전트와 컨텍스트 준비 중...")
    agent = cache.get(state)
    files = get_harness_skill_files()
    files.update(state.attached_files)
    if state.goal.get("title") or state.goal.get("criteria") or state.goal.get("constraints") or state.goal.get("notes"):
        files["/goals/current-goal.md"] = goal_to_markdown(
            state.goal,
            model_name=state.model_name,
            multi_agent=state.enable_multi_agent,
        )

    request = {
        "messages": state.messages,
        "files": files,
    }
    stream_view = MarkdownStream("assistant")

    def print_status(message: str) -> None:
        if show_progress:
            print_status_line(f"[status] {message}")

    def print_delta(delta: str) -> None:
        if not stream_to_console:
            return
        stream_view.append(delta)

    if stream_to_console:
        with stream_view:
            result, streamed = invoke_agent_text(
                agent,
                request,
                on_delta=print_delta,
                on_status=print_status,
            )
    else:
        result, streamed = invoke_agent_text(
            agent,
            request,
            on_delta=None,
            on_status=print_status,
        )
    if stream_to_console:
        if not streamed:
            print_markdown_result("assistant", result)
    state.messages.append({"role": "assistant", "content": result})

    save_wiki_record(
        prompt=prompt,
        result=result,
        model_name=state.model_name,
        enable_multi_agent=state.enable_multi_agent,
        goal_title=str(state.goal.get("title") or ""),
    )
    return result


def run_chat_interactive(cache: ChatAgentCache, state: ChatState, prompt: str) -> None:
    invoke_chat(cache, state, prompt, show_progress=True, stream_to_console=True)


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


def handle_goal_command(state: ChatState, args: str) -> None:
    command, _, value = args.partition(" ")
    command = command.lower().strip()
    value = value.strip()

    if command == "new":
        if not value:
            print("Usage: /goal new <title>")
            return
        state.goal = {"title": value, "criteria": [], "constraints": [], "notes": []}
        print(f"Goal started: {value}")
    elif command == "criteria":
        if not value:
            print("Usage: /goal criteria <text>")
            return
        state.goal.setdefault("criteria", []).append(value)
        print(f"Goal criteria added: {value}")
    elif command == "constraint":
        if not value:
            print("Usage: /goal constraint <text>")
            return
        state.goal.setdefault("constraints", []).append(value)
        print(f"Goal constraint added: {value}")
    elif command == "note":
        if not value:
            print("Usage: /goal note <text>")
            return
        state.goal.setdefault("notes", []).append(value)
        print(f"Goal note added: {value}")
    elif command == "show":
        print(goal_to_markdown(state.goal, model_name=state.model_name, multi_agent=state.enable_multi_agent))
    elif command == "save":
        try:
            path = save_goal_markdown(
                state.goal,
                value,
                model_name=state.model_name,
                multi_agent=state.enable_multi_agent,
            )
            print(f"Goal saved: {path}")
        except ValueError as exc:
            print(exc)
    elif command == "load":
        if not value:
            print("Usage: /goal load <name>")
            return
        try:
            state.goal = load_goal_markdown(value)
            print(f"Goal loaded: {state.goal.get('title')}")
        except FileNotFoundError as exc:
            print(f"Goal not found: {exc}")
    elif command == "clear":
        state.goal = {"title": "", "criteria": [], "constraints": [], "notes": []}
        print("Goal cleared.")
    else:
        print("Usage: /goal new|criteria|constraint|note|show|save|load|clear")


def list_goals() -> None:
    names = list_markdown_names(goal_dir())
    if not names:
        print("No saved goals.")
        return
    for name in names:
        print(f"- {name}")


def handle_session_command(state: ChatState, args: str) -> None:
    command, _, value = args.partition(" ")
    command = command.lower().strip()
    value = value.strip()

    if command == "save":
        if not value:
            print("Usage: /session save <name>")
            return
        try:
            json_path, md_path = save_session(state, value)
            print(f"Session saved: {json_path}")
            print(f"Session wiki: {md_path}")
        except ValueError as exc:
            print(exc)
    elif command == "load":
        if not value:
            print("Usage: /session load <name>")
            return
        try:
            payload = load_session(value)
        except FileNotFoundError as exc:
            print(f"Session not found: {exc}")
            return
        state.model_name = str(payload.get("model_name") or state.model_name)
        state.enable_multi_agent = bool(payload.get("enable_multi_agent", state.enable_multi_agent))
        state.workspace_dir = Path(payload.get("workspace_dir") or state.workspace_dir).resolve()
        state.goal = payload.get("goal") or {"title": "", "criteria": [], "constraints": [], "notes": []}
        plan = payload.get("plan") or {}
        state.plan_title = str(plan.get("title") or "")
        state.plan_steps = list(plan.get("steps") or [])
        state.messages = list(payload.get("messages") or [])
        state.attached_files = dict(payload.get("attached_file_contents") or {})
        print(f"Session loaded: {value}")
    else:
        print("Usage: /session save|load <name>")


def list_sessions() -> None:
    names = list_markdown_names(session_dir())
    if not names:
        print("No saved sessions.")
        return
    for name in names:
        print(f"- {name}")


def run_doctor_command() -> None:
    for line in run_doctor():
        print(line)


def show_catalog() -> None:
    catalog, json_path = ensure_model_catalog(get_available_models())
    md_path = save_model_catalog_markdown(catalog)
    print(f"Model catalog JSON: {json_path}")
    print(f"Model catalog Markdown: {md_path}")
    print("")
    for model, profile in sorted(catalog.get("models", {}).items()):
        print(f"- {model}: tool_calling={profile.get('tool_calling')} context={profile.get('context_length')}")


def handle_experiment_command(command_cache: ChatAgentCache, state: ChatState, args: str) -> None:
    if not state.last_user_prompt:
        print("No last user prompt. Send a prompt first, or /load a saved prompt.")
        return
    models = [item.strip() for item in args.split(",") if item.strip()] if args else get_available_models()
    available = set(get_available_models())
    unknown = [model for model in models if model not in available]
    if unknown:
        print(f"Unknown model(s): {', '.join(unknown)}")
        print(f"Available: {', '.join(get_available_models())}")
        return

    previous_model = state.model_name
    previous_messages = list(state.messages)
    results = []
    for model in models:
        print(f"Running experiment model: {model}")
        state.model_name = model
        state.messages = []
        try:
            result = invoke_chat(command_cache, state, state.last_user_prompt)
            results.append({"model": model, "ok": True, "result": result})
        except Exception as exc:
            results.append({"model": model, "ok": False, "error": str(exc), "result": ""})
    state.model_name = previous_model
    state.messages = previous_messages
    path = save_experiment(
        "model-compare",
        state.last_user_prompt,
        results,
        goal_title=str(state.goal.get("title") or ""),
    )
    print(f"Experiment saved: {path}")


def handle_scaffold_command(state: ChatState, args: str) -> None:
    command, _, value = args.partition(" ")
    command = command.lower().strip()
    value = value.strip()

    if command == "sample":
        print(SCAFFOLD_SAMPLE)
        return
    if command == "last":
        print(state.last_scaffold_summary or "No scaffold has been created yet.")
        return
    if command == "attach":
        if not state.last_scaffold_files:
            print("No scaffold files to attach.")
            return
        attached = 0
        for path in state.last_scaffold_files:
            if path.exists() and path.is_file():
                virtual_path = as_virtual_path(state, path)
                state.attached_files[virtual_path] = path.read_text(encoding="utf-8")
                attached += 1
        print(f"Attached scaffold files: {attached}")
        return

    if command == "paste":
        text = read_paste()
    elif command == "file":
        if not value:
            print("Usage: /scaffold file <path>")
            return
        try:
            path = resolve_workspace_path(state, value)
            text = path.read_text(encoding="utf-8")
        except Exception as exc:
            print(f"Scaffold file read failed: {exc}")
            return
    else:
        print("Usage: /scaffold sample|paste|file <path>|last|attach")
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
        )
    except Exception as exc:
        print(f"Scaffold failed: {exc}")
        return

    state.goal = spec.goal if spec.goal.get("title") else state.goal
    state.plan_title = spec.plan_title
    state.plan_steps = [{"status": "todo", "text": step} for step in spec.plan_steps]
    state.last_scaffold_files = list(result.created_files)
    state.last_scaffold_summary = render_scaffold_summary(spec, result)
    print(state.last_scaffold_summary)
    print(f"Scaffold summary: {result.summary_path}")


def handle_register_command(state: ChatState, args: str) -> None:
    command, _, value = args.partition(" ")
    command = command.lower().strip()
    value = value.strip()

    if command == "scan":
        if not value:
            print("Usage: /register scan <project-path>")
            return
        try:
            profile = scan_project(value)
        except Exception as exc:
            print(f"Registration scan failed: {exc}")
            return
        print(render_registration_report(profile))
    elif command == "report":
        if not value:
            print("Usage: /register report <project-path>")
            return
        try:
            profile = scan_project(value)
            json_path, report_path = save_registration_profile(profile)
        except Exception as exc:
            print(f"Registration report failed: {exc}")
            return
        print(f"Registration profile: {json_path}")
        print(f"Registration report: {report_path}")
    elif command == "scaffold":
        if not value:
            print("Usage: /register scaffold <project-path>")
            return
        try:
            result = scaffold_registered_workspace(value)
        except Exception as exc:
            print(f"Registration scaffold failed: {exc}")
            return
        print(f"Registered workspace: {result['workspace']}")
        print("Generated files:")
        for filename in result["files"]:
            print(f"- {filename}")
    elif command == "fix-log":
        if not value:
            print("Usage: /register fix-log <log-file>")
            return
        try:
            report = analyze_log_file(value)
            path = save_fix_report(report)
        except Exception as exc:
            print(f"Auto Fix analysis failed: {exc}")
            return
        print(render_fix_report(report))
        print(f"Fix report saved: {path}")
    else:
        print("Usage: /register scan|scaffold|report|fix-log <path>")


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
        category = f" [{item.get('category')}]" if item.get("category") else ""
        tags = f" #{', #'.join(item.get('tags', []))}" if item.get("tags") else ""
        print(f"- {item['name']}{category}{tags}")


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
                run_chat_interactive(cache, state, prompt)
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
    elif name == "/goal":
        handle_goal_command(state, args)
    elif name == "/goals":
        list_goals()
    elif name == "/session":
        handle_session_command(state, args)
    elif name == "/sessions":
        list_sessions()
    elif name == "/doctor":
        run_doctor_command()
    elif name == "/catalog":
        show_catalog()
    elif name == "/experiment":
        handle_experiment_command(cache, state, args)
    elif name == "/scaffold":
        handle_scaffold_command(state, args)
    elif name == "/register":
        handle_register_command(state, args)
    elif name == "/paste":
        prompt = read_paste()
        if prompt:
            try:
                run_chat_interactive(cache, state, prompt)
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
        goal_dir=Path(os.getenv("GOAL_DIR", "goals")).resolve(),
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
            run_chat_interactive(cache, state, user_input)
        except Exception as exc:
            print(f"Run failed: {exc}")


if __name__ == "__main__":
    main()
