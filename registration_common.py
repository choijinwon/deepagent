import json
import os
import shutil
import zipfile
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

FRAMEWORK_PROFILES = {
    "huggingface": {
        "project_type": "huggingface-transformers",
        "execution_hint": "transformers/accelerate 기반 학습 후보입니다. tokenizer, model path, config, dataset 경로를 Job args로 명시하세요.",
        "gpu": 1,
        "cpu": 8,
        "memory": "32Gi",
        "template": "templates/huggingface/job_template.yaml",
    },
    "pytorch": {
        "project_type": "pytorch-training",
        "execution_hint": "PyTorch 학습 스크립트 후보입니다. CUDA 사용 여부와 batch size를 검증하세요.",
        "gpu": 1,
        "cpu": 8,
        "memory": "24Gi",
        "template": "templates/pytorch/job_template.yaml",
    },
    "tensorflow": {
        "project_type": "tensorflow-keras-training",
        "execution_hint": "TensorFlow/Keras 학습 후보입니다. GPU memory growth, SavedModel/H5 출력 경로를 확인하세요.",
        "gpu": 1,
        "cpu": 8,
        "memory": "24Gi",
        "template": "templates/tensorflow/job_template.yaml",
    },
    "xgboost": {
        "project_type": "xgboost-training",
        "execution_hint": "XGBoost 학습 후보입니다. GPU histogram 사용이 없으면 CPU 중심 Job으로 등록할 수 있습니다.",
        "gpu": 0,
        "cpu": 8,
        "memory": "16Gi",
        "template": "templates/xgboost/job_template.yaml",
    },
    "sklearn": {
        "project_type": "sklearn-training",
        "execution_hint": "Scikit-learn 학습 후보입니다. 일반적으로 CPU Job으로 시작하고 데이터 크기에 따라 memory를 조정하세요.",
        "gpu": 0,
        "cpu": 4,
        "memory": "16Gi",
        "template": "templates/sklearn/job_template.yaml",
    },
    "notebook": {
        "project_type": "notebook-only",
        "execution_hint": "Notebook 중심 프로젝트입니다. 플랫폼 등록 전 notebook을 스크립트로 변환하거나 papermill 실행 방식을 확정하세요.",
        "gpu": 0,
        "cpu": 4,
        "memory": "16Gi",
        "template": "templates/notebook/job_template.yaml",
    },
    "legacy-script": {
        "project_type": "legacy-script",
        "execution_hint": "프레임워크가 명확하지 않은 legacy script입니다. 실행 파일, working directory, config path를 수동 확인하세요.",
        "gpu": 0,
        "cpu": 4,
        "memory": "8Gi",
        "template": "templates/legacy/job_template.yaml",
    },
}

CONFIG_SUFFIXES = {".yaml", ".yml", ".json", ".toml", ".ini", ".cfg"}
MODEL_SUFFIXES = {".pt", ".pth", ".ckpt", ".bin", ".safetensors", ".pkl", ".joblib", ".onnx", ".h5"}
ENTRYPOINT_NAMES = ["train.py", "main.py", "run.py", "fit.py", "trainer.py"]


def registration_dir() -> Path:
    return Path(os.getenv("REGISTRATION_DIR", "registrations")).resolve()


def registered_workspace_dir() -> Path:
    return Path(os.getenv("REGISTERED_WORKSPACE_DIR", "agent_workspace/registered")).resolve()


def registration_package_dir() -> Path:
    return Path(os.getenv("REGISTRATION_PACKAGE_DIR", "registration_packages")).resolve()


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
    ignored = {
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        "node_modules",
        "agent_workspace",
        "dev_runs",
        "dev_sessions",
        "dev_patches",
        "experiments",
        "fix_reports",
        "goals",
        "offline_bundle",
        "offline_packages",
        "plans",
        "registrations",
        "sessions",
        "outputs",
        "work",
        "wiki_logs",
    }
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


def detect_environment_files(project_root: Path, files: list[Path]) -> dict[str, list[str]]:
    groups = {
        "pip": {"requirements.txt", "requirements-dev.txt", "constraints.txt"},
        "python_project": {"pyproject.toml", "setup.py", "setup.cfg"},
        "conda": {"environment.yml", "environment.yaml", "conda.yaml"},
        "docker": {"dockerfile"},
        "lock": {"poetry.lock", "pdm.lock", "uv.lock", "pipfile.lock"},
        "notebook": set(),
    }
    detected: dict[str, list[str]] = {key: [] for key in groups}
    for path in files:
        rel = path.relative_to(project_root).as_posix()
        lower = path.name.lower()
        for group, names in groups.items():
            if group == "notebook":
                continue
            if lower in names:
                detected[group].append(rel)
        if path.suffix.lower() == ".ipynb":
            detected["notebook"].append(rel)
    return {key: sorted(value) for key, value in detected.items() if value}


