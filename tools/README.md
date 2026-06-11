# Internal Tool Registry

폐쇄망에서 사용할 사내 DB/API Tool을 이 폴더에 추가합니다.

원칙:

- 외부 인터넷, 외부 SaaS, 공개 검색 API Tool은 등록하지 않습니다.
- 사내 네트워크에서 접근 가능한 DB/API/파일 시스템 Tool만 등록합니다.
- API Key, DB 비밀번호, 토큰은 코드에 쓰지 않고 `.env` 또는 Windows 보안 저장소로 관리합니다.
- Tool 설명에는 입력값, 출력 형식, 실패 시 동작을 명확히 적습니다.

예시 후보:

- `asset_inventory`: 서버/시스템 자산 목록 조회
- `access_audit`: 계정/권한 점검 결과 조회
- `vulnerability_status`: 취약점 조치 이력 조회
- `report_archive`: 보고서 초안 저장 또는 조회
