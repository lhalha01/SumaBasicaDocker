[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ResourceGroup,

    [Parameter(Mandatory = $true)]
    [string]$ClusterName,

    [string]$SubscriptionId,
    [string]$Namespace = "calculadora-suma",
    [string]$ReleaseName = "suma-basica",
    [string]$GhcrSecretName = "ghcr-secret",

    [string]$ChartPath = "..\helm\suma-basica",
    [string]$ValuesFile = "..\helm\suma-basica\values.yaml",

    [string]$GithubUser = $env:GITHUB_USER,
    [string]$GithubPat = $env:GITHUB_PAT,

    [switch]$ValidateOnly,
    [switch]$SkipAksCredentials,

    [string]$HelmTimeout = "10m"
)

$ErrorActionPreference = "Stop"

function Require-Command {
    param([Parameter(Mandatory = $true)][string]$Name)

    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Comando requerido no encontrado: $Name"
    }
}

function Resolve-FullPath {
    param([Parameter(Mandatory = $true)][string]$PathValue)

    if ([System.IO.Path]::IsPathRooted($PathValue)) {
        return $PathValue
    }

    return [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot $PathValue))
}

Write-Host "[1/8] Validando herramientas..." -ForegroundColor Cyan
Require-Command "az"
Require-Command "kubectl"
Require-Command "helm"

$chartFullPath = Resolve-FullPath $ChartPath
$valuesFullPath = Resolve-FullPath $ValuesFile

if (-not (Test-Path $chartFullPath)) {
    throw "Chart no encontrado: $chartFullPath"
}
if (-not (Test-Path $valuesFullPath)) {
    throw "Values file no encontrado: $valuesFullPath"
}

Write-Host "[2/8] Verificando sesión Azure..." -ForegroundColor Cyan
$accountInfo = az account show 2>$null
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($accountInfo)) {
    throw "No hay sesión activa en Azure CLI. Ejecuta: az login"
}

Write-Host "[3/8] Seleccionando suscripción (si aplica)..." -ForegroundColor Cyan
if (-not [string]::IsNullOrWhiteSpace($SubscriptionId)) {
    az account set --subscription $SubscriptionId | Out-Null
}

if (-not $SkipAksCredentials) {
    Write-Host "[4/8] Obteniendo credenciales de AKS..." -ForegroundColor Cyan
    az aks get-credentials --resource-group $ResourceGroup --name $ClusterName --overwrite-existing | Out-Null
}
else {
    Write-Host "[4/8] Saltando obtención de credenciales AKS (SkipAksCredentials)." -ForegroundColor Yellow
}

Write-Host "[5/8] Creando namespace (idempotente)..." -ForegroundColor Cyan
kubectl create namespace $Namespace --dry-run=client -o yaml | kubectl apply -f - | Out-Null

Write-Host "[6/8] Validando chart Helm..." -ForegroundColor Cyan
helm lint $chartFullPath
helm template $ReleaseName $chartFullPath -n $Namespace -f $valuesFullPath | Out-Null

if ($ValidateOnly) {
    Write-Host "Validación completada. No se desplegó nada (-ValidateOnly)." -ForegroundColor Green
    exit 0
}

if ([string]::IsNullOrWhiteSpace($GithubUser) -or [string]::IsNullOrWhiteSpace($GithubPat)) {
    throw "Faltan credenciales GHCR. Define -GithubUser/-GithubPat o variables GITHUB_USER/GITHUB_PAT."
}

Write-Host "[7/8] Creando/actualizando secret GHCR..." -ForegroundColor Cyan
kubectl create secret docker-registry $GhcrSecretName `
    --namespace $Namespace `
    --docker-server=ghcr.io `
    --docker-username=$GithubUser `
    --docker-password=$GithubPat `
    --dry-run=client -o yaml | kubectl apply -f - | Out-Null

Write-Host "[8/8] Desplegando release Helm..." -ForegroundColor Cyan
helm upgrade --install $ReleaseName $chartFullPath --namespace $Namespace --create-namespace -f $valuesFullPath --wait --timeout $HelmTimeout

Write-Host "Despliegue remoto completado." -ForegroundColor Green
Write-Host "Comandos útiles:" -ForegroundColor Gray
Write-Host "  helm status $ReleaseName -n $Namespace" -ForegroundColor Gray
Write-Host "  kubectl get deployments,services,pods -n $Namespace" -ForegroundColor Gray