def detect_execution_arguments(project_root: Path, entrypoints: list[str]) -> dict[str, Any]:
    if not entrypoints:
        return {"style": "unknown", "arguments": "", "hints": ["실행 파일 후보가 없어 arguments를 추정하지 못했습니다."]}
    entrypoint = project_root / entrypoints[0]
    content = read_small_text(entrypoint)
    hints = []
    args = []
    if "argparse" in content:
        hints.append("argparse 사용 감지")
        for line in content.splitlines():
            stripped = line.strip()
            if ".add_argument(" not in stripped:
                continue
            quote = '"' if '"' in stripped else "'"
            parts = stripped.split(quote)
            if len(parts) >= 2 and parts[1].startswith("--"):
                args.append(parts[1])
    if "click.command" in content or "@click.option" in content:
        hints.append("click CLI 사용 감지")
    if "hydra" in content.lower():
        hints.append("Hydra config 사용 가능성")
    if "yaml" in content.lower() or ".yml" in content.lower():
        hints.append("YAML config 인자 가능성")
    if not hints:
        hints.append("명시적 CLI parser를 찾지 못했습니다.")
    argument_hint = " ".join(f"{arg} <value>" for arg in args[:8])
    return {"style": "script", "arguments": argument_hint, "hints": hints, "detected_options": args[:20]}


def choose_primary_framework(frameworks: list[str]) -> str:
    for candidate in ("huggingface", "pytorch", "tensorflow", "xgboost", "sklearn", "notebook", "legacy-script"):
        if candidate in frameworks:
            return candidate
    return frameworks[0] if frameworks else "legacy-script"


def recommend_resources(frameworks: list[str], files: list[Path]) -> dict[str, Any]:
    primary = choose_primary_framework(frameworks)
    profile = FRAMEWORK_PROFILES.get(primary, FRAMEWORK_PROFILES["legacy-script"])
    gpu = int(os.getenv("ML_PLATFORM_DEFAULT_GPU", str(profile["gpu"])) or profile["gpu"])
    cpu = int(os.getenv("ML_PLATFORM_DEFAULT_CPU", str(profile["cpu"])) or profile["cpu"])
    memory = os.getenv("ML_PLATFORM_DEFAULT_MEMORY", profile["memory"]) or profile["memory"]
    model_size_bytes = sum(path.stat().st_size for path in files if path.suffix.lower() in MODEL_SUFFIXES)
    notes = [profile["execution_hint"]]
    if model_size_bytes > 5 * 1024 * 1024 * 1024:
        memory = "64Gi"
        notes.append("대형 모델 파일이 감지되어 memory 상향을 권장합니다.")
    if primary in ("xgboost", "sklearn", "legacy-script", "notebook") and gpu > 0:
        notes.append("기본 GPU 값이 설정되어 있지만 이 유형은 CPU Job으로도 시작 가능합니다.")
    return {
        "profile": primary,
        "gpu": gpu,
        "cpu": cpu,
        "memory": memory,
        "queue": os.getenv("ML_PLATFORM_DEFAULT_QUEUE", ""),
        "notes": notes,
    }


def build_framework_templates(frameworks: list[str]) -> list[dict[str, str]]:
    templates = []
    for framework in frameworks:
        profile = FRAMEWORK_PROFILES.get(framework)
        if not profile:
            continue
        templates.append(
            {
                "framework": framework,
                "project_type": profile["project_type"],
                "template": profile["template"],
                "guide": profile["execution_hint"],
            }
        )
    if not templates:
        profile = FRAMEWORK_PROFILES["legacy-script"]
        templates.append(
            {
                "framework": "legacy-script",
                "project_type": profile["project_type"],
                "template": profile["template"],
                "guide": profile["execution_hint"],
            }
        )
    return templates


def build_onboarding_guide(profile: dict[str, Any]) -> list[str]:
    primary = profile.get("project_type", "legacy-script")
    guide = [
        "원본 프로젝트는 수정하지 않고 등록용 workspace의 wrapper와 template만 수정합니다.",
        "등록 전 `run_train.ps1` 또는 `python entrypoint.py`로 실행 경로를 확인합니다.",
        "오류가 발생하면 Job log를 `/register fix-log <path>` 또는 `/dev fix-log <path>`에 넣어 수정 계획을 생성합니다.",
    ]
    if primary == "notebook-only":
        guide.insert(0, "Notebook-only 프로젝트는 스크립트 변환 또는 papermill 실행 방식 중 하나를 선택해야 합니다.")
    if primary == "legacy-script":
        guide.insert(0, "Legacy 프로젝트는 entrypoint, working directory, config path를 먼저 확정해야 합니다.")
    return guide


