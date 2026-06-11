import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from ops_common import slugify


FRAMEWORK_HINTS = {
    "pytorch": ["torch", "pytorch", "lightning"],
    "tensorflow": ["tensorflow", "keras"],
    "xgboost": ["xgboost"],
    "huggingface": ["transformers", "datasets", "accelerate", "peft"],
    "sklearn": ["sklearn", "scikit-learn"],
    "mlflow": ["mlflow"],
}

CONFIG_SUFFIXES = {".yaml", ".yml", ".json", ".toml", ".ini", ".cfg"}
MODEL_SUFFIXES = {".pt", ".pth", ".ckpt", ".bin", ".safetensors", ".pkl", ".joblib", ".onnx", ".h5"}
ENTRYPOINT_NAMES = ["train.py", "main.py", "run.py", "fit.py", "trainer.py"]


def registration_dir() -> Path:
    return Path(os.getenv("REGISTRATION_DIR", "registrations")).resolve()


def registered_workspace_dir() -> Path:
    return Path(os.getenv("REGISTERED_WORKSPACE_DIR", "agent_workspace/registered")).resolve()


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def safe_project_path(value: str) -> Path:
    if not value:
        raise ValueError("project path is required")
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    if not path.exists() or not path.is_dir():
        raise FileNotFoundError(f"project folder not found: {path}")
    return path.resolve()


def iter_project_files(project_root: Path, limit: int = 2000) -> list[Path]:
    ignored = {".git", ".venv", "venv", "__pycache__", ".mypy_cache", ".pytest_cache", "node_modules"}
    files = []
    for path in project_root.rglob("*"):
        if len(files) >= limit:
            break
        if any(part in ignored for part in path.parts):
            continue
        if path.is_file():
            files.append(path)
    return files


def read_small_text(path: Path, limit: int = 300_000) -> str:
    try:
        if path.stat().st_size > limit:
            return ""
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def detect_frameworks(files: list[Path]) -> list[str]:
    scores = {name: 0 for name in FRAMEWORK_HINTS}
    for path in files:
        name = path.name.lower()
        if name in ("requirements.txt", "pyproject.toml", "environment.yml", "environment.yaml", "setup.py"):
            content = read_small_text(path).lower()
            for framework, hints in FRAMEWORK_HINTS.items():
                if any(hint in content for hint in hints):
                    scores[framework] += 2
        if path.suffix == ".ipynb":
            scores["notebook"] = scores.get("notebook", 0) + 2
        if path.suffix == ".py":
            content = read_small_text(path).lower()
            for framework, hints in FRAMEWORK_HINTS.items():
                if any(f"import {hint}" in content or f"from {hint}" in content for hint in hints):
                    scores[framework] += 1
    detected = [name for name, score in scores.items() if score > 0]
    return detected or ["legacy-script"]


def find_entrypoints(project_root: Path, files: list[Path]) -> list[str]:
    candidates = []
    for preferred in ENTRYPOINT_NAMES:
        path = project_root / preferred
        if path.exists():
            candidates.append(path.relative_to(project_root).as_posix())
    for path in files:
        if path.suffix == ".py" and path.name.lower() not in ENTRYPOINT_NAMES:
            content = read_small_text(path)
            if "if __name__" in content or "argparse" in content or "click.command" in content:
                rel = path.relative_to(project_root).as_posix()
                if rel not in candidates:
                    candidates.append(rel)
    return candidates[:10]


def find_files_by_names(project_root: Path, files: list[Path], names: set[str]) -> list[str]:
    found = []
    for path in files:
        if path.name.lower() in names:
            found.append(path.relative_to(project_root).as_posix())
    return sorted(found)


def find_files_by_suffix(project_root: Path, files: list[Path], suffixes: set[str], limit: int = 30) -> list[str]:
    found = []
    for path in files:
        if path.suffix.lower() in suffixes:
            found.append(path.relative_to(project_root).as_posix())
    return sorted(found)[:limit]


def infer_python_version() -> str:
    return os.getenv("ML_PLATFORM_PYTHON_VERSION", "3.11")


