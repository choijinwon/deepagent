import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from ops_common import slugify


def fix_report_dir() -> Path:
    return Path(os.getenv("FIX_REPORT_DIR", "fix_reports")).resolve()


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def retest_command_for(findings: list[dict[str, Any]]) -> str:
    finding_types = {str(item.get("type", "")) for item in findings}
    if "missing_package" in finding_types:
        for finding in findings:
            if finding.get("type") != "missing_package":
                continue
            match = re.search(r"No module named ['\"]([^'\"]+)['\"]", str(finding.get("evidence", "")))
            if match:
                return f"python -c \"import {match.group(1)}; print('import OK')\""
        return "python -c \"import <missing_package>; print('import OK')\""
    if "missing_file" in finding_types or "entrypoint_args" in finding_types:
        return "python entrypoint.py"
    if "mlflow_config" in finding_types:
        return "python -c \"import mlflow; print(mlflow.get_tracking_uri())\""
    if "gpu_memory" in finding_types or "job_resource" in finding_types or "image_runtime" in finding_types:
        return "AI Studio Job 재실행 후 새 로그를 저장하세요."
    if "permission" in finding_types:
        return "권한/서비스 계정 수정 후 동일 Job을 재실행하세요."
    return "동일 명령 또는 동일 AI Studio Job을 재실행하세요."


def analyze_log_text(log_text: str, *, source_name: str = "job-log") -> dict[str, Any]:
    findings = []
    lower_log = log_text.lower()
    module_match = re.search(r"ModuleNotFoundError:\s+No module named ['\"]([^'\"]+)['\"]", log_text)
    if module_match:
        module = module_match.group(1)
        findings.append(
            {
                "type": "missing_package",
                "severity": "high",
                "evidence": module_match.group(0),
                "cause": f"Python package `{module}` is missing in the job runtime.",
                "recommendation": f"Add `{module}` to requirements.lock.txt or the platform image, then rebuild the offline package bundle.",
                "patch_candidate": f"requirements.lock.txt\n+{module}\n",
            }
        )

    file_match = re.search(r"FileNotFoundError:.*No such file or directory: ['\"]([^'\"]+)['\"]", log_text)
    if file_match:
        missing = file_match.group(1)
        findings.append(
            {
                "type": "missing_file",
                "severity": "high",
                "evidence": file_match.group(0),
                "cause": f"The job cannot find `{missing}` from its current working directory.",
                "recommendation": "Check job_template.yaml working directory, mounted paths, config path arguments, and relative path assumptions.",
                "patch_candidate": "job_template.yaml\n# Verify command args and working directory for the missing file path.\n",
            }
        )

    if "cuda out of memory" in lower_log or "outofmemoryerror" in lower_log:
        findings.append(
            {
                "type": "gpu_memory",
                "severity": "high",
                "evidence": "CUDA out of memory",
                "cause": "GPU memory is insufficient for the current batch/model configuration.",
                "recommendation": "Reduce batch size, enable gradient checkpointing, use mixed precision, or request a larger GPU resource.",
                "patch_candidate": "job_template.yaml\nresources:\n  gpu: 1\n  memory: \"32Gi\"\n",
            }
        )

    if "mlflow" in lower_log and any(token in lower_log for token in ["tracking uri", "connection", "refused", "not found", "unauthorized"]):
        findings.append(
            {
                "type": "mlflow_config",
                "severity": "medium",
                "evidence": "MLFlow tracking/config error",
                "cause": "MLFlow tracking URI, authentication, experiment, or network route may be misconfigured.",
                "recommendation": "Verify MLFLOW_TRACKING_URI, experiment name, internal DNS/port, and platform service account permissions.",
                "patch_candidate": "mlflow_config.yaml\ntracking_uri: \"${MLFLOW_TRACKING_URI}\"\n",
            }
        )

    if any(token in lower_log for token in ["insufficient", "resource", "quota", "gpu not available", "pending"]):
        findings.append(
            {
                "type": "job_resource",
                "severity": "medium",
                "evidence": "resource scheduling or quota hint",
                "cause": "Job Template resource request may not match available ML Platform capacity.",
                "recommendation": "Check queue, GPU count/type, CPU, memory, and quota. Try a smaller resource profile for validation.",
                "patch_candidate": "job_template.yaml\nqueue: \"<available-queue>\"\nresources:\n  cpu: 4\n  gpu: 1\n  memory: \"16Gi\"\n",
            }
        )

    if any(
        token in lower_log
        for token in [
            "imagepullbackoff",
            "errimagepull",
            "no such image",
            "exec format error",
            "python: command not found",
            "command not found",
            "glibc",
            "libcudart",
            "cuda version",
            "driver version is insufficient",
        ]
    ):
        findings.append(
            {
                "type": "image_runtime",
                "severity": "high",
                "evidence": "image/runtime compatibility hint",
                "cause": "AI Studio image, Python runtime, CUDA runtime, or system library may not match the job requirements.",
                "recommendation": "Verify image name, Python version, CUDA/runtime compatibility, and required system libraries.",
                "patch_candidate": "job_template.yaml\nimage: \"<verified-ai-studio-image>\"\n",
            }
        )

    if any(token in lower_log for token in ["permission denied", "access denied", "forbidden", " 403 ", "not authorized", "service account"]):
        findings.append(
            {
                "type": "permission",
                "severity": "high",
                "evidence": "permission or service-account error",
                "cause": "The job may not have permission to read datasets, write artifacts, access MLflow, or use the requested resource.",
                "recommendation": "Check dataset permissions, artifact path permissions, MLflow permissions, and AI Studio service account mapping.",
                "patch_candidate": "",
            }
        )

    arg_match = re.search(r"(the following arguments are required: .+|unrecognized arguments: .+)", log_text, re.IGNORECASE)
    if arg_match:
        findings.append(
            {
                "type": "entrypoint_args",
                "severity": "medium",
                "evidence": arg_match.group(1),
                "cause": "The entrypoint command is missing required arguments or includes unsupported arguments.",
                "recommendation": "Update job_template.yaml args or entrypoint.py wrapper to match the training script CLI.",
                "patch_candidate": "job_template.yaml\nargs: \"<required-arguments>\"\n",
            }
        )

    if not findings:
        findings.append(
            {
                "type": "unknown",
                "severity": "info",
                "evidence": "No known pattern matched.",
                "cause": "The log does not match the first-pass Auto Fix rules.",
                "recommendation": "Attach the full job log, generated job_template.yaml, mlflow_config.yaml, and registration_report.md for deeper analysis.",
                "patch_candidate": "",
            }
        )

    return {
        "source": source_name,
        "created_at": now_text(),
        "findings": findings,
        "retest_command": retest_command_for(findings),
    }