def check_result(status: str, title: str, detail: str, weight: int = 10) -> dict[str, Any]:
    return {"status": status, "title": title, "detail": detail, "weight": weight}


def find_closed_network_risks(project_root: Path, files: list[Path]) -> list[str]:
    risk_tokens = ("git+", "http://", "https://", "-e git", "pip install")
    risks = []
    for path in files:
        if path.suffix.lower() not in {".txt", ".toml", ".yml", ".yaml", ".cfg", ".ini", ".py", ".sh", ".ps1"}:
            continue
        content = read_small_text(path, limit=80_000).lower()
        if not content:
            continue
        if any(token in content for token in risk_tokens):
            risks.append(path.relative_to(project_root).as_posix())
    return sorted(set(risks))[:20]


def build_registration_readiness(project_root: Path, files: list[Path], profile: dict[str, Any]) -> dict[str, Any]:
    checks = []
    env_files = profile.get("environment_files", {})
    job = profile.get("job_template", {})
    execution = profile.get("execution", {})
    closed_network_risks = find_closed_network_risks(project_root, files)

    checks.append(
        check_result(
            "pass" if profile.get("default_entrypoint") else "fail",
            "학습 진입점",
            profile.get("default_entrypoint") or "train.py, main.py, run.py, notebook 후보를 찾지 못했습니다.",
            15,
        )
    )
    checks.append(
        check_result(
            "pass" if profile.get("requirements") else "fail",
            "환경 파일",
            ", ".join(profile.get("requirements") or []) or "requirements.txt, pyproject.toml, environment.yml 후보가 필요합니다.",
            15,
        )
    )
    checks.append(
        check_result(
            "warn" if profile.get("primary_framework") == "legacy-script" else "pass",
            "프레임워크 판별",
            profile.get("primary_framework") or "unknown",
            10,
        )
    )
    checks.append(
        check_result(
            "pass" if profile.get("mlflow", {}).get("tracking_uri") else "warn",
            "MLFlow Tracking URI",
            profile.get("mlflow", {}).get("tracking_uri") or "MLFLOW_TRACKING_URI가 비어 있습니다.",
            10,
        )
    )
    checks.append(
        check_result(
            "pass" if job.get("queue") else "warn",
            "Platform Queue",
            job.get("queue") or "ML_PLATFORM_DEFAULT_QUEUE가 비어 있습니다.",
            10,
        )
    )
    resource_ok = bool(job.get("cpu")) and bool(job.get("memory")) and job.get("gpu") is not None
    checks.append(
        check_result(
            "pass" if resource_ok else "fail",
            "CPU/GPU/Memory",
            f"cpu={job.get('cpu')}, gpu={job.get('gpu')}, memory={job.get('memory')}",
            10,
        )
    )
    args_status = "pass" if execution.get("detected_options") or profile.get("project_type") in ("notebook-only", "legacy-script") else "warn"
    checks.append(
        check_result(
            args_status,
            "실행 인자",
            execution.get("arguments") or "명시적 실행 인자를 감지하지 못했습니다. 데이터/config/model output 경로를 확인하세요.",
            10,
        )
    )
    notebook_status = "warn" if profile.get("project_type") == "notebook-only" else "pass"
    checks.append(
        check_result(
            notebook_status,
            "Notebook/Legacy 처리",
            "Notebook은 script 변환 또는 papermill 실행 방식 확정이 필요합니다." if notebook_status == "warn" else "추가 변환 필수 항목 없음",
            10,
        )
    )
    conda_only = "conda" in env_files and "pip" not in env_files
    checks.append(
        check_result(
            "warn" if conda_only else "pass",
            "폐쇄망 패키지 호환성",
            "Conda-only 환경입니다. pip wheel 번들 변환 가능성을 확인하세요." if conda_only else "pip/pyproject 기반 오프라인 번들 생성 가능",
            10,
        )
    )
    checks.append(
        check_result(
            "warn" if closed_network_risks else "pass",
            "외부 의존성 위험",
            ", ".join(closed_network_risks) if closed_network_risks else "외부 URL/git 설치 패턴을 찾지 못했습니다.",
            10,
        )
    )

    total_weight = sum(item["weight"] for item in checks)
    earned = 0.0
    for item in checks:
        if item["status"] == "pass":
            earned += item["weight"]
        elif item["status"] == "warn":
            earned += item["weight"] * 0.5
    score = round((earned / total_weight) * 100) if total_weight else 0
    if score >= 85 and not any(item["status"] == "fail" for item in checks):
        level = "ready"
    elif score >= 65:
        level = "needs-review"
    else:
        level = "blocked"
    return {
        "score": score,
        "level": level,
        "checks": checks,
        "summary": f"Registration Readiness: {score}/100 ({level})",
    }


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
    environment_files = detect_environment_files(project_root, files)
    execution = detect_execution_arguments(project_root, entrypoints)
    resource_recommendation = recommend_resources(frameworks, files)
    primary_framework = choose_primary_framework(frameworks)
    default_entrypoint = entrypoints[0] if entrypoints else (notebooks[0] if notebooks else "")
    profile = {
        "project_name": project_root.name,
        "project_path": project_root.as_posix(),
        "scanned_at": now_text(),
        "project_type": FRAMEWORK_PROFILES.get(primary_framework, FRAMEWORK_PROFILES["legacy-script"])["project_type"],
        "frameworks": frameworks,
        "primary_framework": primary_framework,
        "python_version": infer_python_version(),
        "entrypoints": entrypoints,
        "default_entrypoint": default_entrypoint,
        "execution": execution,
        "requirements": requirements,
        "environment_files": environment_files,
        "notebooks": notebooks[:20],
        "configs": configs[:30],
        "model_files": model_files[:30],
        "framework_templates": build_framework_templates(frameworks),
        "resource_recommendation": resource_recommendation,
        "mlflow": {
            "tracking_uri": os.getenv("MLFLOW_TRACKING_URI", ""),
            "experiment_name": project_root.name,
        },
        "job_template": {
            "queue": resource_recommendation["queue"],
            "gpu": resource_recommendation["gpu"],
            "cpu": resource_recommendation["cpu"],
            "memory": resource_recommendation["memory"],
            "entrypoint": default_entrypoint,
            "arguments": execution.get("arguments", ""),
        },
    }
    profile["onboarding_guide"] = build_onboarding_guide(profile)
    profile["warnings"] = build_warnings(default_entrypoint, requirements, frameworks, environment_files)
    profile["readiness"] = build_registration_readiness(project_root, files, profile)
    return profile