def scan_project(project_path: str) -> dict[str, Any]:
    project_root = safe_project_path(project_path)
    files = iter_project_files(project_root)
    entrypoints = find_entrypoints(project_root, files)
    requirements = find_files_by_names(
        project_root,
        files,
        {"requirements.txt", "pyproject.toml", "environment.yml", "environment.yaml", "setup.py"},
    )
    notebooks = find_files_by_suffix(project_root, files, {".ipynb"})
    configs = find_files_by_suffix(project_root, files, CONFIG_SUFFIXES)
    model_files = find_files_by_suffix(project_root, files, MODEL_SUFFIXES)
    frameworks = detect_frameworks(files)
    default_entrypoint = entrypoints[0] if entrypoints else (notebooks[0] if notebooks else "")
    profile = {
        "project_name": project_root.name,
        "project_path": project_root.as_posix(),
        "scanned_at": now_text(),
        "frameworks": frameworks,
        "python_version": infer_python_version(),
        "entrypoints": entrypoints,
        "default_entrypoint": default_entrypoint,
        "requirements": requirements,
        "notebooks": notebooks[:20],
        "configs": configs[:30],
        "model_files": model_files[:30],
        "mlflow": {
            "tracking_uri": os.getenv("MLFLOW_TRACKING_URI", ""),
            "experiment_name": project_root.name,
        },
        "job_template": {
            "queue": os.getenv("ML_PLATFORM_DEFAULT_QUEUE", ""),
            "gpu": int(os.getenv("ML_PLATFORM_DEFAULT_GPU", "1") or "1"),
            "cpu": int(os.getenv("ML_PLATFORM_DEFAULT_CPU", "4") or "4"),
            "memory": os.getenv("ML_PLATFORM_DEFAULT_MEMORY", "16Gi"),
            "entrypoint": default_entrypoint,
            "arguments": "",
        },
        "warnings": build_warnings(default_entrypoint, requirements, frameworks),
    }
    return profile


def build_warnings(default_entrypoint: str, requirements: list[str], frameworks: list[str]) -> list[str]:
    warnings = []
    if not default_entrypoint:
        warnings.append("학습 실행 파일 또는 notebook 후보를 찾지 못했습니다.")
    if not requirements:
        warnings.append("requirements.txt, pyproject.toml, environment.yml 후보를 찾지 못했습니다.")
    if frameworks == ["legacy-script"]:
        warnings.append("명확한 ML framework import를 찾지 못해 legacy script로 분류했습니다.")
    if "mlflow" not in frameworks:
        warnings.append("MLFlow 의존성 또는 import가 감지되지 않았습니다.")
    return warnings


def save_registration_profile(profile: dict[str, Any]) -> tuple[Path, Path]:
    directory = registration_dir() / slugify(profile["project_name"], "project")
    directory.mkdir(parents=True, exist_ok=True)
    json_path = directory / "registration_profile.json"
    report_path = directory / "registration_report.md"
    json_path.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(render_registration_report(profile), encoding="utf-8")
    return json_path, report_path


def render_registration_report(profile: dict[str, Any]) -> str:
    lines = [
        f"# ML Platform Registration Report - {profile['project_name']}",
        "",
        f"- Scanned: {profile['scanned_at']}",
        f"- Project Path: {profile['project_path']}",
        f"- Python Version: {profile['python_version']}",
        f"- Frameworks: {', '.join(profile['frameworks'])}",
        f"- Default Entrypoint: {profile.get('default_entrypoint') or 'not found'}",
        "",
        "## Requirements",
        "",
    ]
    lines.extend([f"- {item}" for item in profile.get("requirements", [])] or ["- not found"])
    lines.extend(["", "## Config Files", ""])
    lines.extend([f"- {item}" for item in profile.get("configs", [])] or ["- not found"])
    lines.extend(["", "## Model Files", ""])
    lines.extend([f"- {item}" for item in profile.get("model_files", [])] or ["- not found"])
    lines.extend(["", "## MLFlow", ""])
    lines.append(f"- Tracking URI: {profile['mlflow'].get('tracking_uri') or 'not configured'}")
    lines.append(f"- Experiment Name: {profile['mlflow'].get('experiment_name')}")
    lines.extend(["", "## Job Template", ""])
    for key, value in profile.get("job_template", {}).items():
        lines.append(f"- {key}: {value or 'not configured'}")
    lines.extend(["", "## Warnings", ""])
    lines.extend([f"- {item}" for item in profile.get("warnings", [])] or ["- none"])
    lines.append("")
    return "\n".join(lines)


def render_mlflow_config(profile: dict[str, Any]) -> str:
    tracking_uri = profile["mlflow"].get("tracking_uri", "")
    experiment_name = profile["mlflow"].get("experiment_name", profile["project_name"])
    return "\n".join(
        [
            f"tracking_uri: \"{tracking_uri}\"",
            f"experiment_name: \"{experiment_name}\"",
            "registry_uri: \"\"",
            "artifact_location: \"\"",
            "",
        ]
    )


