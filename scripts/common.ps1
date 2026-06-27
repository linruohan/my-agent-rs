# Shared helpers for PowerShell scripts
$ErrorActionPreference = "Stop"

function Get-ProjectRoot {
    # scripts/ 的上一级即项目根
    $Root = Split-Path -Parent $PSScriptRoot
    if (-not (Test-Path (Join-Path $Root "agent\main.py"))) {
        throw "Project root not found. Expected agent\main.py under $Root"
    }
    return $Root
}

function Initialize-AgentEnv {
    param([string]$Root)
    $agentDir = Join-Path $Root "agent"
    $dataDir = Join-Path $Root "data"
    $env:AGENT_CONFIG_DIR = Join-Path $agentDir "config"
    $env:AGENT_DATA_DIR = $dataDir
    foreach ($sub in @("checkpoints", "workspace", "vectorstore")) {
        $p = Join-Path $dataDir $sub
        if (-not (Test-Path $p)) { New-Item -ItemType Directory -Path $p -Force | Out-Null }
    }
    return @{ AgentDir = $agentDir; DataDir = $dataDir }
}

function Test-CommandExists([string]$Name) {
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Assert-Dependencies {
    if (-not (Test-CommandExists "python")) {
        throw "Python not found. Install Python 3.11+ and add to PATH."
    }
    $pyVersion = python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
    if ([version]$pyVersion -lt [version]"3.11") {
        throw "Python 3.11+ required, found $pyVersion"
    }
}

function Wait-SidecarHealth {
    param(
        [int]$Port,
        [int]$TimeoutSec = 45
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    $url = "http://127.0.0.1:$Port/health"
    while ((Get-Date) -lt $deadline) {
        try {
            $resp = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 2
            if ($resp.StatusCode -eq 200) { return $true }
        } catch {}
        Start-Sleep -Milliseconds 500
    }
    return $false
}

function Stop-SidecarProcess {
    param(
        [System.Diagnostics.Process]$Process,
        [int]$Port = 8765
    )
    if ($null -eq $Process -or $Process.HasExited) { return }
    try {
        Invoke-WebRequest -Uri "http://127.0.0.1:$Port/shutdown" -Method POST -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue | Out-Null
    } catch {}
    Start-Sleep -Milliseconds 500
    if (-not $Process.HasExited) {
        Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
    }
}
