$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$SourceRoot = Join-Path $Root "external_sources"
$DeepAgentsSource = Join-Path $SourceRoot "deepagents"
$PackageDir = Join-Path $Root "offline_packages"
$BundleDir = Join-Path $Root "offline_bundle"
$BundleProjectDir = Join-Path $BundleDir "deepagent"
$BundleSourceDir = Join-Path $BundleDir "deepagents_official_source"
$Requirements = Join-Path $Root "requirements.txt"

Write-Host "[외부 인터넷 PC] 공식 DeepAgents 소스 준비"
New-Item -ItemType Directory -Force -Path $SourceRoot | Out-Null

if (Test-Path (Join-Path $DeepAgentsSource ".git")) {
    Write-Host "이미 클론된 공식 DeepAgents 저장소가 있어 최신 상태로 갱신합니다."
    git -C $DeepAgentsSource pull
} else {
    git clone https://github.com/langchain-ai/deepagents.git $DeepAgentsSource
}

Write-Host ""
Write-Host "[외부 인터넷 PC] 오프라인 wheel 패키지 다운로드"
New-Item -ItemType Directory -Force -Path $PackageDir | Out-Null
python -m pip download -d $PackageDir -r $Requirements

Write-Host ""
Write-Host "[외부 인터넷 PC] 폐쇄망 반입용 offline_bundle 생성"
New-Item -ItemType Directory -Force -Path $BundleProjectDir | Out-Null

Copy-Item -Force (Join-Path $Root "README.md") $BundleProjectDir
Copy-Item -Force (Join-Path $Root "app_closed.py") $BundleProjectDir
Copy-Item -Force (Join-Path $Root "web_closed.py") $BundleProjectDir
Copy-Item -Force (Join-Path $Root "console_ui.py") $BundleProjectDir
Copy-Item -Force (Join-Path $Root "chat_cli.py") $BundleProjectDir
Copy-Item -Force (Join-Path $Root "launcher_cli.py") $BundleProjectDir
Copy-Item -Force (Join-Path $Root "dev_common.py") $BundleProjectDir
Copy-Item -Force (Join-Path $Root "doctor.py") $BundleProjectDir
Copy-Item -Force (Join-Path $Root "fix_wizard.py") $BundleProjectDir
Copy-Item -Force (Join-Path $Root "project_wizard.py") $BundleProjectDir
Copy-Item -Force (Join-Path $Root "ops_common.py") $BundleProjectDir
Copy-Item -Force (Join-Path $Root "ml_common.py") $BundleProjectDir
Copy-Item -Force (Join-Path $Root "scaffold_common.py") $BundleProjectDir
Copy-Item -Force (Join-Path $Root "scaffold_cli.py") $BundleProjectDir
Copy-Item -Force (Join-Path $Root "registration_common.py") $BundleProjectDir
Copy-Item -Force (Join-Path $Root "registration_wizard.py") $BundleProjectDir
Copy-Item -Force (Join-Path $Root "autofix_common.py") $BundleProjectDir
Copy-Item -Force (Join-Path $Root "ui_common.py") $BundleProjectDir
Copy-Item -Force (Join-Path $Root "requirements.txt") $BundleProjectDir
Copy-Item -Force (Join-Path $Root "pyproject.toml") $BundleProjectDir
Copy-Item -Force (Join-Path $Root ".env.example") $BundleProjectDir
Copy-Item -Recurse -Force (Join-Path $Root "scripts") $BundleProjectDir
Copy-Item -Recurse -Force (Join-Path $Root "skills") $BundleProjectDir
Copy-Item -Recurse -Force $PackageDir $BundleDir
Copy-Item -Recurse -Force $DeepAgentsSource $BundleSourceDir

$ManifestPath = Join-Path $BundleDir "bundle_manifest.json"
$ProjectFiles = Get-ChildItem -Path $BundleProjectDir -Recurse -File | ForEach-Object {
    $_.FullName.Substring($BundleProjectDir.Length + 1).Replace("\", "/")
}
$WheelFiles = Get-ChildItem -Path (Join-Path $BundleDir "offline_packages") -File | ForEach-Object {
    $_.Name
}
$Manifest = [ordered]@{
    created_at = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    python_version = (& python --version)
    project = "deepagent"
    project_files = @($ProjectFiles)
    requirements = Get-Content $Requirements
    wheel_files = @($WheelFiles)
    official_deepagents_source = "deepagents_official_source"
}
$Manifest | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 $ManifestPath

Write-Host ""
Write-Host "완료"
Write-Host "폐쇄망 PC로 아래 폴더를 통째로 복사하세요:"
Write-Host $BundleDir
Write-Host "번들 매니페스트:"
Write-Host $ManifestPath
