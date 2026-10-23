variable "run_token" {
  description = "Run token. Prefixes every resource name and is written to the run_token tag."
  type        = string

  validation {
    condition     = length(var.run_token) <= 40 && can(regex("^[a-z][a-z0-9]*(-[a-z0-9]+)*$", var.run_token))
    error_message = "run_token must be at most 40 characters of lower-case letters, digits and single hyphens, starting with a letter (e.g. billing-20261023-a1)."
  }
}

variable "expires" {
  description = "RFC 3339 expiry written to the Expires tag (e.g. 2026-11-23T00:00:00Z)."
  type        = string

  validation {
    condition     = can(timeadd(var.expires, "0s"))
    error_message = "expires must be an RFC 3339 timestamp such as 2026-11-23T00:00:00Z."
  }
}

variable "region" {
  description = "AWS region of the otterworks-dev VPC."
  type        = string
  default     = "us-east-1"
}

variable "offline_plan" {
  description = "Skip STS and metadata calls so `terraform plan` runs on mock credentials. Only for PR CI; requires vpc_id, subnet_ids and allowed_cidr_blocks to be set."
  type        = bool
  default     = false
}

variable "vpc_name" {
  description = "Name tag of the VPC to look up when vpc_id is null."
  type        = string
  default     = "otterworks-dev"
}

variable "vpc_id" {
  description = "VPC id. null looks up the VPC by vpc_name."
  type        = string
  default     = null
}

variable "private_subnet_name_prefix" {
  description = "Name tag prefix of the private subnets to look up when subnet_ids is null."
  type        = string
  default     = "otterworks-private-"
}

variable "subnet_ids" {
  description = "Private subnet ids for the DB subnet group (at least two AZs). null looks them up by private_subnet_name_prefix."
  type        = list(string)
  default     = null
}

variable "allowed_cidr_blocks" {
  description = "CIDR blocks admitted on 5432. null admits only the VPC's primary CIDR (the EKS nodes and pods live in it)."
  type        = list(string)
  default     = null

  validation {
    condition     = var.allowed_cidr_blocks == null || alltrue([for c in coalesce(var.allowed_cidr_blocks, []) : can(cidrnetmask(c)) && c != "0.0.0.0/0"])
    error_message = "allowed_cidr_blocks must be valid IPv4 CIDRs and must not include 0.0.0.0/0."
  }
}

variable "engine_version" {
  description = "RDS PostgreSQL engine version, pinned to a minor. The billing transcripts were recorded on 16 (Compose postgres:16 = 16.15 when the inventory ran)."
  type        = string
  default     = "16.15"

  validation {
    condition     = can(regex("^16\\.[0-9]+$", var.engine_version))
    error_message = "engine_version must be a PostgreSQL 16 minor such as 16.15 (major 16 was chosen to match the recorded transcripts)."
  }
}

variable "instance_class" {
  description = "RDS instance class."
  type        = string
  default     = "db.t4g.micro"
}

variable "allocated_storage" {
  description = "Initial gp3 storage in GiB."
  type        = number
  default     = 20
}

variable "max_allocated_storage" {
  description = "Storage autoscaling ceiling in GiB."
  type        = number
  default     = 100
}

variable "multi_az" {
  description = "Run a standby in a second AZ."
  type        = bool
  default     = false
}

variable "backup_retention_days" {
  description = "Automated backup retention in days."
  type        = number
  default     = 7

  validation {
    condition     = var.backup_retention_days >= 1 && var.backup_retention_days <= 35
    error_message = "backup_retention_days must be between 1 and 35 (0 would turn backups off)."
  }
}

variable "deletion_protection" {
  description = "Refuse DeleteDBInstance until this is turned off in a reviewed change."
  type        = bool
  default     = true
}

variable "master_username" {
  description = "RDS master user (rds_superuser). Only creates the database and the billing roles; the app never logs in as it."
  type        = string
  default     = "billing_admin"
}

variable "database_name" {
  description = "Billing database created by bootstrap/create-database.sql (not by RDS, so its locale is explicit)."
  type        = string
  default     = "billing"
}

variable "log_retention_days" {
  description = "Retention for the exported postgresql and upgrade log groups."
  type        = number
  default     = 30
}
