variable "run_token" {
  description = "Run token, lp-<yyyymmdd>-<two letters>. Prefixes every resource name and fills the run_token tag."
  type        = string

  validation {
    condition     = can(regex("^lp-[0-9]{8}-[a-z]{2}$", var.run_token))
    error_message = "run_token must look like lp-20261006-bd."
  }
}

variable "expires" {
  description = "Absolute UTC expiry written to the Expires tag (RFC 3339), read by the reaper."
  type        = string

  validation {
    condition     = can(regex("^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}Z$", var.expires))
    error_message = "expires must be an RFC 3339 UTC timestamp like 2026-10-10T00:00:00Z."
  }
}

variable "region" {
  type    = string
  default = "us-east-1"
}

variable "db_instance_identifier" {
  description = "Existing shared RDS PostgreSQL instance that hosts the run's database. Read only; never modified here."
  type        = string
  default     = "otterworks-postgres-dev"
}

variable "master_secret_id" {
  description = "Secrets Manager secret holding the instance's master credential as JSON with a password key."
  type        = string
  default     = "otterworks/dev/rds/master"
}

variable "master_database" {
  description = "Maintenance database the master user connects to for CREATE/DROP DATABASE."
  type        = string
  default     = "postgres"
}

variable "app_connection_limit" {
  description = "CONNECTION LIMIT of the run's login role."
  type        = number
  default     = 20
}

variable "log_retention_days" {
  type    = number
  default = 7
}
