variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be one of: dev, staging, prod."
  }
}

variable "project" {
  description = "Project name used as prefix for resource naming"
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,20}$", var.project))
    error_message = "Project name must be lowercase alphanumeric with hyphens, 2-21 characters."
  }
}

variable "namespace_suffix" {
  description = <<-EOT
    Namespace suffix applied to the collection, its policies, and any per-run
    objects so concurrent migration runs never collide. E.g. "os-demo".
  EOT
  type        = string
  default     = "os-demo"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,12}$", var.namespace_suffix))
    error_message = "namespace_suffix must be lowercase alphanumeric with hyphens, 2-13 chars."
  }
}

variable "data_access_principal_arns" {
  description = <<-EOT
    IAM principal ARNs (e.g. the search-service IRSA role) granted data-plane
    access to the collection. Leave empty to attach principals out-of-band.
  EOT
  type        = list(string)
  default     = []
}

variable "allow_public_access" {
  description = "If true the network policy allows public access to the collection endpoint and Dashboards (dev only). Prefer VPC access in prod."
  type        = bool
  default     = true
}
