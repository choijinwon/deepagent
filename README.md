# DeepAgents 폐쇄망 Kwan API 연동 PoC

폐쇄망 내부에서 OpenAI 호환 Kwan API 서버를 `deepagents`의 LLM 백엔드로 연결하는 PoC 예제입니다.
설치와 실행 명령은 Windows 11 Pro / PowerShell 기준입니다.

핵심은 다음 4가지입니다.

- 인터넷 다운로드는 외부 PC에서만 수행
- 폐쇄망 PC에는 소스와 wheel 패키지 묶음만 복사
- Kwan OpenAI 호환 API를 `ChatOpenAI`의 `base_url`로 연결
- 외부 검색 Tool은 제거하고 사내 내부 Tool만 등록

## 폴더 구성

```text
deepagent/
├─ app_closed.py
├─ requirements.txt
├─ .env.example
├─ .gitignore
└─ scripts/
   ├─ build_offline_packages.ps1
   └─ install_offline.ps1
```

## 전체 흐름

```text
외부 인터넷 PC
1. 이 저장소 다운로드
2. offline_packages 폴더에 wheel 패키지 다운로드
3. deepagent 폴더와 offline_packages 폴더를 USB/보안망으로 복사

폐쇄망 PC
4. Python 가상환경 생성
5. offline_packages만 사용해서 오프라인 설치
6. .env 작성
7. app_closed.py 실행
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

```powershell
.\scripts\build_offline_packages.ps1
```

스크립트를 쓰지 않는 경우 아래 명령을 직접 실행해도 됩니다.

```powershell
mkdir offline_packages

pip download -d offline_packages -r requirements.txt
```

## 2. 폐쇄망 PC로 복사

아래 2개를 통째로 폐쇄망 PC에 복사합니다.

- `deepagent/`
- `offline_packages/`

중요: 폐쇄망 PC에서는 `git clone`, `pip download`, 인터넷 기반 설치를 실행하지 않습니다.

## 3. 폐쇄망 PC에서 가상환경 생성

```powershell
cd deepagent

python -m venv .venv
.venv\Scripts\activate
```

## 4. 폐쇄망 PC에서 오프라인 설치

`offline_packages` 폴더가 `deepagent` 폴더와 같은 위치에 있다고 가정합니다.

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

`.env` 파일의 값을 사내 Kwan API 서버 정보에 맞게 수정합니다.

```ini
KWAN_API_KEY=your-internal-kwan-key
KWAN_BASE_URL=http://xxx.xxx.xxx.xxx:포트/v1
KWAN_MODEL=kwan-model-name
```

`KWAN_BASE_URL`에 `/v1`이 붙는지 반드시 확인하세요.

## 6. 실행

```powershell
python app_closed.py
```

`app_closed.py`는 외부 검색 Tool을 연결하지 않고, 사내 보안 점검 TODO를 만드는 내부 Tool만 등록합니다.

```python
agent = create_deep_agent(
    model=kwan_llm,
    tools=[make_security_todo],
    instructions=INSTRUCTIONS,
)
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

- 폐쇄망 PC에서는 외부 다운로드 명령을 실행하지 않습니다.
- 외부 웹 검색 도구, 외부 SaaS API, 인터넷 기반 플러그인은 폐쇄망에서 실패할 수 있습니다.
- Tavily, DuckDuckGo, 외부 검색 Tool은 등록하지 마세요.
- 사내 DB, 내부 API, 내부 파일 시스템 등 폐쇄망에서 접근 가능한 Tool만 연결하세요.
- `create_deep_agent(model=kwan_llm)`만 쓰기보다 `tools`, `instructions`, `model`을 명시하는 방식이 폐쇄망 PoC에서 더 안전하고 명확합니다.
- `deepagents`의 계획 수립과 도구 호출이 정상 동작하려면 Kwan API 모델이 Tool Calling을 지원해야 합니다.
- Kwan API가 OpenAI 호환 `/v1/chat/completions` 형태를 지원하는지 확인하세요.

## Git 업로드 전 확인

`.env` 파일은 민감 정보가 포함되므로 Git에 올리지 않습니다.
`offline_packages/`는 용량이 크고 환경별 wheel이 섞일 수 있으므로 Git에 올리지 않습니다.
