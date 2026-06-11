import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ops_common import goal_to_markdown, now_text, save_goal_markdown, slugify


SCAFFOLD_SAMPLE = """# Goal
폐쇄망 DeepAgents PoC 실행 환경 구성

## Success Criteria
- Windows 11에서 python chat_cli.py 실행
- qwen3.5 모델 연결 테스트 성공
- 실행 기록이 wiki_logs에 남는다

## Constraints
- 외부 인터넷 사용 금지
- 외부 검색 Tool 사용 금지

# Plan
- .env 구성
- python doctor.py 실행
- python chat_cli.py 실행
- 결과를 wiki_logs에 기록

# Folders
reports/security
prompts
runbooks/vllm

# Files
## reports/security/checklist.md
```md
# 보안 점검 체크리스트

- [ ] 접근권한 확인
- [ ] 로그 수집 확인
- [ ] 취약점 조치 이력 확인
```

## prompts/access-audit.md
```md
서버 접근권한 보안 점검 TODO를 만들어줘.
```
"""


@dataclass
class ScaffoldSpec:
    goal: dict[str, Any] = field(default_factory=lambda: {"title": "", "criteria": [], "constraints": [], "notes": []})
    plan_title: str = ""
    plan_steps: list[str] = field(default_factory=list)
    folders: list[str] = field(default_factory=list)
    files: dict[str, str] = field(default_factory=dict)


@dataclass
class ScaffoldResult:
    created_dirs: list[Path] = field(default_factory=list)
    created_files: list[Path] = field(default_factory=list)
    goal_path: Path | None = None
    plan_path: Path | None = None
    summary_path: Path | None = None


def parse_scaffold_text(text: str) -> ScaffoldSpec:
    spec = ScaffoldSpec()
    section = ""
    subsection = ""
    current_file = ""
    in_fence = False
    file_lines: list[str] = []

    def finish_file() -> None:
        nonlocal current_file, file_lines
        if current_file:
            spec.files[current_file] = "\n".join(file_lines).rstrip() + "\n"
        current_file = ""
        file_lines = []

    for raw_line in text.splitlines():
        line = raw_line.rstrip("\n")
        stripped = line.strip()

        if section == "files" and current_file:
            if stripped.startswith("```"):
                if in_fence:
                    in_fence = False
                    finish_file()
                else:
                    in_fence = True
                continue
            if in_fence:
                file_lines.append(line)
                continue

        if stripped.startswith("# "):
            finish_file()
            section = stripped[2:].strip().lower()
            subsection = ""
            continue

        if stripped.startswith("## "):
            if section == "files":
                finish_file()
                current_file = stripped[3:].strip()
                file_lines = []
                in_fence = False
            else:
                subsection = stripped[3:].strip().lower()
            continue

        if not stripped:
            if section == "files" and current_file and not in_fence:
                file_lines.append("")
            continue

        if section == "goal":
            if subsection == "success criteria":
                spec.goal["criteria"].append(strip_list_marker(stripped))
            elif subsection == "constraints":
                spec.goal["constraints"].append(strip_list_marker(stripped))
            elif subsection == "notes":
                spec.goal["notes"].append(strip_list_marker(stripped))
            elif not spec.goal["title"]:
                spec.goal["title"] = stripped
            else:
                spec.goal.setdefault("notes", []).append(stripped)
        elif section == "plan":
            spec.plan_steps.append(strip_list_marker(stripped))
        elif section == "folders":
            spec.folders.append(strip_list_marker(stripped))
        elif section == "files" and current_file:
            file_lines.append(line)

    finish_file()
    if spec.goal["title"] and not spec.plan_title:
        spec.plan_title = f"{spec.goal['title']} 실행 플랜"
    elif not spec.plan_title:
        spec.plan_title = "Scaffold Plan"
    return spec


def strip_list_marker(value: str) -> str:
    value = value.strip()
    for marker in ("- [ ] ", "- [x] ", "- ", "* "):
        if value.lower().startswith(marker):
            return value[len(marker):].strip()
    if len(value) > 3 and value[0].isdigit() and value[1:3] in (". ", ") "):
        return value[3:].strip()
    return value


