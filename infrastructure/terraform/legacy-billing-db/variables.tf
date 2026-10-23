variable "run_token" {
  description = "Run token, for example appassess-20261023-g7."
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9]*(-[a-z0-9]+)*$", var.run_token)) && length(var.run_token) <= 40
    error_message = "run_token must be a lowercase token of at most 40 characters, for example appassess-20261023-g7."
  }
}

variable "expires" {
  description = "Expiry date written to the Expires tag."
  type        = string
  default     = "unset"
}

variable "region" {
  description = "AWS region of the otterworks-dev VPC."
  type        = string
  default     = "us-east-1"
}

variable "vpc_name" {
  description = "Name tag of the existing VPC for the database."
  type        = string
  default     = "otterworks-dev"
}

variable "private_subnet_name_prefix" {
  description = "Name tag prefix of the existing private subnets."
  type        = string
  default     = "otterworks-private-"
}

variable "engine_version" {
  description = "PostgreSQL major version; RDS selects the current 16.x minor."
  type        = string
  default     = "16"

  validation {
    condition     = can(regex("^16(\\.[0-9]+)?$", var.engine_version))
    error_message = "engine_version must be PostgreSQL 16, optionally with a minor version."
  }
}

variable "instance_class" {
  description = "RDS instance class."
  type        = string
  default     = "db.t4g.small"
}

variable "allocated_storage" {
  description = "Initial database storage in GiB."
  type        = number
  default     = 20
}

variable "max_allocated_storage" {
  description = "Maximum autoscaled database storage in GiB."
  type        = number
  default     = 100
}

variable "db_name" {
  description = "Initial database name."
  type        = string
  default     = "billing"
}

variable "master_username" {
  description = "RDS-managed master username used only for database bootstrap."
  type        = string
  default     = "billing_admin"
}

variable "multi_az" {
  description = "Whether to deploy a standby in another Availability Zone."
  type        = bool
  default     = false
}

variable "backup_retention_days" {
  description = "Automated backup retention in days."
  type        = number
  default     = 7

  validation {
    condition     = var.backup_retention_days >= 1 && var.backup_retention_days <= 35
    error_message = "backup_retention_days must be between 1 and 35."
  }
}

variable "deletion_protection" {
  description = "Whether RDS deletion protection is enabled."
  type        = bool
  default     = true
}

variable "log_retention_days" {
  description = "Retention for PostgreSQL and upgrade log groups."
  type        = number
  default     = 30
}
