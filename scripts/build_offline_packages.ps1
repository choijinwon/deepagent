$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$PackageDir = Join-Path $Root "offline_packages"
$Requirements = Join-Path $Root "requirements.txt"

Write-Host "[외부 인터넷 PC] 오프라인 패키지 폴더 생성: $PackageDir"
New-Item -ItemType Directory -Force -Path $PackageDir | Out-Null

Write-Host "[외부 인터넷 PC] requirements.txt 기준 wheel 패키지 다운로드"
python -m pip download -d $PackageDir -r $Requirements

Write-Host ""
Write-Host "완료: deepagent 폴더와 offline_packages 폴더를 폐쇄망 PC로 복사하세요."
