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
Write-Host "설치 완료"
