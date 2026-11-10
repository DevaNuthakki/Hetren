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
  description = "4 vCPUs on 2 physical cores, 16 GB: one diagnosis pod per node (llama-server -t 2)."
  type        = string
  default     = "e2-standard-4"

  validation {
    condition     = can(regex("^e2-standard-[0-9]+$", var.machine_type))
    error_message = "An e2-standard machine type (its vCPU count is the number at the end)."
  }
}

variable "min_nodes" {
  type    = number
  default = 1
}

variable "max_nodes" {
  description = "At most 2 nodes: 2 x e2-standard-4 = 8 vCPUs, the Free Trial's concurrent-core limit."
  type        = number
  default     = 2

  validation {
    condition     = var.max_nodes >= 1 && var.max_nodes <= 2
    error_message = "The approved cap is 2 nodes."
  }
}

variable "max_vcpus" {
  description = "The Free Trial's limit on concurrent Compute Engine cores; the node pool at its maximum must fit."
  type        = number
  default     = 8
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
