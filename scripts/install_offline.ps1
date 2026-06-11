$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$PackageDir = Join-Path (Split-Path -Parent $Root) "offline_packages"
$Requirements = Join-Path $Root "requirements.txt"

if (!(Test-Path $PackageDir)) {
    throw "offline_packages 폴더를 찾을 수 없습니다: $PackageDir"
}

Write-Host "[폐쇄망 PC] 인터넷 없이 로컬 wheel 패키지만 사용해 설치합니다."
python -m pip install --no-index --find-links=$PackageDir -r $Requirements

Write-Host ""
Write-Host "[폐쇄망 PC] deepagent 터미널 명령을 등록합니다."
python -m pip install --no-index --find-links=$PackageDir --no-build-isolation --no-deps -e $Root

Write-Host ""
Write-Host "설치 완료"
Write-Host "가상환경이 활성화되어 있으면 아래 명령을 바로 사용할 수 있습니다:"
Write-Host "  deepagent       # 선택 메뉴"
Write-Host "  deepagents      # 선택 메뉴 별칭"
Write-Host "  deepagent-menu  # 선택 메뉴 별칭"
Write-Host "  deepagent-chat"
Write-Host "  deepagent-project"
Write-Host "  deepagent-web"
Write-Host "  deepagent-console"
Write-Host "  deepagent-doctor"
Write-Host "  deepagent-run"
Write-Host "  deepagent-scaffold"
