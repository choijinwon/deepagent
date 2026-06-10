# DeepAgents 폐쇄망 Qwen 3.5 API 연동 PoC

폐쇄망 내부에서 OpenAI 호환 Qwen 3.5 API 서버를 `deepagents`의 LLM 백엔드로 연결하는 PoC 예제입니다.
설치와 실행 명령은 Windows 11 Pro / PowerShell 기준입니다.

핵심은 다음 4가지입니다.

- 인터넷 다운로드는 외부 PC에서만 수행
- 폐쇄망 PC에는 소스와 wheel 패키지 묶음만 복사
- Qwen 3.5 OpenAI 호환 API를 `ChatOpenAI`의 `base_url`로 연결
- 외부 검색 Tool은 제거하고 사내 내부 Tool만 등록

## 폴더 구성

```text
deepagent/
├─ app_closed.py
├─ web_closed.py
├─ requirements.txt
├─ .env.example
├─ .gitignore
└─ scripts/
   ├─ prepare_external_pc.ps1
   ├─ build_offline_packages.ps1
   └─ install_offline.ps1
```

## 전체 흐름

```text
외부 인터넷 PC
1. 이 저장소 다운로드
2. 공식 langchain-ai/deepagents 소스 다운로드
3. offline_packages 폴더에 wheel 패키지 다운로드
4. offline_bundle 폴더를 USB/보안망으로 복사

폐쇄망 PC
5. Python 가상환경 생성
6. offline_packages만 사용해서 오프라인 설치
7. .env 작성
8. app_closed.py 또는 web_closed.py 실행
```

## 1. 외부 인터넷 PC에서 준비

인터넷이 되는 외부 PC에서 이 저장소를 받습니다.

```powershell
git clone https://github.com/choijinwon/deepagent.git
cd deepagent
```

폐쇄망 PC의 Python 버전과 외부 PC의 Python 버전을 맞추는 것을 권장합니다.

```powershell
python --version
```

오프라인 설치용 wheel 패키지를 다운로드합니다.
이 명령은 공식 `langchain-ai/deepagents` 저장소도 함께 클론하고, 폐쇄망 반입용 `offline_bundle` 폴더를 만듭니다.

```powershell
.\scripts\prepare_external_pc.ps1
```

공식 DeepAgents 소스는 아래 경로에 받아집니다.

```text
external_sources/deepagents/
```

폐쇄망으로 가져갈 최종 묶음은 아래 경로에 생성됩니다.

```text
offline_bundle/
├─ deepagent/
├─ offline_packages/
└─ deepagents_official_source/
```

wheel 패키지만 다시 받고 싶은 경우에는 아래 스크립트만 실행해도 됩니다.

```powershell
.\scripts\build_offline_packages.ps1
```

스크립트를 쓰지 않는 경우 아래 명령을 직접 실행해도 됩니다.

```powershell
mkdir offline_packages

pip download -d offline_packages -r requirements.txt
```

## 2. 폐쇄망 PC로 복사

아래 폴더를 통째로 폐쇄망 PC에 복사합니다.

- `offline_bundle/`

`offline_bundle` 안에는 실행용 PoC, 오프라인 wheel 패키지, 공식 DeepAgents 소스가 함께 들어 있습니다.

중요: 폐쇄망 PC에서는 `git clone`, `pip download`, 인터넷 기반 설치를 실행하지 않습니다.

## 3. 폐쇄망 PC에서 가상환경 생성

```powershell
cd offline_bundle\deepagent

python -m venv .venv
.venv\Scripts\activate
```

## 4. 폐쇄망 PC에서 오프라인 설치

`offline_packages` 폴더가 `offline_bundle` 아래에 있다고 가정합니다.

PowerShell 실행 정책 때문에 `.ps1` 실행이 막히면 현재 PowerShell 창에서만 아래 명령으로 임시 허용합니다.

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

```powershell
.\scripts\install_offline.ps1
```

스크립트를 쓰지 않는 경우 아래 명령을 직접 실행합니다.

```powershell
pip install --no-index --find-links=..\offline_packages -r requirements.txt
```

설치를 확인합니다.

```powershell
python -c "import deepagents; print('deepagents import OK')"
python -c "import langchain_openai; print('langchain_openai import OK')"
```

## 5. .env 생성

프로젝트 루트에서 `.env.example`을 복사해 `.env` 파일을 만듭니다.

```powershell
copy .env.example .env
```

`.env` 파일의 값을 사내 Qwen 3.5 API 서버 정보에 맞게 수정합니다.

