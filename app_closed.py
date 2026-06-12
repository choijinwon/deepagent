import os
from pathlib import Path
from typing import Any

from deepagents import create_deep_agent
from env_common import is_placeholder_value, load_project_env
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI


DEFAULT_MODELS = ["qwen3.5", "gpt20", "gamma"]
SKILLS_ROOT = Path(__file__).resolve().parent / "skills"
SKILL_SOURCE = "/skills/"


def get_available_models() -> list[str]:
    load_project_env()

    raw_models = os.getenv("QWEN_MODELS", ",".join(DEFAULT_MODELS))
    models = [model.strip() for model in raw_models.split(",") if model.strip()]
    default_model = os.getenv("QWEN_MODEL")
    if default_model and default_model not in models:
        models.insert(0, default_model)
    return models or DEFAULT_MODELS


def get_default_model() -> str:
    load_project_env()
    return os.getenv("QWEN_MODEL") or get_available_models()[0]


def deepagent_messages_mode() -> str:
    load_project_env()
    mode = os.getenv("DEEPAGENT_MESSAGES_MODE", "string").strip().lower()
    return mode if mode in ("string", "list") else "string"


def normalize_chat_messages(messages: list[dict[str, str]] | list | str) -> list[dict[str, str]]:
    if isinstance(messages, str):
        return [{"role": "user", "content": messages}]
    normalized = []
    for item in messages or []:
        if isinstance(item, dict):
            role = str(item.get("role") or "user")
            content = str(item.get("content") or "")
        else:
            role = str(getattr(item, "type", "") or getattr(item, "role", "") or "user")
            content = str(getattr(item, "content", item) or "")
        if content:
            normalized.append({"role": role, "content": content})
    return normalized


def messages_to_transcript(messages: list[dict[str, str]] | list | str) -> str:
    normalized = normalize_chat_messages(messages)
    lines = []
    for message in normalized:
        role = str(message.get("role") or "user")
        content = str(message.get("content") or "")
        lines.append(f"{role}:\n{content}")
    return "\n\n".join(lines).strip()


def build_agent_request(messages: list[dict[str, str]] | list | str, files: dict[str, str] | None = None) -> dict[str, Any]:
    return build_agent_request_for_mode(messages, files, deepagent_messages_mode())


def build_agent_request_for_mode(
    messages: list[dict[str, str]] | list | str,
    files: dict[str, str] | None = None,
    mode: str = "string",
) -> dict[str, Any]:
    if mode == "list":
        request_messages: str | list[dict[str, str]] = normalize_chat_messages(messages)
    else:
        request_messages = messages_to_transcript(messages)
    return {
        "messages": request_messages,
        "files": files or {},
    }


def opposite_messages_mode(mode: str) -> str:
    return "list" if mode == "string" else "string"


def is_message_format_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return (
        "string indices must be integers" in text
        or "list indices must be integers" in text
        or "message" in text and "content" in text and "dict" in text
    )


def build_alternate_agent_request(request: dict[str, Any]) -> dict[str, Any]:
    files = dict(request.get("files") or {})
    messages = request.get("messages", "")
    if isinstance(messages, str):
        return build_agent_request_for_mode(messages, files, "list")
    return build_agent_request_for_mode(messages, files, "string")


def invoke_agent_compatible(agent, messages: list[dict[str, str]] | list | str, files: dict[str, str] | None = None):
    mode = deepagent_messages_mode()
    request = build_agent_request_for_mode(messages, files, mode)
    try:
        return agent.invoke(request)
    except Exception as exc:
        if not is_message_format_error(exc):
            raise
        return agent.invoke(build_agent_request_for_mode(messages, files, opposite_messages_mode(mode)))


def build_qwen_llm(model_name: str | None = None) -> ChatOpenAI:
    load_project_env()

    api_key = os.getenv("QWEN_API_KEY")
    base_url = os.getenv("QWEN_BASE_URL")
    selected_model = model_name or get_default_model()

    if is_placeholder_value(api_key):
        raise ValueError("QWEN_API_KEY가 비어 있거나 예시값입니다. `deepagent-env setup`으로 실제 API Key를 입력하세요.")
    if is_placeholder_value(base_url):
        raise ValueError("QWEN_BASE_URL이 비어 있거나 예시값입니다. `deepagent-env setup`으로 실제 /v1 주소를 입력하세요.")

    return ChatOpenAI(
        model=selected_model,
        api_key=api_key,
        base_url=base_url,
        temperature=0.2,
    )


