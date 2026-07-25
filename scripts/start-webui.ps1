param(
    [string]$HostName = "127.0.0.1",
    [int]$Port = 8000,
    [switch]$NoAutoPort,
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

function Test-PortInUse {
    param(
        [string]$Address,
        [int]$PortNumber
    )

    $listener = $null
    try {
        $ipAddress = [System.Net.IPAddress]::Parse($Address)
        $listener = [System.Net.Sockets.TcpListener]::new($ipAddress, $PortNumber)
        $listener.Start()
        return $false
    } catch {
        return $true
    } finally {
        if ($listener -ne $null) {
            $listener.Stop()
        }
    }
}

function Resolve-Port {
    param(
        [string]$Address,
        [int]$RequestedPort,
        [bool]$DisableAutoPort
    )

    if (-not (Test-PortInUse $Address $RequestedPort)) {
        return $RequestedPort
    }

    if ($DisableAutoPort) {
        throw "Port $RequestedPort is already in use. Stop the existing process or pass -Port with a free port."
    }

    for ($candidate = $RequestedPort + 1; $candidate -le $RequestedPort + 50; $candidate++) {
        if (-not (Test-PortInUse $Address $candidate)) {
            Write-Host "Port $RequestedPort is already in use; using $candidate instead."
            return $candidate
        }
    }

    throw "No free port found from $RequestedPort to $($RequestedPort + 50)."
}

$projectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$pythonExe = Resolve-Python $Python
$resolvedPort = Resolve-Port $HostName $Port $NoAutoPort.IsPresent
$reloadArg = @()
if ($Reload) {
    $reloadArg = @("--reload")
}

Write-Host "Starting Harness API/WebUI"
Write-Host "Project: $projectRoot"
Write-Host "Python:  $pythonExe"
Write-Host "URL:     http://$HostName`:$resolvedPort"
Write-Host ""
Write-Host "Run detail pages are available at /ui/runs/{run_id}."
Write-Host "See START_WEBUI.md for commands that create a demo run."
Write-Host ""

Set-Location $projectRoot
$env:PYTHONUTF8 = "1"
& $pythonExe -m uvicorn harness.api:app --host $HostName --port $resolvedPort @reloadArg
