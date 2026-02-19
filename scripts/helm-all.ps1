param(
    [string]$Namespace = "calculadora-suma",
    [string]$ReleaseName = "suma-basica",
    [string]$ChartPath = "./helm/suma-basica",
    [string]$ValuesFile = "./helm/suma-basica/values-local.yaml",
    [string]$GithubUser = "lhalha01",
    [string]$GithubPat = "",
    [switch]$SkipSecret,
    [switch]$ValidateOnly,
    [int]$EventsTail = 30
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$helmLocalScript = Join-Path $scriptDir "helm-local.ps1"
$helmStatusScript = Join-Path $scriptDir "helm-status.ps1"

if (-not (Test-Path $helmLocalScript)) {
    throw "No se encontró $helmLocalScript"
}
if (-not (Test-Path $helmStatusScript)) {
    throw "No se encontró $helmStatusScript"
}

if ([string]::IsNullOrWhiteSpace($GithubPat)) {
    $GithubPat = $env:GITHUB_PAT
}

Write-Host "[1/2] Ejecutando despliegue/validación Helm..." -ForegroundColor Cyan

$localParams = @{
    Namespace = $Namespace
    ReleaseName = $ReleaseName
    ChartPath = $ChartPath
    ValuesFile = $ValuesFile
    GithubUser = $GithubUser
}

if (-not [string]::IsNullOrWhiteSpace($GithubPat)) {
    $localParams.GithubPat = $GithubPat
}
if ($SkipSecret) {
    $localParams.SkipSecret = $true
}
if ($ValidateOnly) {
    $localParams.ValidateOnly = $true
}

& $helmLocalScript @localParams

Write-Host "[2/2] Ejecutando diagnóstico Helm/Kubernetes..." -ForegroundColor Cyan
& $helmStatusScript -Namespace $Namespace -ReleaseName $ReleaseName -EventsTail $EventsTail

Write-Host "Flujo Helm completado." -ForegroundColor Green