def harness_skills_enabled() -> bool:
    load_project_env()
    return os.getenv("ENABLE_HARNESS_SKILLS", "true").lower() in ("1", "true", "yes", "y")


def get_harness_skill_sources() -> list[str] | None:
    return [SKILL_SOURCE] if harness_skills_enabled() else None


def get_harness_skill_files() -> dict[str, str]:
    if not harness_skills_enabled() or not SKILLS_ROOT.exists():
        return {}

    skill_files = {}
    for skill_file in sorted(SKILLS_ROOT.glob("*/SKILL.md")):
        virtual_path = f"/skills/{skill_file.parent.name}/SKILL.md"
        skill_files[virtual_path] = skill_file.read_text(encoding="utf-8")
    return skill_files


def get_harness_skill_names() -> list[str]:
    if not harness_skills_enabled() or not SKILLS_ROOT.exists():
        return []
    return sorted(path.parent.name for path in SKILLS_ROOT.glob("*/SKILL.md"))


@tool
def make_security_todo(topic: str) -> str:
    """사내 보안 점검 TODO를 생성한다."""
    return f"""
[{topic}] 보안 점검 TODO

1. 점검 대상 시스템 확인
2. 접근 권한 확인
3. 로그 수집 여부 확인
4. 취약점 조치 이력 확인
5. 담당자 확인
6. 최종 보고서 작성
"""


INSTRUCTIONS = """
너는 폐쇄망 내부에서 동작하는 사내 AI Agent다.
외부 인터넷, 외부 API, 웹 검색 도구는 절대 사용하지 않는다.
내부 Qwen 3.5 OpenAI 호환 API와 등록된 사내 Tool만 사용한다.
결과는 업무자가 바로 사용할 수 있게 TODO, 체크리스트, 보고서 형식으로 작성한다.
멀티에이전트 모드에서는 필요 시 task 도구로 전문 서브에이전트에게 분석을 위임한다.
"""


def build_subagents() -> list[dict[str, Any]]:
    skill_sources = get_harness_skill_sources()
    return [
        {
            "name": "security-checker",
            "description": "접근권한, 로그, 취약점 조치 여부를 기준으로 보안 점검 항목을 분석한다.",
            "system_prompt": """
너는 폐쇄망 내부 보안 점검 전문 서브에이전트다.
외부 인터넷과 외부 API는 사용하지 않는다.
점검 대상, 권한, 로그, 취약점 조치, 담당자 확인 관점으로 누락 항목을 찾아 체크리스트로 정리한다.
""",
            "tools": [make_security_todo],
            "skills": skill_sources or [],
        },
        {
            "name": "report-writer",
            "description": "보안 점검 결과를 업무자가 바로 사용할 수 있는 보고서와 TODO 형식으로 정리한다.",
            "system_prompt": """
너는 폐쇄망 내부 보고서 작성 전문 서브에이전트다.
외부 인터넷과 외부 API는 사용하지 않는다.
분석 내용을 요약, TODO, 담당자 확인 사항, 후속 조치 형식으로 명확하게 작성한다.
""",
            "tools": [make_security_todo],
            "skills": skill_sources or [],
        },
    ]


def build_agent(model_name: str | None = None, enable_multi_agent: bool = True):
    qwen_llm = build_qwen_llm(model_name)
    subagents = build_subagents() if enable_multi_agent else []
    return create_deep_agent(
        model=qwen_llm,
        tools=[make_security_todo],
        system_prompt=INSTRUCTIONS,
        subagents=subagents,
        skills=get_harness_skill_sources(),
    )


def main() -> None:
    model_name = get_default_model()
    enable_multi_agent = os.getenv("ENABLE_MULTI_AGENT", "true").lower() in ("1", "true", "yes", "y")
    agent = build_agent(model_name=model_name, enable_multi_agent=enable_multi_agent)

    print(f"[폐쇄망 안전 모드] 딥에이전트가 내부 Qwen API 모델({model_name})과 통신을 시작합니다...")
    print(f"멀티에이전트 모드: {'사용' if enable_multi_agent else '미사용'}")
    print(f"하네스 스킬: {', '.join(get_harness_skill_names()) or '미사용'}")

    try:
        result = invoke_agent_compatible(
            agent,
            "서버 접근권한 보안 점검 TODO 만들어줘.",
            get_harness_skill_files(),
        )

        print("\nQwen 3.5 에이전트 실행 결과:")
        print(result)

    except Exception as exc:
        print("\n연결 실패: Qwen 3.5 API 주소나 모델명을 확인하세요.")
        print(f"오류 내용: {exc}")


if __name__ == "__main__":
    main()
