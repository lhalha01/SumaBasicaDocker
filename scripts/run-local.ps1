param(
    [switch]$InstallDeps,
    [switch]$NoRestart,
    [switch]$Foreground,
    [int]$TimeoutSeconds = 20,
    [string]$Url = "http://localhost:8080"
)

$ErrorActionPreference = "Stop"

function Resolve-PythonExecutable {
    $venvPython = Join-Path $PSScriptRoot "..\.venv\Scripts\python.exe"
    $venvPython = [System.IO.Path]::GetFullPath($venvPython)

    if (Test-Path $venvPython) {
        return $venvPython
    }

    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCmd) {
        return $pythonCmd.Path
    }

    throw "No se encontró Python. Crea el .venv o instala Python y asegúralo en PATH."
}

function Stop-ExistingProxy {
    $processes = Get-CimInstance Win32_Process |
        Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -like '*proxy.py*' }

    foreach ($p in $processes) {
        try {
            Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop
            Write-Host "Proxy previo detenido (PID $($p.ProcessId))." -ForegroundColor Yellow
        }
        catch {
            Write-Host "No se pudo detener PID $($p.ProcessId): $($_.Exception.Message)" -ForegroundColor Yellow
        }
    }
}

function Wait-ForUrl {
    param([string]$TargetUrl, [int]$Seconds)

    $deadline = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -Uri $TargetUrl -UseBasicParsing -TimeoutSec 3
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
                return $true
            }
        }
        catch {
            Start-Sleep -Milliseconds 600
        }
    }

    return $false
}

Write-Host "[1/4] Resolviendo ejecutable de Python..." -ForegroundColor Cyan
$pythonExe = Resolve-PythonExecutable

if ($InstallDeps) {
    Write-Host "[2/4] Instalando dependencias Python..." -ForegroundColor Cyan
    & $pythonExe -m pip install flask flask-cors requests
}
else {
    Write-Host "[2/4] Saltando instalación de dependencias (usa -InstallDeps si lo necesitas)." -ForegroundColor Cyan
}

if (-not $NoRestart) {
    Write-Host "[3/4] Reiniciando instancia previa de proxy (si existe)..." -ForegroundColor Cyan
    Stop-ExistingProxy
}
else {
    Write-Host "[3/4] Saltando reinicio de proxy previo (NoRestart)." -ForegroundColor Cyan
}

if ($Foreground) {
    Write-Host "[4/4] Iniciando proxy en primer plano..." -ForegroundColor Cyan
    & $pythonExe "proxy.py"
    exit $LASTEXITCODE
}

Write-Host "[4/4] Iniciando proxy en segundo plano y validando salud..." -ForegroundColor Cyan
$proc = Start-Process -FilePath $pythonExe -ArgumentList "proxy.py" -WorkingDirectory (Join-Path $PSScriptRoot "..") -PassThru

if (Wait-ForUrl -TargetUrl $Url -Seconds $TimeoutSeconds) {
    Write-Host "Proxy operativo en $Url (PID $($proc.Id))." -ForegroundColor Green
    Write-Host "Para detener: Stop-Process -Id $($proc.Id)" -ForegroundColor Gray
}
else {
    Write-Host "El proxy no respondió en $Url tras $TimeoutSeconds segundos." -ForegroundColor Red
    Write-Host "Revisa ejecución en primer plano con: .\scripts\run-local.ps1 -Foreground" -ForegroundColor Yellow
    exit 1
}