def safe_workspace_path(root: Path, relative_path: str) -> Path:
    raw = relative_path.strip().replace("\\", "/")
    if not raw:
        raise ValueError("empty path")
    path = Path(raw)
    if path.is_absolute() or ":" in raw or any(part == ".." for part in path.parts):
        raise ValueError(f"unsafe path: {relative_path}")
    resolved = (root / path).resolve()
    root_resolved = root.resolve()
    try:
        resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError(f"path escapes workspace: {relative_path}") from exc
    return resolved


def render_plan_markdown(title: str, steps: list[str]) -> str:
    lines = [f"# {title or 'Scaffold Plan'}", "", f"- Created: {now_text()}", "", "## Steps", ""]
    lines.extend([f"- [ ] {step}" for step in steps] or ["- [ ] No steps yet"])
    lines.append("")
    return "\n".join(lines)


def render_scaffold_summary(spec: ScaffoldSpec, result: ScaffoldResult) -> str:
    lines = [
        f"# Scaffold Result - {spec.goal.get('title') or spec.plan_title}",
        "",
        f"- Created: {now_text()}",
        "",
        "## Goal",
        "",
        f"- {spec.goal.get('title') or 'none'}",
        "",
        "## Plan",
        "",
    ]
    lines.extend([f"- [ ] {step}" for step in spec.plan_steps] or ["- [ ] No steps"])
    lines.extend(["", "## Created Folders", ""])
    lines.extend([f"- {path.as_posix()}" for path in result.created_dirs] or ["- none"])
    lines.extend(["", "## Created Files", ""])
    lines.extend([f"- {path.as_posix()}" for path in result.created_files] or ["- none"])
    if result.goal_path:
        lines.extend(["", f"- Goal File: {result.goal_path.as_posix()}"])
    if result.plan_path:
        lines.append(f"- Plan File: {result.plan_path.as_posix()}")
    lines.append("")
    return "\n".join(lines)


def apply_scaffold(
    spec: ScaffoldSpec,
    workspace_root: Path,
    *,
    plan_dir: Path,
    session_dir: Path,
    model_name: str = "",
    enable_multi_agent: bool = True,
    write_files: bool = True,
) -> ScaffoldResult:
    overwrite = os.getenv("SCAFFOLD_OVERWRITE", "false").lower() in ("1", "true", "yes", "y")
    workspace_root.mkdir(parents=True, exist_ok=True)
    result = ScaffoldResult()

    for folder in spec.folders:
        path = safe_workspace_path(workspace_root, folder)
        if write_files:
            path.mkdir(parents=True, exist_ok=True)
        result.created_dirs.append(path)

    for relative_path, content in spec.files.items():
        path = safe_workspace_path(workspace_root, relative_path)
        final_path = path
        if final_path.exists() and not overwrite:
            final_path = path.with_name(f"{path.name}.new")
        if write_files:
            final_path.parent.mkdir(parents=True, exist_ok=True)
            final_path.write_text(content, encoding="utf-8")
        result.created_files.append(final_path)

    if spec.goal.get("title") or spec.goal.get("criteria") or spec.goal.get("constraints") or spec.goal.get("notes"):
        if write_files:
            result.goal_path = save_goal_markdown(spec.goal, model_name=model_name, multi_agent=enable_multi_agent)

    if spec.plan_title or spec.plan_steps:
        plan_dir.mkdir(parents=True, exist_ok=True)
        path = plan_dir / f"{slugify(spec.plan_title, 'scaffold-plan')}.md"
        if write_files:
            path.write_text(render_plan_markdown(spec.plan_title, spec.plan_steps), encoding="utf-8")
        result.plan_path = path

    session_dir.mkdir(parents=True, exist_ok=True)
    summary_path = session_dir / f"scaffold-{slugify(spec.goal.get('title') or spec.plan_title, 'run')}.md"
    if write_files:
        summary_path.write_text(render_scaffold_summary(spec, result), encoding="utf-8")
    result.summary_path = summary_path
    return result


def scaffold_to_context_files(workspace_root: Path, result: ScaffoldResult) -> dict[str, str]:
    files = {}
    for path in result.created_files:
        if not path.exists() or not path.is_file():
            continue
        try:
            relative = path.resolve().relative_to(workspace_root.resolve()).as_posix()
            virtual_path = f"/workspace/{relative}"
        except ValueError:
            virtual_path = f"/workspace_external/{path.name}"
        files[virtual_path] = path.read_text(encoding="utf-8")
    return files
