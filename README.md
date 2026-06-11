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
├─ console_ui.py
├─ chat_cli.py
├─ doctor.py
├─ ops_common.py
├─ ml_common.py
├─ scaffold_common.py
├─ skills/
│  ├─ security-report/
│  ├─ access-audit/
│  └─ vllm-ops-wiki/
├─ tools/
│  └─ README.md
├─ requirements.txt
├─ .env.example
├─ .gitignore
└─ scripts/
   ├─ prepare_external_pc.ps1
   ├─ build_offline_packages.ps1
   ├─ install_offline.ps1
   └─ verify_bundle.ps1
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
8. app_closed.py, web_closed.py, console_ui.py 또는 chat_cli.py 실행
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
ENABLE_HARNESS_SKILLS=true
WEB_HOST=127.0.0.1
WEB_PORT=8000
PROMPT_STORE_PATH=prompt_templates.json
WIKI_LOG_DIR=wiki_logs
WIKI_LOG_STYLE=vllm
CHAT_WORKSPACE_DIR=agent_workspace
PLAN_DIR=plans
GOAL_DIR=goals
SESSION_DIR=sessions
MASK_SENSITIVE_LOGS=true
MODEL_CATALOG_PATH=model_catalog.json
EXPERIMENT_DIR=experiments
SCAFFOLD_OVERWRITE=false
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

하네스 스킬은 기본으로 켜져 있습니다.

```ini
ENABLE_HARNESS_SKILLS=true
```

현재 포함된 스킬은 아래와 같습니다.

- `security-report`: 보안 점검 보고서, TODO, 체크리스트 작성
- `access-audit`: 서버 접근권한, 계정, 권한, 로그 점검
- `vllm-ops-wiki`: vLLM 실행 기록과 운영 위키 Markdown 작성

스킬을 끄고 순수 Tool/Subagent만 테스트하려면 아래처럼 설정합니다.

```ini
ENABLE_HARNESS_SKILLS=false
```

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
    subagents=subagents,
    skills=get_harness_skill_sources(),
)
```

기본 `StateBackend`를 사용하므로 실행 시 로컬 `skills/` 파일을 가상 파일로 주입합니다.

```python
agent.invoke({
    "messages": [...],
    "files": get_harness_skill_files(),
})
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

`모델 연결 테스트` 버튼은 선택한 모델로 짧은 요청을 보내 API Key, Base URL, 모델명 설정이 맞는지 확인합니다.

멀티에이전트 사용을 켜면 메인 에이전트가 필요할 때 아래 서브에이전트로 작업을 위임합니다.

- `security-checker`: 접근권한, 로그, 취약점 조치 여부를 기준으로 보안 점검 항목 분석
- `report-writer`: 분석 결과를 TODO, 체크리스트, 보고서 형식으로 정리

콘솔 실행에서 멀티에이전트를 끄려면 `.env`에 아래처럼 설정합니다.

```ini
ENABLE_MULTI_AGENT=false
```

`결과 다운로드` 버튼은 현재 화면의 응답을 Markdown 파일로 저장합니다.

자주 쓰는 프롬프트는 웹 화면에서 이름을 입력한 뒤 `프롬프트 저장` 버튼으로 저장할 수 있습니다.
저장된 프롬프트는 `저장된 프롬프트` 목록에서 다시 불러오거나 삭제할 수 있습니다.
프롬프트 분류와 태그도 함께 저장할 수 있어 보안점검, 보고서, vLLM 운영, 장애분석 등으로 구분할 수 있습니다.
기본 저장 파일은 `prompt_templates.json`이며, 위치를 바꾸려면 `.env`에서 아래 값을 수정합니다.

```ini
PROMPT_STORE_PATH=prompt_templates.json
```

웹에서 `실행` 버튼으로 생성한 결과는 vLLM 위키트리 형식의 Markdown 기록으로 자동 저장됩니다.
기본 저장 폴더는 `wiki_logs/`입니다.
웹 화면의 목표, 플랜, 첨부 파일 경로는 실행 시 에이전트 가상 파일 컨텍스트에 함께 전달됩니다.
`목표 저장`, `플랜 저장` 버튼으로 CLI와 같은 `goals/`, `plans/` 폴더에 Markdown 기록을 남길 수 있습니다.
`작업 생성기` 영역에 템플릿을 붙여넣으면 `agent_workspace/` 아래 폴더와 파일을 자동 생성하고, 목표와 플랜도 함께 저장할 수 있습니다.
`생성 후 실행` 버튼은 자동 생성된 파일을 에이전트 컨텍스트에 첨부한 뒤 요청을 바로 실행합니다.
`모델 카탈로그` 버튼은 `model_catalog.json`과 `model_catalog.md`를 생성하고, `모델 비교 실험` 버튼은 등록 모델별 응답을 `experiments/`에 저장합니다.

