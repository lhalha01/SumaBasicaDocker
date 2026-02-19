param(
    [string]$Namespace = "calculadora-suma",
    [string]$ReleaseName = "suma-basica",
    [int]$EventsTail = 30
)

$ErrorActionPreference = "Stop"

function Require-Command {
    param([string]$CommandName)
    if (-not (Get-Command $CommandName -ErrorAction SilentlyContinue)) {
        throw "No se encontró '$CommandName' en PATH. Instálalo y vuelve a ejecutar el script."
    }
}

Write-Host "[1/6] Validando herramientas..." -ForegroundColor Cyan
Require-Command "kubectl"
Require-Command "helm"

Write-Host "[2/6] Release Helm" -ForegroundColor Cyan
try {
    helm status $ReleaseName -n $Namespace
}
catch {
    Write-Host "Release '$ReleaseName' no encontrada en namespace '$Namespace'." -ForegroundColor Yellow
}

Write-Host "[3/6] Historial Helm" -ForegroundColor Cyan
try {
    helm history $ReleaseName -n $Namespace
}
catch {
    Write-Host "No hay historial disponible para '$ReleaseName'." -ForegroundColor Yellow
}

Write-Host "[4/6] Deployments y Services" -ForegroundColor Cyan
kubectl get deployments,services -n $Namespace

Write-Host "[5/6] Pods" -ForegroundColor Cyan
kubectl get pods -n $Namespace -o wide

Write-Host "[6/6] Últimos eventos" -ForegroundColor Cyan
kubectl get events -n $Namespace --sort-by=.metadata.creationTimestamp | Select-Object -Last $EventsTail

Write-Host "Diagnóstico completado." -ForegroundColor Green
