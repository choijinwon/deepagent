import argparse
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

from ops_common import session_dir, slugify
from scaffold_common import apply_scaffold, parse_scaffold_text, render_scaffold_summary
from ui_common import print_markdown_result, print_status_line


PROJECT_TYPES = {
    "1": ("python-cli", "Python CLI / 업무 자동화 도구"),
    "2": ("web-ui", "웹 UI / 내부 업무 화면"),
    "3": ("ml-platform", "ML Platform 등록 자동화"),
    "4": ("ml-experiment", "ML 실험 / 모델 개발"),
    "5": ("runbook", "문서 / 위키 / 운영 런북"),
    "6": ("custom", "직접 정의"),
}


@dataclass
class ProjectWizardSpec:
    name: str
    kind: str
    description: str
    users: str
    features: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    tech_stack: list[str] = field(default_factory=list)
    validation: list[str] = field(default_factory=list)


def ask_value(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{prompt}{suffix}: ").strip()
    return value or default


def ask_lines(prompt: str, defaults: list[str] | None = None) -> list[str]:
    defaults = defaults or []
    print_status_line(prompt, "cyan")
    if defaults:
        print_status_line("기본값을 쓰려면 바로 Enter를 누르세요.", "dim")
        for item in defaults:
            print(f"- {item}")
    print_status_line("직접 입력하려면 한 줄에 하나씩 쓰고, 빈 줄로 종료합니다.", "dim")
    lines = []
    while True:
        line = input("> ").strip()
        if not line:
            break
        lines.append(line)
    return lines or defaults


def choose_project_type() -> str:
    print_status_line("프로젝트 유형을 선택하세요.", "cyan")
    for number, (_, label) in PROJECT_TYPES.items():
        print(f"{number}. {label}")
    selected = ask_value("선택 번호", "1")
    return PROJECT_TYPES.get(selected, PROJECT_TYPES["6"])[0]


def default_features(kind: str) -> list[str]:
    if kind == "ml-platform":
        return ["프로젝트 구조 분석", "등록 프로필 생성", "Job Template 초안 생성", "오류 로그 Auto Fix 리포트 생성"]
    if kind == "ml-experiment":
        return ["데이터/모델 설정 정리", "학습 실행 스크립트", "실험 로그 기록", "검증 결과 리포트"]
    if kind == "web-ui":
        return ["모델 선택", "작업 실행", "결과 Markdown 렌더링", "실행 기록 저장"]
    if kind == "runbook":
        return ["절차 문서", "장애 대응 체크리스트", "운영 FAQ", "변경 이력"]
    return ["명령 실행", "설정 파일 관리", "로그 저장", "오류 분석"]


def default_stack(kind: str) -> list[str]:
    if kind == "web-ui":
        return ["Python stdlib HTTP server", "HTML/CSS/JavaScript", "Markdown rendering"]
    if kind == "ml-platform":
        return ["Python", "MLFlow", "YAML Job Template", "Offline wheel bundle"]
    if kind == "ml-experiment":
        return ["Python", "requirements.txt", "train.py", "MLFlow"]
    if kind == "runbook":
        return ["Markdown", "wiki_logs", "PowerShell"]
    return ["Python", "PowerShell", "Rich CLI"]


def default_validation(kind: str) -> list[str]:
    common = ["python -m py_compile src/main.py", "deepagent-doctor"]
    if kind in ("ml-platform", "ml-experiment"):
        return common + ["MLFlow 설정 확인", "샘플 Job Template 검토"]
    if kind == "web-ui":
        return common + ["deepagent-web 실행 확인"]
    return common


def ask_project_spec() -> ProjectWizardSpec:
    kind = choose_project_type()
    name = ask_value("프로젝트 이름", "new-internal-tool")
    description = ask_value("이 프로젝트가 해결할 문제", "폐쇄망 업무 자동화를 더 쉽게 만든다")
    users = ask_value("주 사용자", "사내 업무 담당자")
    features = ask_lines("필요한 주요 기능을 입력하세요.", default_features(kind))
    constraints = ask_lines(
        "제약사항을 입력하세요.",
        ["외부 인터넷 사용 금지", "폐쇄망 Windows 11 Pro에서 실행", "결과와 로그는 Markdown으로 기록"],
    )
    tech_stack = ask_lines("사용할 기술/도구를 입력하세요.", default_stack(kind))
    validation = ask_lines("검증 명령 또는 확인 기준을 입력하세요.", default_validation(kind))
    return ProjectWizardSpec(
        name=name,
        kind=kind,
        description=description,
        users=users,
        features=features,
        constraints=constraints,
        tech_stack=tech_stack,
        validation=validation,
    )


def bullet(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items) or "- TBD"


def checkbox(items: list[str]) -> str:
    return "\n".join(f"- [ ] {item}" for item in items) or "- [ ] TBD"


def build_project_scaffold_text(spec: ProjectWizardSpec) -> str:
    project_slug = slugify(spec.name, "project")
    root = f"projects/{project_slug}"
    plan_steps = [
        "요구사항과 성공 기준 확정",
        "초기 폴더/파일 구조 생성",
        "핵심 기능 1차 구현",
        "오류 로그 기반 수정 루프 실행",
        "검증 명령 실행 및 결과 기록",
        "운영 문서와 사용법 정리",
    ]
    files = {
        f"{root}/README.md": f"""# {spec.name}

## Purpose

{spec.description}

## Users

{spec.users}

## Project Type

{spec.kind}

## Features

{bullet(spec.features)}

## Constraints

{bullet(spec.constraints)}

## Tech Stack

{bullet(spec.tech_stack)}

## Validation

{checkbox(spec.validation)}
""",
        f"{root}/docs/requirements.md": f"""# Requirements - {spec.name}

## Problem

{spec.description}

## Primary Users

{spec.users}

## Functional Requirements

{checkbox(spec.features)}

## Constraints

{checkbox(spec.constraints)}
""",
        f"{root}/docs/development-plan.md": f"""# Development Plan - {spec.name}

## Steps

{checkbox(plan_steps)}

## Validation

{checkbox(spec.validation)}
""",
        f"{root}/src/main.py": f'''"""Entry point for {spec.name}."""


def main() -> None:
    print("{spec.name} 준비 중")


if __name__ == "__main__":
    main()
''',
        f"{root}/tests/README.md": f"""# Tests - {spec.name}

검증 명령:

{bullet(spec.validation)}
""",
    }
    if spec.kind == "ml-platform":
        files[f"{root}/platform/job_template.yaml"] = """name: sample-training-job
queue: ${ML_PLATFORM_DEFAULT_QUEUE}
resources:
  cpu: ${ML_PLATFORM_DEFAULT_CPU}
  gpu: ${ML_PLATFORM_DEFAULT_GPU}
  memory: ${ML_PLATFORM_DEFAULT_MEMORY}
command:
  - python
  - src/main.py
"""
        files[f"{root}/platform/mlflow_config.yaml"] = """tracking_uri: ${MLFLOW_TRACKING_URI}
experiment_name: ${PROJECT_NAME}
"""

    file_blocks = []
    for path, content in files.items():
        file_blocks.extend([f"## {path}", "```text", content.rstrip(), "```", ""])

    return "\n".join(
        [
            "# Goal",
            spec.name,
            "",
            "## Success Criteria",
            checkbox(spec.validation),
            "",
            "## Constraints",
            bullet(spec.constraints),
            "",
            "# Plan",
            bullet(plan_steps),
            "",
            "# Folders",
            f"{root}",
            f"{root}/docs",
            f"{root}/src",
            f"{root}/tests",
            *( [f"{root}/platform"] if spec.kind == "ml-platform" else [] ),
            "",
            "# Files",
            *file_blocks,
        ]
    )


def run_project_wizard(
    *,
    workspace_dir: Path,
    plan_dir: Path,
    session_path: Path,
    model_name: str,
    enable_multi_agent: bool,
    write_files: bool = True,
):
    spec = ask_project_spec()
    scaffold_text = build_project_scaffold_text(spec)
    scaffold_spec = parse_scaffold_text(scaffold_text)
    result = apply_scaffold(
        scaffold_spec,
        workspace_dir,
        plan_dir=plan_dir,
        session_dir=session_path,
        model_name=model_name,
        enable_multi_agent=enable_multi_agent,
        write_files=write_files,
    )
    return spec, scaffold_spec, result, render_scaffold_summary(scaffold_spec, result)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="deepagent-project", description="질문에 답하면서 새 프로젝트 구조를 생성합니다.")
    parser.add_argument("--preview", action="store_true", help="실제 파일 생성 없이 미리보기만 합니다.")
    return parser


def main() -> None:
    load_dotenv()
    args = build_parser().parse_args()
    workspace_dir = Path(os.getenv("CHAT_WORKSPACE_DIR", "agent_workspace")).resolve()
    plan_dir = Path(os.getenv("PLAN_DIR", "plans")).resolve()
    spec, _, result, summary = run_project_wizard(
        workspace_dir=workspace_dir,
        plan_dir=plan_dir,
        session_path=session_dir(),
        model_name=os.getenv("QWEN_MODEL", "qwen3.5"),
        enable_multi_agent=os.getenv("ENABLE_MULTI_AGENT", "true").lower() in ("1", "true", "yes", "y"),
        write_files=not args.preview,
    )
    print_markdown_result("Project Preview" if args.preview else "Project Created", summary, border_style="cyan")
    if not args.preview:
        print_status_line(f"프로젝트 생성 완료: {spec.name}", "green")
        if result.summary_path:
            print_status_line(f"요약 파일: {result.summary_path}", "green")


if __name__ == "__main__":
    main()
