import os

from deepagents import create_deep_agent
from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI


def build_kwan_llm() -> ChatOpenAI:
    load_dotenv()

    api_key = os.getenv("KWAN_API_KEY")
    base_url = os.getenv("KWAN_BASE_URL")
    model_name = os.getenv("KWAN_MODEL", "kwan-model-name")

    if not api_key:
        raise ValueError("KWAN_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요.")
    if not base_url:
        raise ValueError("KWAN_BASE_URL이 설정되지 않았습니다. .env 파일을 확인하세요.")

    return ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=base_url,
        temperature=0.2,
    )


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
내부 Kwan API와 등록된 사내 Tool만 사용한다.
결과는 업무자가 바로 사용할 수 있게 TODO, 체크리스트, 보고서 형식으로 작성한다.
"""


def build_agent():
    kwan_llm = build_kwan_llm()
    return create_deep_agent(
        model=kwan_llm,
        tools=[make_security_todo],
        instructions=INSTRUCTIONS,
    )


def main() -> None:
    agent = build_agent()

    print("[폐쇄망 안전 모드] 딥에이전트가 내부 Kwan API와 통신을 시작합니다...")

    try:
        result = agent.invoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": "서버 접근권한 보안 점검 TODO 만들어줘.",
                    }
                ]
            }
        )

        print("\nKwan 에이전트 실행 결과:")
        print(result)

    except Exception as exc:
        print("\n연결 실패: Kwan API 주소나 모델명을 확인하세요.")
        print(f"오류 내용: {exc}")
if __name__ == "__main__":
    main()
