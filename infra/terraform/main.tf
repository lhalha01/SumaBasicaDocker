resource "azurerm_resource_group" "rg" {
  name     = var.resource_group_name
  location = var.location
  tags     = var.tags
}

resource "random_string" "acr_suffix" {
  length  = 5
  upper   = false
  lower   = true
  numeric = true
  special = false
}

resource "azurerm_container_registry" "acr" {
  name                = "${var.acr_name_prefix}${random_string.acr_suffix.result}"
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
  sku                 = "Basic"
  admin_enabled       = false
  tags                = var.tags
}

resource "azurerm_kubernetes_cluster" "aks" {
  count               = var.create_aks ? 1 : 0
  name                = var.aks_name
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  dns_prefix          = var.aks_name
  tags                = var.tags

  default_node_pool {
    name       = "system"
    node_count = var.node_count
    vm_size    = "Standard_B2s"
  }

  identity {
    type = "SystemAssigned"
  }
}

data "azurerm_kubernetes_cluster" "existing" {
  count               = var.create_aks ? 0 : 1
  name                = var.existing_aks_name
  resource_group_name = azurerm_resource_group.rg.name
}

locals {
  kubelet_object_id = var.create_aks ? azurerm_kubernetes_cluster.aks[0].kubelet_identity[0].object_id : var.kubelet_identity_object_id
  aks_name_effective = var.create_aks ? azurerm_kubernetes_cluster.aks[0].name : data.azurerm_kubernetes_cluster.existing[0].name
}

resource "azurerm_role_assignment" "acr_pull" {
  count                = local.kubelet_object_id != "" ? 1 : 0
  scope                = azurerm_container_registry.acr.id
  role_definition_name = "AcrPull"
  principal_id         = local.kubelet_object_id
}
