import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import load_dotenv


REQUIRED_IMPORTS = [
    "deepagents",
    "langchain_openai",
    "langchain_core",
    "langgraph",
    "pydantic",
    "dotenv",
    "httpx",
    "requests",
]


def status_line(ok: bool, label: str, detail: str = "") -> str:
    marker = "OK" if ok else "FAIL"
    suffix = f" - {detail}" if detail else ""
    return f"[{marker}] {label}{suffix}"


def normalize_models_url(base_url: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/v1"):
        return f"{base}/models"
    return f"{base}/v1/models"


def check_imports() -> list[str]:
    lines = ["## Python Packages"]
    for module_name in REQUIRED_IMPORTS:
        try:
            __import__(module_name)
            lines.append(status_line(True, module_name))
        except Exception as exc:
            lines.append(status_line(False, module_name, str(exc)))
    return lines


def check_env() -> list[str]:
    lines = ["## Environment"]
    env_path = Path(".env")
    lines.append(status_line(env_path.exists(), ".env file", str(env_path.resolve()) if env_path.exists() else "missing"))

    api_key = os.getenv("QWEN_API_KEY", "")
    base_url = os.getenv("QWEN_BASE_URL", "")
    model = os.getenv("QWEN_MODEL", "")
    models = os.getenv("QWEN_MODELS", "")

    lines.append(status_line(bool(api_key), "QWEN_API_KEY", "configured" if api_key else "missing"))
    lines.append(status_line(bool(base_url), "QWEN_BASE_URL", base_url or "missing"))
    lines.append(status_line(base_url.rstrip("/").endswith("/v1") if base_url else False, "QWEN_BASE_URL ends with /v1"))
    lines.append(status_line(bool(model), "QWEN_MODEL", model or "missing"))
    lines.append(status_line(bool(models), "QWEN_MODELS", models or "missing"))
    return lines


def check_models_endpoint() -> list[str]:
    lines = ["## OpenAI Compatible API"]
    base_url = os.getenv("QWEN_BASE_URL", "")
    api_key = os.getenv("QWEN_API_KEY", "")
    if not base_url:
        lines.append(status_line(False, "/v1/models", "QWEN_BASE_URL missing"))
        return lines

    url = normalize_models_url(base_url)
    request = urllib.request.Request(url)
    if api_key:
        request.add_header("Authorization", f"Bearer {api_key}")

    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            body = response.read().decode("utf-8", errors="replace")
            lines.append(status_line(True, "/v1/models", f"HTTP {response.status}"))
            try:
                data = json.loads(body)
                model_ids = [str(item.get("id")) for item in data.get("data", []) if isinstance(item, dict)]
                if model_ids:
                    lines.append(f"Models: {', '.join(model_ids[:20])}")
                else:
                    lines.append("Models: response parsed but no data[].id values found")
            except Exception:
                lines.append("Models: response was not JSON")
    except urllib.error.HTTPError as exc:
        lines.append(status_line(False, "/v1/models", f"HTTP {exc.code}: {exc.reason}"))
    except Exception as exc:
        lines.append(status_line(False, "/v1/models", str(exc)))
    return lines


def check_tool_calling_hint() -> list[str]:
    lines = ["## Tool Calling Readiness"]
    lines.append("DeepAgents requires a LangChain chat model that supports tool calling.")
    lines.append("If agent execution fails with tool/function errors, verify vLLM OpenAI tool calling settings for qwen3.5/gpt20/gamma.")
    lines.append("Recommended quick test: run `python chat_cli.py`, then `/test`, then ask for a TODO using the registered internal tool.")
    return lines


def run_doctor() -> list[str]:
    load_dotenv()
    lines = [
        "# DeepAgents Closed-Network Doctor",
        f"Python: {sys.version.split()[0]}",
        f"Working Directory: {Path.cwd()}",
        "",
    ]
    for block in (check_imports(), check_env(), check_models_endpoint(), check_tool_calling_hint()):
        lines.extend(block)
        lines.append("")
    return lines


def main() -> None:
    print("\n".join(run_doctor()))


if __name__ == "__main__":
    main()
