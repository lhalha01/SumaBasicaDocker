param(
    [string]$Namespace = "calculadora-suma",
    [string]$ReleaseName = "suma-basica",
    [switch]$DeleteNamespace,
    [switch]$DeleteGhcrSecret
)

$ErrorActionPreference = "Stop"

function Require-Command {
    param([string]$CommandName)
    if (-not (Get-Command $CommandName -ErrorAction SilentlyContinue)) {
        throw "No se encontró '$CommandName' en PATH. Instálalo y vuelve a ejecutar el script."
    }
}

Write-Host "[1/4] Validando herramientas..." -ForegroundColor Cyan
Require-Command "kubectl"
Require-Command "helm"

Write-Host "[2/4] Eliminando release Helm (si existe)..." -ForegroundColor Cyan
$releaseExists = $false
try {
    $null = helm status $ReleaseName -n $Namespace 2>$null
    $releaseExists = $true
}
catch {
    $releaseExists = $false
}

if ($releaseExists) {
    helm uninstall $ReleaseName -n $Namespace
}
else {
    Write-Host "Release '$ReleaseName' no existe en namespace '$Namespace'." -ForegroundColor Yellow
}

Write-Host "[3/4] Limpieza opcional de secretos..." -ForegroundColor Cyan
if ($DeleteGhcrSecret) {
    kubectl delete secret ghcr-secret -n $Namespace --ignore-not-found | Out-Null
    Write-Host "Secret ghcr-secret eliminado (si existía)." -ForegroundColor Green
}
else {
    Write-Host "Se conserva secret ghcr-secret (usa -DeleteGhcrSecret para eliminarlo)." -ForegroundColor Yellow
}

Write-Host "[4/4] Limpieza opcional de namespace..." -ForegroundColor Cyan
if ($DeleteNamespace) {
    kubectl delete namespace $Namespace --ignore-not-found
}
else {
    Write-Host "Namespace '$Namespace' conservado (usa -DeleteNamespace para eliminarlo)." -ForegroundColor Yellow
    kubectl get deployments,services -n $Namespace 2>$null
}

Write-Host "Limpieza completada." -ForegroundColor Green