```text
wiki_logs/
├─ index.md
└─ 2026-06-11/
   ├─ 101530-서버-접근권한-보안-점검-TODO-만들어줘.md
   └─ 102010-보안-점검-보고서-초안.md
```

`wiki_logs/index.md`에는 vLLM 환경 정보, 등록 모델, 날짜별 실행 기록 트리, 모델별 링크, 목표별 링크가 자동으로 갱신됩니다.
각 실행 기록에는 모델명, OpenAI 호환 Base URL, 목표, Tool Calling 필요 여부, 멀티에이전트 사용 여부, 하네스 스킬 목록, 프롬프트, 결과가 저장됩니다.
API Key는 기록하지 않습니다.
`MASK_SENSITIVE_LOGS=true`이면 실행 기록 저장 전에 API Key/Bearer 토큰 패턴과 IPv4 주소를 마스킹합니다.
저장 위치를 바꾸려면 `.env`에서 아래 값을 수정합니다.

```ini
WIKI_LOG_DIR=wiki_logs
WIKI_LOG_STYLE=vllm
```

## 8. 콘솔 UI로 실행

브라우저 없이 PowerShell 콘솔에서 메뉴 기반으로 사용하려면 아래 명령을 실행합니다.

```powershell
python console_ui.py
```

콘솔 UI에서 가능한 작업:

- 등록 모델 선택
- 프롬프트 입력/수정
- 저장된 프롬프트 불러오기/저장/삭제
- 멀티에이전트 ON/OFF
- 하네스 스킬 ON/OFF
- 모델 연결 테스트
- 실행 결과를 vLLM 위키 Markdown으로 자동 기록

Windows 기본 콘솔에서도 동작하도록 추가 UI 패키지를 사용하지 않습니다.

## 9. 챗봇형 CLI로 실행

Claude 스타일의 대화형 CLI가 필요하면 아래 명령을 실행합니다.

```powershell
python chat_cli.py
```

대화형 CLI 명령:

```text
/help                 명령 보기
/status               현재 모델과 런타임 상태 보기
/model                등록 모델 목록 보기
/model <name>         모델 변경
/multi on|off         멀티에이전트 켜기/끄기
/skills on|off        하네스 스킬 켜기/끄기
/prompts              저장된 프롬프트 목록
/load <name>          저장된 프롬프트를 불러와 바로 실행
/save <name>          마지막 사용자 프롬프트 저장
/clear                대화 메모리 초기화
/test                 선택 모델 연결 테스트
/paste                여러 줄 프롬프트 입력
/folder               현재 작업 폴더 보기
/folder <path>        작업 폴더 설정
/tree [depth]         작업 폴더 트리 보기
/read <path>          작업 폴더 파일 출력
/write <path>         작업 폴더 파일 작성
/add-file <path>      파일을 에이전트 컨텍스트에 첨부
/files                첨부 파일 목록 보기
/drop-file <path|all> 첨부 파일 제거
/plan new <title>     플랜 시작
/plan add <step>      플랜 단계 추가
/plan done <number>   플랜 단계 완료 처리
/plan show            현재 플랜 보기
/plan save [name]     플랜 Markdown 저장
/plan load <name>     저장된 플랜 불러오기
/plan clear           현재 플랜 초기화
/plans                저장된 플랜 목록
/goal new <title>     목표 시작
/goal criteria <text> 성공 기준 추가
/goal constraint <t>  제약사항 추가
/goal note <text>     목표 메모 추가
/goal show            현재 목표 보기
/goal save [name]     목표 Markdown 저장
/goal load <name>     저장된 목표 불러오기
/goal clear           현재 목표 초기화
/goals                저장된 목표 목록
/session save <name>  현재 세션 저장
/session load <name>  저장된 세션 복구
/sessions             저장된 세션 목록
/doctor               폐쇄망 진단 실행
/catalog              모델 카탈로그 생성/보기
/experiment <models>  마지막 프롬프트를 여러 모델로 비교 실행
/scaffold sample      붙여넣기 생성기 예시 보기
/scaffold paste       붙여넣기로 폴더/파일/목표/플랜 자동 생성
/scaffold file <path> 파일 내용으로 자동 생성
/scaffold last        마지막 생성 결과 보기
/scaffold attach      마지막 생성 파일을 에이전트 컨텍스트에 첨부
/exit                 종료
```

일반 문장을 입력하면 바로 모델에 전송됩니다.
응답은 화면에 출력되고 `wiki_logs/`에도 vLLM 위키 Markdown 기록으로 저장됩니다.

작업 폴더와 플랜 저장 위치는 `.env`에서 바꿀 수 있습니다.

```ini
CHAT_WORKSPACE_DIR=agent_workspace
PLAN_DIR=plans
GOAL_DIR=goals
SESSION_DIR=sessions
MODEL_CATALOG_PATH=model_catalog.json
EXPERIMENT_DIR=experiments
SCAFFOLD_OVERWRITE=false
```

