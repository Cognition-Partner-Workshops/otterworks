variable "account" {
  description = "Snowflake account identifier, ORGNAME-ACCOUNTNAME."
  type        = string
  default     = "TOJGONB-SF03144"
  validation {
    condition     = can(regex("^[A-Z0-9_]+-[A-Z0-9_]+$", var.account))
    error_message = "account must be ORGNAME-ACCOUNTNAME (upper case)."
  }
}

variable "database" {
  description = "Tenant Snowflake database the external stage is created in (bootstrap/tenant.sql)."
  type        = string
  default     = "OTTERWORKS_LDM_S30_AFTER"
}

variable "bucket" {
  description = "Tenant S3 staging bucket (demo-aws output bucket_name)."
  type        = string
  default     = "otterworks-ldm-s30-after-599083837640"
}

variable "prefix" {
  description = "Tenant prefix inside the bucket (demo-aws output s3_prefix). Exactly one path segment plus '/'."
  type        = string
  default     = "s30-after/"
  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9-]{0,62}/$", var.prefix))
    error_message = "prefix must be a single tenant segment ending in '/', e.g. s30-after/."
  }
}

variable "region" {
  description = "AWS region of the demo account (bucket, IAM)."
  type        = string
  default     = "us-east-1"
}

variable "snowflake_user" {
  description = "Snowflake user Terraform connects as (PAT in SNOWFLAKE_PAT); empty = the SNOWFLAKE_USER environment variable."
  type        = string
  default     = ""
}

variable "snowflake_role" {
  description = "Role Terraform uses; needs CREATE INTEGRATION on the account (bootstrap/account.sql)."
  type        = string
  default     = "LDM_ADMIN"
}

variable "snowflake_warehouse" {
  description = "Warehouse for the provider session."
  type        = string
  default     = "LDM_WH"
}

variable "integration_name" {
  description = "Storage integration name (account-level object)."
  type        = string
  default     = "LDM_S3_INT"
}

variable "stage_name" {
  description = "External stage name inside <database>.STG; the job's SNOWFLAKE_STAGE."
  type        = string
  default     = "LDM_STAGE"
}

variable "job_role" {
  description = "Tenant job role (bootstrap/tenant.sql) granted USAGE on the stage. Empty derives LDM_JOB_<TOKEN>."
  type        = string
  default     = ""
}

variable "guardrail_principal_arns" {
  description = <<-EOT
    Extra IAM principals trusted (with the integration's external ID) only while running the IAM guardrail
    proof (./guardrail.sh). Leave empty in the steady state: then Snowflake's IAM user is the sole principal.
  EOT
  type        = list(string)
  default     = []
}