def render_job_template(profile: dict[str, Any]) -> str:
    job = profile.get("job_template", {})
    return "\n".join(
        [
            f"name: \"{profile['project_name']}-train\"",
            f"queue: \"{job.get('queue', '')}\"",
            "image: \"\"",
            "command: \"python entrypoint.py\"",
            f"args: \"{job.get('arguments', '')}\"",
            "resources:",
            f"  cpu: {job.get('cpu', 4)}",
            f"  gpu: {job.get('gpu', 1)}",
            f"  memory: \"{job.get('memory', '16Gi')}\"",
            "env:",
            "  MLFLOW_TRACKING_URI: \"${MLFLOW_TRACKING_URI}\"",
            "",
        ]
    )


def render_entrypoint(profile: dict[str, Any]) -> str:
    target = profile.get("default_entrypoint", "")
    if target.endswith(".ipynb"):
        original = (Path(profile["project_path"]) / target).as_posix()
        body = [
            "print('Notebook entrypoint detected.')",
            f"print('Convert or execute notebook manually before platform registration: {original}')",
            "raise SystemExit(1)",
        ]
    elif target:
        original = (Path(profile["project_path"]) / target).as_posix()
        body = [
            "import runpy",
            f"runpy.run_path({original!r}, run_name='__main__')",
        ]
    else:
        body = [
            "raise SystemExit('No train entrypoint was detected. Update entrypoint.py before submitting the job.')",
        ]
    return "\n".join(["# Auto-generated wrapper. Original project is not modified.", *body, ""])


def render_run_train(profile: dict[str, Any]) -> str:
    return "\n".join(
        [
            "$ErrorActionPreference = \"Stop\"",
            "$env:MLFLOW_TRACKING_URI = $env:MLFLOW_TRACKING_URI",
            "python entrypoint.py",
            "",
        ]
    )


def render_registered_readme(profile: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# Registered Workspace - {profile['project_name']}",
            "",
            "이 폴더는 ML Platform 등록을 위해 자동 생성된 표준 구조입니다.",
            "원본 프로젝트는 수정하지 않습니다.",
            "",
            "## Files",
            "",
            "- `mlflow_config.yaml`: MLFlow 설정 초안",
            "- `job_template.yaml`: ML Platform Job Template 초안",
            "- `entrypoint.py`: 원본 학습 스크립트를 호출하는 래퍼",
            "- `run_train.ps1`: Windows PowerShell 실행 확인 스크립트",
            "- `requirements.lock.txt`: 감지된 requirements 복사본 또는 후보 목록",
            "",
            "## Next Steps",
            "",
            "1. `mlflow_config.yaml`의 tracking URI를 확인합니다.",
            "2. `job_template.yaml`의 queue, image, CPU/GPU, memory를 확인합니다.",
            "3. `python entrypoint.py`로 로컬 실행 가능성을 확인합니다.",
            "4. 내부 ML Platform API 스펙이 확정되면 등록 Tool과 연결합니다.",
            "",
        ]
    )


def scaffold_registered_workspace(project_path: str) -> dict[str, Any]:
    profile = scan_project(project_path)
    save_registration_profile(profile)
    project_root = safe_project_path(project_path)
    target_dir = registered_workspace_dir() / slugify(profile["project_name"], "project")
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "README.md").write_text(render_registered_readme(profile), encoding="utf-8")
    (target_dir / "mlflow_config.yaml").write_text(render_mlflow_config(profile), encoding="utf-8")
    (target_dir / "job_template.yaml").write_text(render_job_template(profile), encoding="utf-8")
    (target_dir / "entrypoint.py").write_text(render_entrypoint(profile), encoding="utf-8")
    (target_dir / "run_train.ps1").write_text(render_run_train(profile), encoding="utf-8")
    write_requirements_lock(project_root, profile, target_dir)
    return {"profile": profile, "workspace": target_dir.as_posix(), "files": sorted(path.name for path in target_dir.iterdir())}


def write_requirements_lock(project_root: Path, profile: dict[str, Any], target_dir: Path) -> None:
    output = target_dir / "requirements.lock.txt"
    for rel in profile.get("requirements", []):
        if rel.endswith("requirements.txt"):
            source = project_root / rel
            if source.exists():
                shutil.copyfile(source, output)
                return
    lines = ["# No requirements.txt was found.", "# Candidate dependency files:"]
    lines.extend(profile.get("requirements", []) or ["# none"])
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
