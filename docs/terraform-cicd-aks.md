# Terraform + CI/CD para publicar frontal y API en AKS

## 1. Qué se creó

### Infraestructura (Terraform)

Ruta: [infra/terraform/main.tf](../infra/terraform/main.tf)

- Resource Group
- Azure Container Registry (ACR)
- AKS opcional (crear nuevo o reutilizar uno existente)
- Rol `AcrPull` para que AKS pueda descargar imágenes del ACR

Archivos:

- [infra/terraform/providers.tf](../infra/terraform/providers.tf)
- [infra/terraform/variables.tf](../infra/terraform/variables.tf)
- [infra/terraform/main.tf](../infra/terraform/main.tf)
- [infra/terraform/outputs.tf](../infra/terraform/outputs.tf)
- [infra/terraform/terraform.tfvars.example](../infra/terraform/terraform.tfvars.example)

### Aplicación en Kubernetes

Ruta: [k8s](../k8s)

- Namespace
- Backends `suma-digito-0..3`
- RBAC para proxy
- Deployment/Service del proxy (frontal + API)

### CI/CD (GitHub Actions)

Ruta: [.github/workflows/ci-cd-aks.yml](../.github/workflows/ci-cd-aks.yml)

Jobs:

1. `terraform-plan`
2. `build-and-push` (imagen proxy a ACR)
3. `deploy` (aplica manifiestos en AKS)

---

## 2. Secrets y Variables en GitHub

## Secrets (Repository Secrets)

- `AZURE_CREDENTIALS` (JSON de Service Principal)
- `GHCR_USER`

> El `GHCR_PAT` se lee desde Azure Key Vault (secreto `github-pat`) durante el pipeline.

## Variables (Repository Variables)

- `AZURE_RESOURCE_GROUP` (ej: `AHL_resources`)
- `AKS_CLUSTER_NAME` (ej: `KSuma`)
- `ACR_NAME` (nombre ACR, sin dominio)
- `ACR_LOGIN_SERVER` (ej: `miacr.azurecr.io`)
- `AKS_KUBELET_OBJECT_ID` (si reutilizas AKS y quieres que Terraform asigne `AcrPull`)
- `AZURE_KEYVAULT_NAME` (ej: `AHLSecretos`)

---

## 3. Crear credenciales de Azure para GitHub

Ejemplo (ajusta suscripción):

```powershell
az ad sp create-for-rbac `
  --name "gh-sumabasica-cicd" `
  --role contributor `
  --scopes /subscriptions/<SUBSCRIPTION_ID> `
  --sdk-auth
```

El JSON resultante se guarda como `AZURE_CREDENTIALS` en GitHub Secrets.

---

## 4. Ejecución local de Terraform (opcional)

```powershell
cd infra/terraform
terraform init
terraform validate
terraform plan -var="resource_group_name=AHL_resources" -var="existing_aks_name=KSuma"
```

---

## 5. Flujo de despliegue

1. Push a `FrontalSuma`, `ConHelm` o `master`
2. GitHub Actions ejecuta:
   - Plan de Terraform
   - Build/push de imagen proxy a ACR
   - Deploy a AKS (namespace + workloads)
3. Verificación automática de rollout del deployment `suma-proxy`

---

## 6. Validación post-despliegue

```powershell
kubectl get deployments,services,pods -n calculadora-suma
kubectl logs -n calculadora-suma deploy/suma-proxy --tail=200
```

Si `suma-proxy` está `Running` y el Service tipo LoadBalancer tiene IP pública, abre esa IP para usar el frontal.

---

## 7. Notas importantes

- El `proxy` necesita `kubectl` dentro de su contenedor para escalar deployments.
- El frontend usa endpoint relativo (`/suma-n-digitos`), por lo que frontal y API comparten origen.
- Si no quieres exponer por `LoadBalancer`, cambia [k8s/proxy-service.yaml](../k8s/proxy-service.yaml) a `ClusterIP` y publica con Ingress.
