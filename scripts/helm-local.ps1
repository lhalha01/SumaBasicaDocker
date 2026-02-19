param(
    [string]$Namespace = "calculadora-suma",
    [string]$ReleaseName = "suma-basica",
    [string]$ChartPath = "./helm/suma-basica",
    [string]$ValuesFile = "./helm/suma-basica/values-local.yaml",
    [string]$GithubUser = "lhalha01",
    [string]$GithubPat = "",
    [switch]$ValidateOnly,
    [switch]$SkipSecret
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($GithubPat)) {
    $GithubPat = $env:GITHUB_PAT
}

function Require-Command {
    param([string]$CommandName)
    if (-not (Get-Command $CommandName -ErrorAction SilentlyContinue)) {
        throw "No se encontró '$CommandName' en PATH. Instálalo y vuelve a ejecutar el script."
    }
}

Write-Host "[1/6] Validando herramientas..." -ForegroundColor Cyan
Require-Command "kubectl"
Require-Command "helm"

Write-Host "[2/6] Validando chart Helm..." -ForegroundColor Cyan
helm lint $ChartPath
helm template $ReleaseName $ChartPath -f $ValuesFile | Out-Null

if ($ValidateOnly) {
    Write-Host "Validación completada (modo ValidateOnly)." -ForegroundColor Green
    exit 0
}

Write-Host "[3/6] Creando namespace si no existe..." -ForegroundColor Cyan
kubectl create namespace $Namespace --dry-run=client -o yaml | kubectl apply -f - | Out-Null

if (-not $SkipSecret) {
    if ([string]::IsNullOrWhiteSpace($GithubPat)) {
        throw "No se proporcionó GitHub PAT. Define GITHUB_PAT o usa -GithubPat <token>."
    }

    Write-Host "[4/6] Creando/actualizando secret ghcr-secret..." -ForegroundColor Cyan
    kubectl create secret docker-registry ghcr-secret `
      --docker-server=ghcr.io `
      --docker-username=$GithubUser `
      --docker-password=$GithubPat `
      -n $Namespace `
      --dry-run=client -o yaml | kubectl apply -f - | Out-Null
}
else {
    Write-Host "[4/6] Omitiendo creación de secret (SkipSecret)." -ForegroundColor Yellow
}

Write-Host "[5/6] Desplegando release Helm..." -ForegroundColor Cyan
helm upgrade --install $ReleaseName $ChartPath --namespace $Namespace --create-namespace -f $ValuesFile

Write-Host "[6/6] Verificando estado..." -ForegroundColor Cyan
helm status $ReleaseName -n $Namespace
kubectl get deployments,services -n $Namespace

Write-Host "Despliegue local completado." -ForegroundColor Green
