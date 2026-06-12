import argparse
import os
import sys
from pathlib import Path

from env_common import load_project_env
from ops_common import session_dir
from scaffold_common import (
    SCAFFOLD_SAMPLE,
    apply_scaffold,
    parse_scaffold_text,
    render_scaffold_summary,
)
from ui_common import print_markdown_result, print_status_line


def read_paste() -> str:
    print_status_line("아이디어를 붙여넣으세요. 마지막 줄에 점 하나(.)만 입력하면 실행합니다.", "cyan")
    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line == ".":
            break
        lines.append(line)
    return "\n".join(lines).strip()


def read_input(args: argparse.Namespace) -> str:
    if args.command == "sample":
        return SCAFFOLD_SAMPLE
    if args.command == "paste":
        return read_paste()
    if args.command == "file":
        if not args.path:
            raise ValueError("file 명령에는 파일 경로가 필요합니다.")
        return Path(args.path).read_text(encoding="utf-8")
    if args.command == "stdin":
        return sys.stdin.read().strip()
    raise ValueError(f"지원하지 않는 명령입니다: {args.command}")


def run_scaffold(text: str, *, write_files: bool) -> int:
    if not text.strip():
        print_status_line("입력된 아이디어가 비어 있습니다.", "red")
        return 1

    load_project_env()
    workspace_dir = Path(os.getenv("CHAT_WORKSPACE_DIR", "agent_workspace")).resolve()
    plan_dir = Path(os.getenv("PLAN_DIR", "plans")).resolve()
    enable_multi_agent = os.getenv("ENABLE_MULTI_AGENT", "true").lower() in ("1", "true", "yes", "y")
    model_name = os.getenv("QWEN_MODEL", "qwen3.5")

    spec = parse_scaffold_text(text)
    result = apply_scaffold(
        spec,
        workspace_dir,
        plan_dir=plan_dir,
        session_dir=session_dir(),
        model_name=model_name,
        enable_multi_agent=enable_multi_agent,
        write_files=write_files,
    )
    summary = render_scaffold_summary(spec, result)
    title = "Scaffold Preview" if not write_files else "Scaffold Created"
    print_markdown_result(title, summary, border_style="cyan" if not write_files else "green")

    if write_files:
        print_status_line(f"작업 폴더: {workspace_dir}", "green")
        if result.summary_path:
            print_status_line(f"요약 파일: {result.summary_path}", "green")
    else:
        print_status_line("preview 모드라 실제 파일은 생성하지 않았습니다.", "yellow")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="deepagent-scaffold",
        description="아이디어 텍스트로 폴더, 파일, 목표, 플랜을 자동 생성합니다.",
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="paste",
        choices=("paste", "file", "stdin", "sample"),
        help="입력 방식입니다. 기본값은 paste입니다.",
    )
    parser.add_argument("path", nargs="?", help="file 명령에서 읽을 아이디어 Markdown 경로입니다.")
    parser.add_argument("--preview", action="store_true", help="실제 생성 없이 미리보기만 출력합니다.")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    try:
        text = read_input(args)
        if args.command == "sample" and not args.preview:
            print_markdown_result("Scaffold Sample", text, border_style="cyan")
            return
        raise SystemExit(run_scaffold(text, write_files=not args.preview))
    except Exception as exc:
        print_status_line(f"Scaffold 실패: {exc}", "red")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