def build_warnings(
    default_entrypoint: str,
    requirements: list[str],
    frameworks: list[str],
    environment_files: dict[str, list[str]] | None = None,
) -> list[str]:
    warnings = []
    if not default_entrypoint:
        warnings.append("학습 실행 파일 또는 notebook 후보를 찾지 못했습니다.")
    if not requirements:
        warnings.append("requirements.txt, pyproject.toml, environment.yml 후보를 찾지 못했습니다.")
    if environment_files and "docker" in environment_files:
        warnings.append("Dockerfile이 감지되었습니다. 플랫폼에서 커스텀 이미지 사용 가능 여부를 확인하세요.")
    if environment_files and "conda" in environment_files and "pip" not in environment_files:
        warnings.append("Conda 환경 파일만 감지되었습니다. 폐쇄망 pip wheel 번들로 변환 가능한지 확인하세요.")
    if frameworks == ["legacy-script"]:
        warnings.append("명확한 ML framework import를 찾지 못해 legacy script로 분류했습니다.")
    if "notebook" in frameworks and not default_entrypoint.endswith(".ipynb"):
        warnings.append("Notebook이 감지되었습니다. 실제 학습 진입점이 script인지 notebook인지 확인하세요.")
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
        f"- Project Type: {profile.get('project_type', 'unknown')}",
        f"- Primary Framework: {profile.get('primary_framework', 'unknown')}",
        f"- Frameworks: {', '.join(profile['frameworks'])}",
        f"- Default Entrypoint: {profile.get('default_entrypoint') or 'not found'}",
        "",
        "## Registration Readiness",
        "",
        f"- Score: {profile.get('readiness', {}).get('score', 0)}/100",
        f"- Level: {profile.get('readiness', {}).get('level', 'unknown')}",
        "",
        "### Checklist",
        "",
    ]
    for item in profile.get("readiness", {}).get("checks", []):
        marker = {"pass": "[OK]", "warn": "[주의]", "fail": "[오류]"}.get(item.get("status"), "[정보]")
        lines.append(f"- {marker} {item.get('title')}: {item.get('detail')}")
    lines.extend(
        [
            "",
        "## Execution",
        "",
        f"- Style: {profile.get('execution', {}).get('style', 'unknown')}",
        f"- Arguments: {profile.get('execution', {}).get('arguments') or 'not detected'}",
        "",
        "### Execution Hints",
        "",
        ]
    )
    lines.extend([f"- {item}" for item in profile.get("execution", {}).get("hints", [])] or ["- none"])
    lines.extend(
        [
            "",
            "## Environment Files",
            "",
        ]
    )
    env_files = profile.get("environment_files", {})
    if env_files:
        for group, items in env_files.items():
            lines.append(f"### {group}")
            lines.extend([f"- {item}" for item in items])
            lines.append("")
    else:
        lines.append("- not found")
    lines.extend(
        [
            "",
            "## Framework Templates",
            "",
        ]
    )
    for item in profile.get("framework_templates", []):
        lines.extend(
            [
                f"### {item.get('framework')}",
                "",
                f"- Project Type: {item.get('project_type')}",
                f"- Template: {item.get('template')}",
                f"- Guide: {item.get('guide')}",
                "",
            ]
        )
    lines.extend(
        [
            "## Resource Recommendation",
            "",
        ]
    )
    resource = profile.get("resource_recommendation", {})
    lines.extend(
        [
            f"- Profile: {resource.get('profile', 'unknown')}",
            f"- Queue: {resource.get('queue') or 'not configured'}",
            f"- CPU: {resource.get('cpu')}",
            f"- GPU: {resource.get('gpu')}",
            f"- Memory: {resource.get('memory')}",
            "",
        ]
    )
    lines.extend([f"- {item}" for item in resource.get("notes", [])] or ["- none"])
    lines.extend(
        [
            "",
            "## Requirements",
            "",
        ]
    )
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
    lines.extend(["", "## Onboarding Guide", ""])
    lines.extend([f"{index}. {item}" for index, item in enumerate(profile.get("onboarding_guide", []), start=1)])
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
    primary = profile.get("primary_framework", "legacy-script")
    template_name = FRAMEWORK_PROFILES.get(primary, FRAMEWORK_PROFILES["legacy-script"]).get("template", "")
    return "\n".join(
        [
            f"name: \"{profile['project_name']}-train\"",
            f"project_type: \"{profile.get('project_type', 'legacy-script')}\"",
            f"framework: \"{profile.get('primary_framework', 'legacy-script')}\"",
            f"template_hint: \"{template_name}\"",
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
            "## Auto Detected Profile",
            "",
            f"- Project Type: {profile.get('project_type')}",
            f"- Primary Framework: {profile.get('primary_framework')}",
            f"- Registration Readiness: {profile.get('readiness', {}).get('score', 0)}/100 "
            f"({profile.get('readiness', {}).get('level', 'unknown')})",
            f"- Recommended CPU/GPU/Memory: {profile.get('job_template', {}).get('cpu')}/"
            f"{profile.get('job_template', {}).get('gpu')}/{profile.get('job_template', {}).get('memory')}",
            "",
            "## Onboarding Guide",
            "",
            *[f"{index}. {item}" for index, item in enumerate(profile.get("onboarding_guide", []), start=1)],
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


def create_registration_package(project_path: str) -> dict[str, Any]:
    scaffold = scaffold_registered_workspace(project_path)
    profile = scaffold["profile"]
    project_slug = slugify(profile["project_name"], "project")
    profile_dir = registration_dir() / project_slug
    workspace = Path(scaffold["workspace"])
    package_root = registration_package_dir()
    package_root.mkdir(parents=True, exist_ok=True)
    package_path = package_root / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{project_slug}-registration-package.zip"
    manifest = {
        "created_at": now_text(),
        "project_name": profile["project_name"],
        "project_path": profile["project_path"],
        "readiness": profile.get("readiness", {}),
        "workspace": workspace.as_posix(),
        "files": [],
    }

    with zipfile.ZipFile(package_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(profile_dir.glob("*")):
            if path.is_file():
                arcname = f"registration/{path.name}"
                archive.write(path, arcname)
                manifest["files"].append(arcname)
        for path in sorted(workspace.glob("*")):
            if path.is_file():
                arcname = f"registered_workspace/{path.name}"
                archive.write(path, arcname)
                manifest["files"].append(arcname)
        manifest["files"].append("registration_package_manifest.json")
        archive.writestr("registration_package_manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))

    return {
        "profile": profile,
        "workspace": workspace.as_posix(),
        "package_path": package_path.as_posix(),
        "files": manifest["files"],
        "readiness": profile.get("readiness", {}),
    }
