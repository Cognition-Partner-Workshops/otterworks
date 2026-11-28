terraform {
  required_version = ">= 1.4.0"
}

variable "root_volume_gib" {
  type = number

  validation {
    condition     = var.root_volume_gib > 0 && floor(var.root_volume_gib) == var.root_volume_gib
    error_message = "Root volume must be a positive whole number of GiB."
  }
}

variable "app_retention_days" {
  type = number

  validation {
    condition     = contains([7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1096, 1827, 2192, 2557, 2922, 3288, 3653], var.app_retention_days)
    error_message = "Use a supported retention period of at least seven days."
  }
}

resource "terraform_data" "dev_settings" {
  input = {
    root_volume_gib      = var.root_volume_gib
    app_retention_days   = var.app_retention_days
    audit_retention_days = 90
  }
}

output "dev_settings" {
  value = terraform_data.dev_settings.output
}
