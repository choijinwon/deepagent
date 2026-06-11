import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any


def slugify(value: str, fallback: str = "item", limit: int = 80) -> str:
    normalized = re.sub(r"[^0-9A-Za-z가-힣_-]+", "-", value.strip())
    normalized = re.sub(r"-+", "-", normalized).strip("-")
    return (normalized[:limit] or fallback)


def goal_dir() -> Path:
    return Path(os.getenv("GOAL_DIR", "goals")).resolve()


def session_dir() -> Path:
    return Path(os.getenv("SESSION_DIR", "sessions")).resolve()


def workspace_dir() -> Path:
    return Path(os.getenv("CHAT_WORKSPACE_DIR", "agent_workspace")).resolve()


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def goal_to_markdown(goal: dict[str, Any], *, model_name: str = "", multi_agent: bool | None = None) -> str:
    title = str(goal.get("title") or "Untitled Goal")
    criteria = [str(item) for item in goal.get("criteria", []) if str(item).strip()]
    constraints = [str(item) for item in goal.get("constraints", []) if str(item).strip()]
    notes = [str(item) for item in goal.get("notes", []) if str(item).strip()]
    lines = [
        f"# {title}",
        "",
        f"- Updated: {now_text()}",
    ]
    if model_name:
        lines.append(f"- Model: {model_name}")
    if multi_agent is not None:
        lines.append(f"- Multi Agent: {'enabled' if multi_agent else 'disabled'}")
    lines.extend(["", "## Success Criteria", ""])
    lines.extend([f"- [ ] {item}" for item in criteria] or ["- [ ] No success criteria yet"])
    lines.extend(["", "## Constraints", ""])
    lines.extend([f"- {item}" for item in constraints] or ["- No constraints yet"])
    lines.extend(["", "## Notes", ""])
    lines.extend([f"- {item}" for item in notes] or ["- No notes yet"])
    lines.append("")
    return "\n".join(lines)


def parse_goal_markdown(content: str, fallback_name: str) -> dict[str, Any]:
    goal: dict[str, Any] = {"title": fallback_name, "criteria": [], "constraints": [], "notes": []}
    section = ""
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            goal["title"] = stripped[2:].strip() or fallback_name
        elif stripped == "## Success Criteria":
            section = "criteria"
        elif stripped == "## Constraints":
            section = "constraints"
        elif stripped == "## Notes":
            section = "notes"
        elif section == "criteria" and stripped.startswith("- ["):
            text = stripped[6:].strip()
            if text and text != "No success criteria yet":
                goal["criteria"].append(text)
        elif section in ("constraints", "notes") and stripped.startswith("- "):
            text = stripped[2:].strip()
            if text and not text.startswith("No "):
                goal[section].append(text)
    return goal


def save_goal_markdown(goal: dict[str, Any], name: str = "", *, model_name: str = "", multi_agent: bool | None = None) -> Path:
    if not goal.get("title") and not goal.get("criteria") and not goal.get("constraints") and not goal.get("notes"):
        raise ValueError("No current goal.")
    directory = goal_dir()
    directory.mkdir(parents=True, exist_ok=True)
    filename = f"{slugify(name or str(goal.get('title') or 'goal'), 'goal')}.md"
    path = directory / filename
    path.write_text(goal_to_markdown(goal, model_name=model_name, multi_agent=multi_agent), encoding="utf-8")
    return path


def list_markdown_names(directory: Path) -> list[str]:
    directory.mkdir(parents=True, exist_ok=True)
    return [path.stem for path in sorted(directory.glob("*.md"))]


def load_goal_markdown(name: str) -> dict[str, Any]:
    path = goal_dir() / f"{slugify(name, 'goal')}.md"
    if not path.exists():
        raise FileNotFoundError(path)
    return parse_goal_markdown(path.read_text(encoding="utf-8"), path.stem)


def session_payload(state: Any) -> dict[str, Any]:
    return {
        "saved_at": now_text(),
        "model_name": state.model_name,
        "enable_multi_agent": state.enable_multi_agent,
        "workspace_dir": str(state.workspace_dir),
        "attached_files": sorted(state.attached_files.keys()),
        "attached_file_contents": state.attached_files,
        "goal": state.goal,
        "plan": {
            "title": state.plan_title,
            "steps": state.plan_steps,
        },
        "messages": state.messages,
    }


def save_session(state: Any, name: str) -> tuple[Path, Path]:
    if not name:
        raise ValueError("session name is required")
    directory = session_dir()
    directory.mkdir(parents=True, exist_ok=True)
    slug = slugify(name, "session")
    payload = session_payload(state)
    json_path = directory / f"{slug}.json"
    md_path = directory / f"{slug}.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_session_markdown(payload), encoding="utf-8")
    return json_path, md_path


def load_session(name: str) -> dict[str, Any]:
    path = session_dir() / f"{slugify(name, 'session')}.json"
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def render_session_markdown(payload: dict[str, Any]) -> str:
    goal = payload.get("goal") or {}
    plan = payload.get("plan") or {}
    lines = [
        f"# Session - {payload.get('model_name', 'unknown')}",
        "",
        f"- Saved: {payload.get('saved_at', '')}",
        f"- Model: {payload.get('model_name', '')}",
        f"- Multi Agent: {'enabled' if payload.get('enable_multi_agent') else 'disabled'}",
        f"- Workspace: {payload.get('workspace_dir', '')}",
        "",
        "## Goal",
        "",
        f"- Title: {goal.get('title') or 'none'}",
        "",
        "## Plan",
        "",
        f"- Title: {plan.get('title') or 'none'}",
    ]
    for step in plan.get("steps", []):
        checked = "x" if step.get("status") == "done" else " "
        lines.append(f"- [{checked}] {step.get('text', '')}")
    lines.extend(["", "## Attached Files", ""])
    lines.extend([f"- {path}" for path in payload.get("attached_files", [])] or ["- none"])
    lines.extend(["", "## Conversation Summary", ""])
    messages = payload.get("messages", [])
    if not messages:
        lines.append("- No messages")
    else:
        for message in messages[-10:]:
            content = str(message.get("content", "")).replace("\n", " ")
            lines.append(f"- {message.get('role', 'unknown')}: {content[:200]}")
    lines.append("")
    return "\n".join(lines)
