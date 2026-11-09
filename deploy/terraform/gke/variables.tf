variable "project_id" {
  description = "The dedicated project the bootstrap stack created."
  type        = string
}

variable "region" {
  type    = string
  default = "us-central1"
}

variable "zone" {
  description = "A zonal cluster: its management fee is the one the GKE free tier covers."
  type        = string
  default     = "us-central1-a"
}

variable "machine_type" {
  description = "8 vCPUs on 4 physical cores, 32 GB: one diagnosis pod per node."
  type        = string
  default     = "e2-standard-8"
}

variable "min_nodes" {
  type    = number
  default = 1
}

variable "max_nodes" {
  description = "Bounds the burn rate: at most 3 nodes (24 vCPUs)."
  type        = number
  default     = 3

  validation {
    condition     = var.max_nodes >= 1 && var.max_nodes <= 3
    error_message = "The approved cap is 3 nodes."
  }
}

variable "disk_size_gb" {
  type    = number
  default = 50
}

variable "master_authorized_cidr" {
  description = "The operator's public IP as a /32: the only address allowed to reach the cluster's API."
  type        = string

  validation {
    condition     = can(cidrhost(var.master_authorized_cidr, 0)) && endswith(var.master_authorized_cidr, "/32")
    error_message = "One address, as a /32 (curl -s https://checkip.amazonaws.com)."
  }
}
