# DeepAgents 폐쇄망 Kwan API 연동 PoC

폐쇄망 내부에서 OpenAI 호환 Kwan API 서버를 `deepagents`의 LLM 백엔드로 연결하는 PoC 예제입니다.
핵심은 `deepagents` 설치, Kwan OpenAI 호환 API 연결, 외부 Tool 제거, 내부 Tool만 등록입니다.

## 1. 외부 인터넷 PC에서 전체 소스 받기

인터넷이 되는 PC에서 아래 명령어를 실행합니다.

```powershell
git clone https://github.com/langchain-ai/deepagents.git
cd deepagents
```

DeepAgents 저장소와 별도로 이 PoC 파일도 함께 준비합니다.

## 2. 오프라인 패키지 묶음 만들기

폐쇄망 PC의 Python 버전과 외부 PC의 Python 버전을 맞추는 것을 권장합니다.

```powershell
python --version
```

외부 PC에서 wheel 패키지와 의존성을 다운로드합니다.

```powershell
mkdir offline_packages

pip download -d offline_packages `
  deepagents `
  langchain `
  langchain-openai `
  langchain-core `
  langgraph `
  python-dotenv `
  pydantic `
  requests `
  httpx
```

## 3. 폐쇄망으로 복사할 폴더

아래 항목을 USB 또는 사내 보안망을 통해 폐쇄망 PC로 복사합니다.

- `deepagents/`
- `offline_packages/`
- 이 PoC의 `app_closed.py`, `.env.example`, `requirements.txt`

## 4. 폐쇄망 PC에서 가상환경 생성

```powershell
cd deepagents

python -m venv .venv
.venv\Scripts\activate
```

## 5. 오프라인 설치

```powershell
pip install --no-index --find-links=..\offline_packages -r requirements.txt
```

설치를 확인합니다.

```powershell
python -c "import deepagents; print('deepagents import OK')"
python -c "import langchain_openai; print('langchain_openai import OK')"
```

## 6. 실행용 파일 생성

`app_closed.py`를 프로젝트 루트에 둡니다.

이 예제는 외부 검색 Tool을 연결하지 않고, 사내 보안 점검 TODO를 만드는 내부 Tool만 등록합니다.

```python
import os

from deepagents import create_deep_agent
from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

load_dotenv()

kwan_llm = ChatOpenAI(
    model=os.getenv("KWAN_MODEL", "kwan-model-name"),
    api_key=os.getenv("KWAN_API_KEY"),
    base_url=os.getenv("KWAN_BASE_URL"),
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


agent = create_deep_agent(
    model=kwan_llm,
    tools=[make_security_todo],
    instructions="""
너는 폐쇄망 내부 AI Agent다.
외부 인터넷, 외부 검색, 외부 API는 사용하지 않는다.
내부 Kwan API와 등록된 사내 Tool만 사용한다.
""",
)

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

print(result)
```

## 7. .env 생성

프로젝트 루트에서 `.env.example`을 복사해 `.env` 파일을 만듭니다.

```powershell
copy .env.example .env
```

`.env` 파일의 값을 사내 Kwan API 서버 정보에 맞게 수정합니다.

```ini
KWAN_API_KEY=your-internal-kwan-key
KWAN_BASE_URL=http://xxx.xxx.xxx.xxx:포트/v1
KWAN_MODEL=kwan-model-name
```

`KWAN_BASE_URL`에 `/v1`이 붙는지 반드시 확인하세요.

## 8. 실행

```powershell
python app_closed.py
```

## 실패 시 먼저 확인

패키지 import를 확인합니다.

```powershell
python -c "import langchain_openai; print('ok')"
python -c "import deepagents; print('ok')"
```

Kwan API 연결을 확인합니다.

```powershell
curl http://xxx.xxx.xxx.xxx:포트/v1/models
```

## 폐쇄망 구동 시 주의사항

- 외부 웹 검색 도구, 외부 SaaS API, 인터넷 기반 플러그인은 폐쇄망에서 실패할 수 있습니다.
- 사내 DB, 내부 API, 내부 파일 시스템 등 폐쇄망에서 접근 가능한 도구만 연결하세요.
- `create_deep_agent(model=kwan_llm)`만 쓰기보다 `tools`, `instructions`, `model`을 명시하는 방식이 폐쇄망 PoC에서 더 안전하고 명확합니다.
- `deepagents`의 계획 수립과 도구 호출이 정상 동작하려면 Kwan API 모델이 Tool Calling을 지원해야 합니다.
- Kwan API가 OpenAI 호환 `/v1/chat/completions` 형태를 지원하는지 확인하세요.
- 오류가 발생하면 Kwan 서버의 `base_url`, API Key, 모델명, Tool Calling 활성화 여부를 먼저 확인하세요.

## Git 업로드 전 확인

`.env` 파일은 민감 정보가 포함되므로 Git에 올리지 않습니다. `.gitignore`에 이미 제외되어 있습니다.