`/add-file`로 첨부한 파일은 DeepAgents 가상 파일 컨텍스트에 함께 전달됩니다.
`/plan save`로 저장한 플랜은 Markdown 파일로 남습니다.
`/goal save`로 저장한 목표도 Markdown 파일로 남고, 현재 목표는 다음 에이전트 호출에 `/goals/current-goal.md`로 자동 전달됩니다.
`/session save`는 모델, 멀티에이전트 설정, 목표, 플랜, 첨부 파일 내용, 최근 대화를 JSON과 Markdown으로 저장합니다.

붙여넣기로 작업 폴더와 파일을 자동 생성하려면 아래처럼 실행합니다.

```text
/scaffold paste
```

그 뒤 아래 형식의 내용을 붙여넣고 마지막 줄에 `.`을 입력합니다.

````text
# Goal
폐쇄망 DeepAgents PoC 실행 환경 구성

## Success Criteria
- Windows 11에서 python chat_cli.py 실행
- qwen3.5 모델 연결 테스트 성공
- 실행 기록이 wiki_logs에 남는다

## Constraints
- 외부 인터넷 사용 금지
- 외부 검색 Tool 사용 금지

# Plan
- .env 구성
- python doctor.py 실행
- python chat_cli.py 실행
- 결과를 wiki_logs에 기록

# Folders
reports/security
prompts
runbooks/vllm

# Files
## reports/security/checklist.md
```md
# 보안 점검 체크리스트

- [ ] 접근권한 확인
- [ ] 로그 수집 확인
- [ ] 취약점 조치 이력 확인
```

## prompts/access-audit.md
```md
서버 접근권한 보안 점검 TODO를 만들어줘.
```
````

생성된 파일을 바로 에이전트 컨텍스트에 넣으려면 아래 명령을 실행합니다.

```text
/scaffold attach
```

마지막 프롬프트를 여러 모델로 비교하려면 먼저 일반 프롬프트를 한 번 실행한 뒤 아래처럼 실행합니다.

```text
/experiment qwen3.5,gpt20,gamma
```

결과는 `experiments/YYYY-MM-DD/` 아래 Markdown으로 저장됩니다.

모델 카탈로그를 만들려면 아래 명령을 실행합니다.

```text
/catalog
```

`model_catalog.json`은 모델 설명, 컨텍스트 길이, Tool Calling 확인 상태, 권장 temperature, 사용 사례를 기록하는 오프라인 모델 장부입니다.

## 10. 폐쇄망 진단

Windows 11 폐쇄망 PC에서 설정 문제를 먼저 확인하려면 아래 명령을 실행합니다.

```powershell
python doctor.py
```

챗봇형 CLI 안에서는 아래 명령으로 같은 진단을 실행할 수 있습니다.

```text
/doctor
```

진단 항목:

- 필수 패키지 import 확인
- `.env` 존재 여부 확인
- `QWEN_API_KEY`, `QWEN_BASE_URL`, `QWEN_MODEL`, `QWEN_MODELS` 확인
- `QWEN_BASE_URL`의 `/v1/models` 호출 확인
- Tool Calling 설정 확인 안내

## 11. 오프라인 번들 검증

외부 PC에서 `prepare_external_pc.ps1`을 실행하면 `offline_bundle/bundle_manifest.json`이 함께 생성됩니다.
폐쇄망 PC로 복사한 뒤 아래 명령으로 필수 파일 누락 여부를 확인합니다.

```powershell
cd offline_bundle\deepagent
.\scripts\verify_bundle.ps1
```

검증 항목:

- 실행용 Python 파일
- 스킬 파일
- 설치 스크립트
- `offline_packages` 폴더와 wheel 파일
- `bundle_manifest.json`

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
- `create_deep_agent(model=qwen_llm)`만 쓰기보다 `tools`, `system_prompt`, `model`을 명시하는 방식이 폐쇄망 PoC에서 더 안전하고 명확합니다.
- `deepagents`의 계획 수립과 도구 호출이 정상 동작하려면 Qwen 3.5 API 모델이 Tool Calling을 지원해야 합니다.
- Qwen 3.5 API가 OpenAI 호환 `/v1/chat/completions` 형태를 지원하는지 확인하세요.

## Git 업로드 전 확인

`.env` 파일은 민감 정보가 포함되므로 Git에 올리지 않습니다.
`prompt_templates.json`은 사용자별 프롬프트 저장 파일이므로 Git에 올리지 않습니다.
`wiki_logs/`는 실행 기록 폴더이므로 Git에 올리지 않습니다.
`agent_workspace/`, `plans/`, `goals/`, `sessions/`, `experiments/`는 사용자별 작업 파일, 플랜, 목표, 세션, 실험 저장 폴더이므로 Git에 올리지 않습니다.
`model_catalog.json`과 `model_catalog.md`는 폐쇄망 환경별 모델 장부이므로 기본적으로 Git에 올리지 않습니다.
`offline_packages/`는 용량이 크고 환경별 wheel이 섞일 수 있으므로 Git에 올리지 않습니다.
