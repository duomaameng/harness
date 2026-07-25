param(
    [string]$HostName = "127.0.0.1",
    [int]$Port = 8000,
    [switch]$Reload,
    [string]$Python = ""
)

$ErrorActionPreference = "Stop"

function Resolve-Python {
    param([string]$RequestedPython)

    if ($RequestedPython) {
        return $RequestedPython
    }

    if ($env:HARNESS_PYTHON) {
        return $env:HARNESS_PYTHON
    }

    $localVenv = Join-Path $PSScriptRoot "..\.venv\Scripts\python.exe"
    if (Test-Path $localVenv) {
        return (Resolve-Path $localVenv).Path
    }

    $codexPython = "C:\Users\duoma\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
    if (Test-Path $codexPython) {
        return $codexPython
    }

    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCommand) {
        return $pythonCommand.Source
    }

    throw "Python was not found. Install Python, create .venv, or set HARNESS_PYTHON."
}

$projectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$pythonExe = Resolve-Python $Python
$reloadArg = @()
if ($Reload) {
    $reloadArg = @("--reload")
}

Write-Host "Starting Harness API/WebUI"
Write-Host "Project: $projectRoot"
Write-Host "Python:  $pythonExe"
Write-Host "URL:     http://$HostName`:$Port"
Write-Host ""
Write-Host "Run detail pages are available at /ui/runs/{run_id}."
Write-Host "See START_WEBUI.md for commands that create a demo run."
Write-Host ""

Set-Location $projectRoot
$env:PYTHONUTF8 = "1"
& $pythonExe -m uvicorn harness.api:app --host $HostName --port $Port @reloadArg
