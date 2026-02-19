# Terraform + Azure DevOps CI/CD para publicar frontal y API en AKS

## 1. Qué incluye esta solución

- Infraestructura con Terraform en [infra/terraform](../infra/terraform)
- Despliegue Kubernetes en [k8s](../k8s)
- Pipeline Azure DevOps en [azure-pipelines.yml](../azure-pipelines.yml)

El pipeline hace:

1. `terraform init/validate/plan`
2. build/push de imagen proxy a ACR
3. despliegue en AKS (namespace, secretos, workloads)

## 2. Prerrequisitos en Azure DevOps

- Proyecto Azure DevOps con repo conectado
- Service Connection a Azure (`azureServiceConnection`)
- Permisos del Service Connection sobre:
  - Resource Group (Contributor o mínimo equivalente)
  - AKS (lectura/escritura para despliegue)
  - ACR (push)
  - Key Vault (secrets get/list)

## 3. Variables de pipeline necesarias

Define estas variables en Azure DevOps (Pipeline variables o Variable Group):

- `azureServiceConnection` = nombre de la service connection (por defecto `sc-aks-deploy`)
- `resourceGroup` = `AHL_resources`
- `aksClusterName` = `KSuma`
- `acrName` = nombre corto del ACR (ej. `sumaacrxyz12`)
- `acrLoginServer` = login server ACR (ej. `sumaacrxyz12.azurecr.io`)
- `keyVaultName` = `AHLSecretos`
- `ghcrUser` = `lhalha01`
- `namespace` = `calculadora-suma`
- `AKS_KUBELET_OBJECT_ID` = Object ID de kubelet identity (si aplica para Terraform role assignment)

## 4. Secretos

No se usa `GHCR_PAT` en variables del pipeline.

El PAT se obtiene de Azure Key Vault:

- Vault: `AHLSecretos`
- Secret name: `github-pat`

El pipeline lo lee en runtime con Azure CLI y crea/actualiza el `ghcr-secret` en Kubernetes.

## 5. Ejecución

1. Push a `FrontalSuma`, `ConHelm` o `master` (trigger automático)
2. O ejecutar manualmente el pipeline desde Azure DevOps
3. Revisar stages:
   - `TerraformPlan`
   - `BuildAndPush`
   - `DeployAKS`

## 6. Validación post-despliegue

```powershell
kubectl get deployments,services,pods -n calculadora-suma
kubectl logs -n calculadora-suma deploy/suma-proxy --tail=200
```

Si `suma-proxy` está `Running` y `proxy-service` tiene endpoint público (LoadBalancer), abre esa URL para usar el frontal.

## 7. Notas operativas

- El frontend usa ruta relativa (`/suma-n-digitos`) y comparte origen con la API.
- Los backends `suma-digito-*` arrancan en `replicas: 0` (scale-to-zero inicial).
- Si prefieres Ingress en lugar de LoadBalancer, cambia [k8s/proxy-service.yaml](../k8s/proxy-service.yaml).
