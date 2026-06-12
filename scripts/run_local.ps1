param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$CommandArgs
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Separator = [IO.Path]::PathSeparator
$ExistingPythonPath = $env:PYTHONPATH

if ([string]::IsNullOrWhiteSpace($ExistingPythonPath)) {
    $env:PYTHONPATH = $Root
} else {
    $Paths = $ExistingPythonPath -split [regex]::Escape($Separator)
    if ($Paths -notcontains $Root) {
        $env:PYTHONPATH = "$Root$Separator$ExistingPythonPath"
    }
}

Set-Location $Root
python (Join-Path $Root "launcher_cli.py") @CommandArgs