def analyze_log_file(path: str) -> dict[str, Any]:
    log_path = Path(path).expanduser()
    if not log_path.is_absolute():
        log_path = (Path.cwd() / log_path).resolve()
    if not log_path.exists() or not log_path.is_file():
        raise FileNotFoundError(f"log file not found: {log_path}")
    return analyze_log_text(log_path.read_text(encoding="utf-8", errors="ignore"), source_name=log_path.name)


def render_fix_report(report: dict[str, Any]) -> str:
    lines = [
        f"# Auto Fix Plan - {report['source']}",
        "",
        f"- Created: {report['created_at']}",
        f"- Retest Command: {report.get('retest_command') or '동일 명령 또는 동일 AI Studio Job을 재실행하세요.'}",
        "",
        "## Findings",
        "",
    ]
    for index, finding in enumerate(report.get("findings", []), start=1):
        lines.extend(
            [
                f"### {index}. {finding['type']} ({finding['severity']})",
                "",
                f"- Evidence: {finding['evidence']}",
                f"- Cause: {finding['cause']}",
                f"- Recommendation: {finding['recommendation']}",
                "",
            ]
        )
        if finding.get("patch_candidate"):
            lines.extend(["```text", finding["patch_candidate"].rstrip(), "```", ""])
    if report.get("context"):
        lines.extend(["", "## Context", ""])
        for key, value in report["context"].items():
            lines.append(f"- {key}: {value or 'not provided'}")
    return "\n".join(lines)


def save_fix_report(report: dict[str, Any]) -> Path:
    directory = fix_report_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{slugify(report['source'], 'log')}-fix-plan.md"
    path.write_text(render_fix_report(report), encoding="utf-8")
    return path
