import argparse
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from registration_common import (
    create_registration_package_from_profile,
    render_registration_report,
    save_registration_profile,
    scan_project,
    scaffold_registered_workspace_from_profile,
    refresh_registration_readiness,
)
from ui_common import print_key_value_table, print_markdown_result, print_status_line


def ask_value(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{prompt}{suffix}: ").strip()
    return value or default


def ask_yes_no(prompt: str, default: bool = True) -> bool:
    suffix = "Y/n" if default else "y/N"
    value = input(f"{prompt} ({suffix}): ").strip().lower()
    if not value:
        return default
    return value in ("y", "yes", "1", "true")


def ask_int(prompt: str, default: int) -> int:
    while True:
        value = ask_value(prompt, str(default))
        try:
            return int(value)
        except ValueError:
            print("숫자를 입력하세요.")


def print_readiness(profile: dict[str, Any]) -> None:
    readiness = profile.get("readiness", {})
    rows = [
        ("Project", profile.get("project_name", "")),
        ("Type", profile.get("project_type", "")),
        ("Framework", profile.get("primary_framework", "")),
        ("Entrypoint", profile.get("default_entrypoint") or "not found"),
        ("Readiness", f"{readiness.get('score', 0)}/100 ({readiness.get('level', 'unknown')})"),
    ]
    print_key_value_table("Registration Wizard", rows)
    lines = ["# 등록 전 점검표", ""]
    for item in readiness.get("checks", []):
        marker = {"pass": "[OK]", "warn": "[주의]", "fail": "[오류]"}.get(item.get("status"), "[정보]")
        lines.append(f"- {marker} {item.get('title')}: {item.get('detail')}")
    print_markdown_result("Readiness", "\n".join(lines), border_style="cyan")


def choose_entrypoint(profile: dict[str, Any]) -> None:
    candidates = list(profile.get("entrypoints") or [])
    notebooks = list(profile.get("notebooks") or [])
    if profile.get("default_entrypoint") and profile["default_entrypoint"] not in candidates:
        candidates.insert(0, profile["default_entrypoint"])
    for item in notebooks:
        if item not in candidates:
            candidates.append(item)
    if not candidates:
        value = ask_value("학습 실행 파일 경로를 입력하세요. 예: train.py")
        if value:
            profile["default_entrypoint"] = value
            profile.setdefault("job_template", {})["entrypoint"] = value
        return

    print_status_line("학습 진입점을 확인하세요.", "cyan")
    for index, item in enumerate(candidates, start=1):
        marker = " *" if item == profile.get("default_entrypoint") else ""
        print(f"{index}. {item}{marker}")
    print("0. 직접 입력")
    selected = ask_value("선택 번호", "1")
    if selected == "0":
        value = ask_value("학습 실행 파일 경로")
    elif selected.isdigit() and 1 <= int(selected) <= len(candidates):
        value = candidates[int(selected) - 1]
    else:
        value = profile.get("default_entrypoint") or candidates[0]
    profile["default_entrypoint"] = value
    profile.setdefault("job_template", {})["entrypoint"] = value


def fill_required_fields(profile: dict[str, Any]) -> dict[str, Any]:
    print_readiness(profile)
    choose_entrypoint(profile)

    mlflow = profile.setdefault("mlflow", {})
    job = profile.setdefault("job_template", {})
    execution = profile.setdefault("execution", {})

    mlflow["tracking_uri"] = ask_value("MLFlow Tracking URI", mlflow.get("tracking_uri") or os.getenv("MLFLOW_TRACKING_URI", ""))
    mlflow["experiment_name"] = ask_value("MLFlow Experiment 이름", mlflow.get("experiment_name") or profile.get("project_name", "experiment"))

    job["queue"] = ask_value("ML Platform Queue", job.get("queue") or os.getenv("ML_PLATFORM_DEFAULT_QUEUE", ""))
    job["arguments"] = ask_value("학습 실행 Arguments", job.get("arguments") or execution.get("arguments", ""))
    execution["arguments"] = job["arguments"]

    job["cpu"] = ask_int("CPU 개수", int(job.get("cpu") or 4))
    job["gpu"] = ask_int("GPU 개수", int(job.get("gpu") or 0))
    job["memory"] = ask_value("Memory", str(job.get("memory") or "16Gi"))

    image = ask_value("Platform Image 이름(모르면 비워두세요)", str(job.get("image") or ""))
    if image:
        job["image"] = image

    resource = profile.setdefault("resource_recommendation", {})
    resource["queue"] = job.get("queue", "")
    resource["cpu"] = job.get("cpu", 4)
    resource["gpu"] = job.get("gpu", 0)
    resource["memory"] = job.get("memory", "16Gi")

    profile = refresh_registration_readiness(profile)
    print_readiness(profile)
    return profile


def render_wizard_summary(result: dict[str, Any] | None, profile: dict[str, Any]) -> str:
    readiness = profile.get("readiness", {})
    lines = [
        "# ML Platform 등록 위자드 결과",
        "",
        f"- Project: {profile.get('project_name')}",
        f"- Project Type: {profile.get('project_type')}",
        f"- Framework: {profile.get('primary_framework')}",
        f"- Readiness: {readiness.get('score', 0)}/100 ({readiness.get('level', 'unknown')})",
        "",
        "## 산출물",
        "",
    ]
    if result:
        lines.append(f"- Registered Workspace: {result.get('workspace')}")
        if result.get("package_path"):
            lines.append(f"- Registration Package: {result.get('package_path')}")
    else:
        lines.append("- 미리보기 모드라 파일을 생성하지 않았습니다.")
    lines.extend(["", "## 다음 단계", ""])
    if readiness.get("level") == "ready":
        lines.append("- 등록 패키지를 플랫폼팀 또는 내부 포털에 전달할 수 있습니다.")
    else:
        lines.append("- 점검표의 [주의]/[오류] 항목을 먼저 보완하세요.")
    lines.append("- Job 실행 오류가 나면 `/register fix-log <로그파일>`로 Auto Fix 리포트를 생성하세요.")
    return "\n".join(lines)


def run_registration_wizard(*, write_files: bool = True, create_package: bool = True) -> tuple[dict[str, Any], dict[str, Any] | None, str]:
    project_path = ask_value("등록할 ML 프로젝트 폴더 경로")
    profile = scan_project(project_path)
    profile = fill_required_fields(profile)

    if not write_files:
        return profile, None, render_wizard_summary(None, profile)

    save_registration_profile(profile)
    if create_package:
        result = create_registration_package_from_profile(profile)
    else:
        result = scaffold_registered_workspace_from_profile(profile)
    return profile, result, render_wizard_summary(result, profile)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="deepagent-register-wizard", description="질문에 답하면서 ML Platform 등록 산출물을 생성합니다.")
    parser.add_argument("--preview", action="store_true", help="실제 파일 생성 없이 점검표와 입력값만 확인합니다.")
    parser.add_argument("--no-package", action="store_true", help="zip 패키지는 만들지 않고 등록 workspace만 생성합니다.")
    return parser


def main() -> None:
    load_dotenv()
    args = build_parser().parse_args()
    profile, _, summary = run_registration_wizard(write_files=not args.preview, create_package=not args.no_package)
    print_markdown_result("Registration Wizard", summary, border_style="cyan")
    if not args.preview:
        print_status_line(f"등록 위자드 완료: {profile.get('project_name')}", "green")
        print_status_line(f"최종 점수: {profile.get('readiness', {}).get('score', 0)}/100", "green")
    else:
        print_markdown_result("Registration Report Preview", render_registration_report(profile), border_style="cyan")


if __name__ == "__main__":
    main()
