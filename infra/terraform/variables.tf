variable "location" {
  description = "Azure region"
  type        = string
  default     = "spaincentral"
}

variable "resource_group_name" {
  description = "Resource group name"
  type        = string
  default     = "AHL_resources"
}

variable "create_aks" {
  description = "Create a new AKS cluster. If false, use existing_aks_name."
  type        = bool
  default     = false
}

variable "existing_aks_name" {
  description = "Existing AKS cluster name when create_aks=false"
  type        = string
  default     = "KSuma"
}

variable "aks_name" {
  description = "AKS name when create_aks=true"
  type        = string
  default     = "ksuma-tf"
}

variable "node_count" {
  description = "Default node count when creating AKS"
  type        = number
  default     = 1
}

variable "acr_name_prefix" {
  description = "Prefix for ACR name (must be globally unique after suffix)"
  type        = string
  default     = "sumaacr"
}

variable "kubelet_identity_object_id" {
  description = "Kubelet identity object id for existing AKS (required to grant AcrPull when create_aks=false)"
  type        = string
  default     = ""
}

variable "tags" {
  description = "Resource tags"
  type        = map(string)
  default = {
    project = "SumaBasicaDocker"
    env     = "prod"
    managed = "terraform"
  }
}