```ini
QWEN_API_KEY=your-internal-qwen-key
QWEN_BASE_URL=http://xxx.xxx.xxx.xxx:포트/v1
QWEN_MODEL=qwen3.5
QWEN_MODELS=qwen3.5,gpt20,gamma
ENABLE_MULTI_AGENT=true
WEB_HOST=127.0.0.1
WEB_PORT=8000
```

`QWEN_BASE_URL`에 `/v1`이 붙는지 반드시 확인하세요.

콘솔 기본 실행 모델은 `QWEN_MODEL`로 지정합니다.

```ini
QWEN_MODEL=qwen3.5
```

웹 화면에서 선택 가능한 모델 목록은 `QWEN_MODELS`에 쉼표로 등록합니다.

```ini
QWEN_MODELS=qwen3.5,gpt20,gamma
```

사용 가능한 모델명이 아래와 같다면 웹에서 드롭다운으로 선택할 수 있습니다.

```ini
QWEN_MODEL=qwen3.5
```

```ini
QWEN_MODEL=gpt20
```

```ini
QWEN_MODEL=gamma
```

DeepAgents는 Tool Calling 가능한 Chat Model을 전제로 동작하므로, 먼저 `qwen3.5`로 테스트하고 Tool Calling 오류가 나면 `gpt20` 또는 `gamma`로 바꿔 확인하세요.

## 6. 실행

콘솔에서 바로 테스트하려면 아래 명령을 실행합니다.

```powershell
python app_closed.py
```

`app_closed.py`는 외부 검색 Tool을 연결하지 않고, 사내 보안 점검 TODO를 만드는 내부 Tool만 등록합니다.

```python
agent = create_deep_agent(
    model=qwen_llm,
    tools=[make_security_todo],
    system_prompt=INSTRUCTIONS,
)
```

## 7. 웹으로 실행

추가 패키지 설치 없이 Python 표준 라이브러리 HTTP 서버로 실행됩니다.

```powershell
python web_closed.py
```

브라우저에서 아래 주소를 엽니다.

```text
http://127.0.0.1:8000
```

다른 PC에서 접속해야 하는 내부 테스트 환경이면 `.env`에서 `WEB_HOST`를 `0.0.0.0`으로 바꾸고 Windows 방화벽 인바운드 규칙에서 해당 포트를 허용하세요.

웹 화면에서는 `.env`의 `QWEN_MODELS`에 등록된 모델을 드롭다운으로 선택할 수 있습니다.

멀티에이전트 사용을 켜면 메인 에이전트가 필요할 때 아래 서브에이전트로 작업을 위임합니다.

- `security-checker`: 접근권한, 로그, 취약점 조치 여부를 기준으로 보안 점검 항목 분석
- `report-writer`: 분석 결과를 TODO, 체크리스트, 보고서 형식으로 정리

콘솔 실행에서 멀티에이전트를 끄려면 `.env`에 아래처럼 설정합니다.

```ini
ENABLE_MULTI_AGENT=false
```

## 실패 시 먼저 확인

패키지 import를 확인합니다.

```powershell
python -c "import langchain_openai; print('ok')"
python -c "import deepagents; print('ok')"
```

Qwen 3.5 API 연결을 확인합니다.

```powershell
curl http://xxx.xxx.xxx.xxx:포트/v1/models
```

## 폐쇄망 구동 시 주의사항

- 폐쇄망 PC에서는 외부 다운로드 명령을 실행하지 않습니다.
- 외부 웹 검색 도구, 외부 SaaS API, 인터넷 기반 플러그인은 폐쇄망에서 실패할 수 있습니다.
- Tavily, DuckDuckGo, 외부 검색 Tool은 등록하지 마세요.
- 사내 DB, 내부 API, 내부 파일 시스템 등 폐쇄망에서 접근 가능한 Tool만 연결하세요.
- `create_deep_agent(model=qwen_llm)`만 쓰기보다 `tools`, `instructions`, `model`을 명시하는 방식이 폐쇄망 PoC에서 더 안전하고 명확합니다.
- `deepagents`의 계획 수립과 도구 호출이 정상 동작하려면 Qwen 3.5 API 모델이 Tool Calling을 지원해야 합니다.
- Qwen 3.5 API가 OpenAI 호환 `/v1/chat/completions` 형태를 지원하는지 확인하세요.

## Git 업로드 전 확인

`.env` 파일은 민감 정보가 포함되므로 Git에 올리지 않습니다.
`offline_packages/`는 용량이 크고 환경별 wheel이 섞일 수 있으므로 Git에 올리지 않습니다.
