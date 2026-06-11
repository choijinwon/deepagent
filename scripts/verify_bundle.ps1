$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$BundleRoot = Split-Path -Parent $Root
$ManifestPath = Join-Path $BundleRoot "bundle_manifest.json"
$PackageDir = Join-Path $BundleRoot "offline_packages"

Write-Host "[폐쇄망 PC] offline_bundle 검증을 시작합니다."
Write-Host "프로젝트 폴더: $Root"
Write-Host "번들 폴더: $BundleRoot"

if (!(Test-Path $ManifestPath)) {
    throw "bundle_manifest.json을 찾을 수 없습니다: $ManifestPath"
}

$Manifest = Get-Content $ManifestPath -Raw | ConvertFrom-Json

$RequiredProjectFiles = @(
    "README.md",
    "app_closed.py",
    "web_closed.py",
    "console_ui.py",
    "chat_cli.py",
    "doctor.py",
    "ops_common.py",
    "ml_common.py",
    "scaffold_common.py",
    "registration_common.py",
    "autofix_common.py",
    "requirements.txt",
    ".env.example",
    "scripts/install_offline.ps1",
    "scripts/verify_bundle.ps1",
    "skills/security-report/SKILL.md",
    "skills/access-audit/SKILL.md",
    "skills/vllm-ops-wiki/SKILL.md"
)

$Missing = @()
foreach ($RelativePath in $RequiredProjectFiles) {
    $Path = Join-Path $Root ($RelativePath -replace "/", [IO.Path]::DirectorySeparatorChar)
    if (!(Test-Path $Path)) {
        $Missing += $RelativePath
    }
}

if (!(Test-Path $PackageDir)) {
    $Missing += "../offline_packages/"
} else {
    $WheelCount = (Get-ChildItem -Path $PackageDir -File | Measure-Object).Count
    if ($WheelCount -eq 0) {
        $Missing += "../offline_packages/*.whl"
    }
}

Write-Host ""
Write-Host "매니페스트 생성일: $($Manifest.created_at)"
Write-Host "매니페스트 Python: $($Manifest.python_version)"
Write-Host "패키지 파일 수: $WheelCount"

if ($Missing.Count -gt 0) {
    Write-Host ""
    Write-Host "누락 항목:"
    foreach ($Item in $Missing) {
        Write-Host "- $Item"
    }
    throw "번들 검증 실패"
}

Write-Host ""
Write-Host "검증 완료: 필수 파일과 offline_packages 폴더가 확인되었습니다."
