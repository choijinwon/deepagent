import argparse
from pathlib import Path

from dotenv import load_dotenv

from autofix_common import analyze_log_file, render_fix_report, save_fix_report
from dev_common import generate_patch_candidates, save_patch_candidates
from ui_common import print_markdown_result, print_status_line


def ask_value(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{prompt}{suffix}: ").strip()
    return value or default


def resolve_optional_dir(value: str) -> Path:
    if not value:
        return Path.cwd().resolve()
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    if not path.exists() or not path.is_dir():
        raise FileNotFoundError(f"folder not found: {path}")
    return path.resolve()


def run_fix_wizard(*, log_path: str = "", workspace_path: str = "") -> tuple[dict, Path, Path]:
    log_path = log_path or ask_value("오류 로그 파일 경로")
    workspace_path = workspace_path or ask_value("관련 프로젝트 또는 등록 workspace 경로(모르면 Enter)", "")
    workspace_dir = resolve_optional_dir(workspace_path)

    report = analyze_log_file(log_path)
    report["context"] = {
        "workspace": workspace_dir.as_posix(),
        "log_path": str(Path(log_path).expanduser()),
    }
    fix_path = save_fix_report(report)

    candidates = generate_patch_candidates(report, workspace_dir)
    patch_path = save_patch_candidates(candidates, report["source"])
    return report, fix_path, patch_path


def render_wizard_result(report: dict, fix_path: Path, patch_path: Path) -> str:
    lines = [
        "# AI Studio 오류수정 위자드 결과",
        "",
        f"- Fix Report: {fix_path}",
        f"- Patch Candidates: {patch_path}",
        f"- Retest Command: {report.get('retest_command')}",
        "",
        "## 다음 단계",
        "",
        "1. Fix Report의 [오류]/[주의] 항목을 확인합니다.",
        "2. Patch Candidates에 적용 가능한 변경이 있으면 내용을 검토합니다.",
        "3. 자동 적용은 하지 않았습니다. 적용이 필요하면 CLI의 `/dev apply` 흐름 또는 수동 수정 후 재검증합니다.",
        "4. Retest Command 또는 동일 AI Studio Job을 재실행하고 새 로그를 저장합니다.",
    ]
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="deepagent-fix-wizard", description="AI Studio 학습 Job 오류 로그를 질문형으로 분석합니다.")
    parser.add_argument("log_path", nargs="?", default="", help="오류 로그 파일 경로")
    parser.add_argument("--workspace", default="", help="관련 프로젝트 또는 등록 workspace 경로")
    return parser


def main() -> None:
    load_dotenv()
    args = build_parser().parse_args()
    try:
        report, fix_path, patch_path = run_fix_wizard(log_path=args.log_path, workspace_path=args.workspace)
    except Exception as exc:
        print_status_line(f"오류수정 위자드 실패: {exc}", "red")
        raise SystemExit(1) from exc

    print_markdown_result("Auto Fix Plan", render_fix_report(report), border_style="yellow")
    print_markdown_result("Patch Candidates", patch_path.read_text(encoding="utf-8"), border_style="yellow")
    print_markdown_result("오류수정 위자드", render_wizard_result(report, fix_path, patch_path), border_style="cyan")
    print_status_line(f"Fix report 저장: {fix_path}", "green")


if __name__ == "__main__":
    main()
