output "resource_group_name" {
  description = "Nombre del Resource Group creado"
  value       = azurerm_resource_group.rg.name
}

output "aks_cluster_name" {
  description = "Nombre del AKS creado"
  value       = azurerm_kubernetes_cluster.aks.name
}

output "aks_fqdn" {
  description = "FQDN del API server de AKS"
  value       = azurerm_kubernetes_cluster.aks.fqdn
}

output "kubectl_connect_command" {
  description = "Comando para obtener credenciales de kubectl"
  value       = "az aks get-credentials --resource-group ${azurerm_resource_group.rg.name} --name ${azurerm_kubernetes_cluster.aks.name} --overwrite-existing"
}
