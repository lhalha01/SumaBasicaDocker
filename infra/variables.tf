variable "resource_group_name" {
  description = "Nombre del Resource Group donde se desplegará AKS"
  type        = string
}

variable "location" {
  description = "Región de Azure"
  type        = string
  default     = "westeurope"
}

variable "aks_cluster_name" {
  description = "Nombre del cluster AKS"
  type        = string
}

variable "dns_prefix" {
  description = "Prefijo DNS para AKS"
  type        = string
}

variable "node_count" {
  description = "Número de nodos del pool por defecto"
  type        = number
  default     = 1
}

variable "node_vm_size" {
  description = "Tamaño de VM para nodos AKS"
  type        = string
  default     = "Standard_B2s"
}

variable "kubernetes_version" {
  description = "Versión de Kubernetes para AKS (null = última soportada por región)"
  type        = string
  default     = null
}

variable "tags" {
  description = "Etiquetas para recursos"
  type        = map(string)
  default = {
    project = "SumaBasicaDocker"
    env     = "dev"
    iac     = "terraform"
  }
}
