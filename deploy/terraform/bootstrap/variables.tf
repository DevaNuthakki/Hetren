variable "project_id" {
  description = "ID of the dedicated GCP project to create for Hetren (globally unique, e.g. hetren-m4-<suffix>)."
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.project_id))
    error_message = "A GCP project ID: 6-30 characters, lowercase letters, digits and hyphens."
  }
}

variable "billing_account" {
  description = "Billing account ID (XXXXXX-XXXXXX-XXXXXX) the project is linked to and the budget watches."
  type        = string
}

variable "org_id" {
  description = "Organization ID to create the project in; empty for a project without an organization."
  type        = string
  default     = ""
}

variable "region" {
  description = "Region of the state bucket, the kill switch and (in the gke stack) the cluster."
  type        = string
  default     = "us-central1"
}

variable "budget_usd" {
  description = "Budget for the project; at 100% the kill switch disables billing on the project."
  type        = number
  default     = 25

  validation {
    condition     = var.budget_usd > 0 && var.budget_usd <= 25
    error_message = "The approved cap is $25."
  }
}

variable "alert_email" {
  description = "Optional extra email for budget alerts; billing account admins are always emailed."
  type        = string
  default     = ""
}

variable "kill_switch_dry_run" {
  description = "true: the kill switch only logs what it would do (for a test message); false in the cloud session."
  type        = bool
  default     = false
}
