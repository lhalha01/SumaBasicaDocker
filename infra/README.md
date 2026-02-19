# Terraform IaC para AKS

Este directorio contiene la infraestructura base para desplegar un cluster AKS en Azure:
- Resource Group
- AKS (node pool por defecto)

## Archivos
- `versions.tf`: versiones de Terraform y providers
- `variables.tf`: variables de entrada
- `main.tf`: recursos principales
- `outputs.tf`: salidas útiles
- `terraform.tfvars.example`: ejemplo de configuración

## Uso local

1. Copia valores base:
```bash
cp terraform.tfvars.example terraform.tfvars
```

2. Inicializa y valida:
```bash
terraform init
terraform fmt -recursive
terraform validate
```

3. Previsualiza cambios:
```bash
terraform plan -out tfplan
```

4. Aplica infraestructura:
```bash
terraform apply tfplan
```

5. Configura kubectl:
```bash
az aks get-credentials --resource-group <resource_group_name> --name <aks_cluster_name> --overwrite-existing
```

## Variables mínimas requeridas
- `resource_group_name`
- `aks_cluster_name`
- `dns_prefix`

## Notas
- El workflow `aks-platform-delivery.yml` detecta automáticamente este directorio y ejecuta Terraform.
- Para pipeline en GitHub, asegúrate de configurar:
  - `secrets.AZURE_CREDENTIALS`
  - `vars.AZURE_RESOURCE_GROUP`
  - `vars.AZURE_AKS_CLUSTER`
  - `vars.AZURE_LOCATION` (opcional)
