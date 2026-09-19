<#
.SYNOPSIS
    Starts the NexusAI FastAPI backend server on port 8001.
    Directory-independent: can be run from project root, backend folder, or anywhere.
.PARAMETER ForceRestart
    Terminates any existing process holding port 8001 and starts a fresh server.
.PARAMETER Reload
    Optional switch to enable Uvicorn auto-reload (default: false to prevent WinError 10013).
.PARAMETER Port
    Port number to bind (default: 8001).
#>
param(
    [switch]$ForceRestart,
    [switch]$Reload,
    [int]$Port = 8001
)

$ErrorActionPreference = "Stop"

Write-Host "=================================================" -ForegroundColor Cyan
Write-Host "         NexusAI Backend Launcher (Windows)      " -ForegroundColor Cyan
Write-Host "=================================================" -ForegroundColor Cyan

# 1. Resolve Backend Directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (Test-Path (Join-Path $ScriptDir "NexusAI-GitHub\main.py")) {
    $BackendDir = Join-Path $ScriptDir "NexusAI-GitHub"
    $ProjectRoot = $ScriptDir
} elseif (Test-Path (Join-Path $ScriptDir "main.py")) {
    $BackendDir = $ScriptDir
    $ProjectRoot = Split-Path -Parent $ScriptDir
} elseif (Test-Path (Join-Path $ScriptDir "backend\main.py")) {
    $BackendDir = Join-Path $ScriptDir "backend"
    $ProjectRoot = $ScriptDir
} elseif (Test-Path ".\NexusAI-GitHub\main.py") {
    $BackendDir = (Get-Item ".\NexusAI-GitHub").FullName
    $ProjectRoot = (Get-Item ".").FullName
} elseif (Test-Path ".\main.py") {
    $BackendDir = (Get-Item ".").FullName
    $ProjectRoot = Split-Path -Parent $BackendDir
} elseif (Test-Path ".\backend\main.py") {
    $BackendDir = (Get-Item ".\backend").FullName
    $ProjectRoot = (Get-Item ".").FullName
} else {
    Write-Error "Could not locate NexusAI backend directory. Please run from project root or backend folder."
}

Write-Host "[*] Backend Directory: $BackendDir" -ForegroundColor Gray

# 2. Resolve Python Executable
$PythonCmd = $null
$VenvPython1 = Join-Path $BackendDir "venv\Scripts\python.exe"
$VenvPython2 = Join-Path $BackendDir ".venv\Scripts\python.exe"
$VenvPython3 = Join-Path $ProjectRoot "backend\venv\Scripts\python.exe"
$VenvPython4 = Join-Path $ProjectRoot "venv\Scripts\python.exe"
$VenvPython5 = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (Test-Path $VenvPython1) {
    $PythonCmd = $VenvPython1
} elseif (Test-Path $VenvPython2) {
    $PythonCmd = $VenvPython2
} elseif (Test-Path $VenvPython3) {
    $PythonCmd = $VenvPython3
} elseif (Test-Path $VenvPython4) {
    $PythonCmd = $VenvPython4
} elseif (Test-Path $VenvPython5) {
    $PythonCmd = $VenvPython5
} else {
    try {
        $pyCheck = & python --version 2>&1
        if ($LASTEXITCODE -eq 0 -or $pyCheck -match "Python") {
            $PythonCmd = "python"
        }
    } catch {
        try {
            $pyCheck = & py -3 --version 2>&1
            if ($LASTEXITCODE -eq 0 -or $pyCheck -match "Python") {
                $PythonCmd = "py"
            }
        } catch {
            Write-Error "Python was not found. Please install Python 3.10+ and add it to PATH."
        }
    }
}

if (-not $PythonCmd) {
    $PythonCmd = "python"
}

Write-Host "[*] Using Python: $PythonCmd" -ForegroundColor Gray

# 3. Check and Clean Port 8001 (WinError 10048 & WinError 10013 Prevention)
Write-Host "[*] Ensuring port $Port is free and stopping stale instances..." -ForegroundColor Gray

# Step A: Terminate any process listening on port $Port via netstat
try {
    $netstatOutput = netstat -ano | Select-String ":$Port\s.*LISTENING"
    foreach ($match in $netstatOutput) {
        $parts = ($match.Line -split '\s+') | Where-Object { $_ -ne "" }
        if ($parts.Count -ge 5) {
            $stalePID = [int]$parts[-1]
            if ($stalePID -gt 0 -and $stalePID -ne $PID) {
                Write-Host "[*] Terminating process on port $Port (PID $stalePID)..." -ForegroundColor Yellow
                & taskkill /F /T /PID $stalePID 2>$null
                try { Stop-Process -Id $stalePID -Force -ErrorAction SilentlyContinue } catch {}
            }
        }
    }
} catch {}

# Step B: Terminate any leftover uvicorn python processes
try {
    Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.Id -ne $PID } | Stop-Process -Force -ErrorAction SilentlyContinue
} catch {}

# Step C: Poll until port is 100% free
$retryCount = 0
while ($retryCount -lt 10) {
    $isOccupied = $false
    try {
        $check = netstat -ano | Select-String ":$Port\s.*LISTENING"
        if ($check) { $isOccupied = $true }
    } catch {}
    
    if (-not $isOccupied) {
        break
    }
    
    Start-Sleep -Milliseconds 500
    $retryCount++
}

Write-Host "[+] Port $Port is ready and clear." -ForegroundColor Green

# 4. Build Uvicorn Command Arguments (No --reload by default to prevent WinError 10013)
$UvicornArgs = @("-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "$Port")
if ($Reload) {
    Write-Host "[i] Auto-reload enabled by flag." -ForegroundColor Yellow
    $UvicornArgs += "--reload"
}

# 5. Start Uvicorn Server
Push-Location $BackendDir
try {
    Write-Host "[+] Starting NexusAI Backend on http://127.0.0.1:$Port ..." -ForegroundColor Green
    Write-Host "    API Docs available at: http://127.0.0.1:$Port/docs" -ForegroundColor Cyan
    Write-Host "    Press Ctrl+C to stop the server.`n" -ForegroundColor Gray
    
    if ($PythonCmd -eq "py") {
        & py -3 @UvicornArgs
    } else {
        & $PythonCmd @UvicornArgs
    }
} finally {
    Pop-Location
}
