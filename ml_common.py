import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from ops_common import slugify


DEFAULT_MODEL_PROFILE = {
    "description": "폐쇄망 OpenAI 호환 vLLM 모델",
    "context_length": "unknown",
    "tool_calling": "verify",
    "recommended_temperature": 0.2,
    "use_cases": ["보안 점검", "보고서 작성", "내부 문서 기반 질의"],
    "notes": ["python doctor.py와 /test로 연결 및 Tool Calling 동작을 확인하세요."],
}


def model_catalog_path() -> Path:
    return Path(os.getenv("MODEL_CATALOG_PATH", "model_catalog.json")).resolve()


def experiment_dir() -> Path:
    return Path(os.getenv("EXPERIMENT_DIR", "experiments")).resolve()


def load_model_catalog(models: list[str]) -> dict[str, Any]:
    path = model_catalog_path()
    if path.exists():
        try:
            catalog = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            catalog = {}
    else:
        catalog = {}

    profiles = catalog.get("models", {}) if isinstance(catalog, dict) else {}
    for model in models:
        profiles.setdefault(model, dict(DEFAULT_MODEL_PROFILE))
    return {"models": profiles}


def save_model_catalog(catalog: dict[str, Any]) -> Path:
    path = model_catalog_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def ensure_model_catalog(models: list[str]) -> tuple[dict[str, Any], Path]:
    catalog = load_model_catalog(models)
    path = save_model_catalog(catalog)
    return catalog, path


def render_model_catalog_markdown(catalog: dict[str, Any]) -> str:
    lines = ["# Offline Model Catalog", "", f"- Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ""]
    for model, profile in sorted((catalog.get("models") or {}).items()):
        lines.extend(
            [
                f"## {model}",
                "",
                f"- Description: {profile.get('description', '')}",
                f"- Context Length: {profile.get('context_length', 'unknown')}",
                f"- Tool Calling: {profile.get('tool_calling', 'verify')}",
                f"- Recommended Temperature: {profile.get('recommended_temperature', 0.2)}",
                "",
                "### Use Cases",
                "",
            ]
        )
        lines.extend([f"- {item}" for item in profile.get("use_cases", [])] or ["- none"])
        lines.extend(["", "### Notes", ""])
        lines.extend([f"- {item}" for item in profile.get("notes", [])] or ["- none"])
        lines.append("")
    return "\n".join(lines)


def save_model_catalog_markdown(catalog: dict[str, Any]) -> Path:
    path = model_catalog_path().with_suffix(".md")
    path.write_text(render_model_catalog_markdown(catalog), encoding="utf-8")
    return path


def render_experiment_markdown(
    *,
    name: str,
    prompt: str,
    results: list[dict[str, Any]],
    goal_title: str = "",
) -> str:
    lines = [
        f"# Model Experiment - {name}",
        "",
        f"- Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- Goal: {goal_title or 'not set'}",
        f"- Models: {', '.join(item['model'] for item in results)}",
        "",
        "## Prompt",
        "",
        prompt,
        "",
        "## Summary",
        "",
        "| Model | Status | Characters | Error |",
        "|---|---:|---:|---|",
    ]
    for item in results:
        status = "ok" if item.get("ok") else "fail"
        output = str(item.get("result", ""))
        error = str(item.get("error", "")).replace("|", "\\|")
        lines.append(f"| {item['model']} | {status} | {len(output)} | {error} |")
    lines.append("")

    for item in results:
        lines.extend([f"## {item['model']}", ""])
        if item.get("ok"):
            lines.extend([str(item.get("result", "")), ""])
        else:
            lines.extend([f"Error: {item.get('error', '')}", ""])
    return "\n".join(lines)


def save_experiment(name: str, prompt: str, results: list[dict[str, Any]], *, goal_title: str = "") -> Path:
    day = datetime.now().strftime("%Y-%m-%d")
    directory = experiment_dir() / day
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{datetime.now().strftime('%H%M%S')}-{slugify(name, 'experiment')}.md"
    path.write_text(
        render_experiment_markdown(name=name, prompt=prompt, results=results, goal_title=goal_title),
        encoding="utf-8",
    )
    rebuild_experiment_index()
    return path


def rebuild_experiment_index() -> Path:
    root = experiment_dir()
    root.mkdir(parents=True, exist_ok=True)
    lines = ["# Offline ML Experiments", "", "```text", f"{root.name}/"]
    day_dirs = sorted([path for path in root.iterdir() if path.is_dir()], reverse=True)
    for day_dir in day_dirs:
        lines.append(f"├─ {day_dir.name}/")
        for record in sorted(day_dir.glob("*.md"), reverse=True):
            lines.append(f"│  ├─ {record.name}")
    lines.extend(["```", "", "## Records", ""])
    for day_dir in day_dirs:
        lines.extend([f"### {day_dir.name}", ""])
        for record in sorted(day_dir.glob("*.md"), reverse=True):
            relative = record.relative_to(root).as_posix()
            lines.append(f"- [{record.stem}]({relative})")
        lines.append("")
    index_path = root / "index.md"
    index_path.write_text("\n".join(lines), encoding="utf-8")
    return index_path
