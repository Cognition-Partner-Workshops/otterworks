variable "service_name" {
  description = "Lowercase identifier for the application being rearchitected."
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,30}$", var.service_name))
    error_message = "service_name must start with a lowercase letter and contain 2 to 31 lowercase letters, digits, or hyphens."
  }
}

variable "run_token" {
  description = "Unique run identifier used for names and mandatory run tags."
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]*-[0-9]{8}-[a-z0-9]{2}$", var.run_token)) && length(var.run_token) <= 15
    error_message = "run_token must match <prefix>-YYYYMMDD-xx and be at most 15 characters so the Synthetics canary name stays within AWS's 21-character limit."
  }
}

variable "expires" {
  description = "RFC 3339 expiry timestamp applied to the Expires tag."
  type        = string

  validation {
    condition     = can(formatdate("YYYY", var.expires))
    error_message = "expires must be a valid RFC 3339 timestamp."
  }
}

variable "disposition_evidence" {
  description = "Assessment row that supports this rearchitect disposition."
  type        = string

  validation {
    condition     = trimspace(var.disposition_evidence) != ""
    error_message = "disposition_evidence must identify the assessment row."
  }
}

variable "vpc_id" {
  description = "Existing VPC hosting Aurora."
  type        = string
}

variable "subnet_ids" {
  description = "Existing private subnet IDs for the Aurora subnet group."
  type        = list(string)

  validation {
    condition     = length(var.subnet_ids) > 0
    error_message = "subnet_ids must contain at least one subnet."
  }
}

variable "extra_tags" {
  description = "Additional tags; mandatory disposition tags take precedence."
  type        = map(string)
  default     = {}
}

variable "contexts" {
  description = "Application contexts mapped to PostgreSQL schema, API prefix, event publishing, and additional Lambda environment."
  type = map(object({
    schema           = string
    route_prefix     = string
    publishes_events = optional(bool, false)
    environment      = optional(map(string), {})
  }))

  validation {
    condition     = length(var.contexts) > 0
    error_message = "contexts must contain at least one application context."
  }

  validation {
    condition     = alltrue([for context in keys(var.contexts) : can(regex("^[a-z][a-z0-9-]{0,47}$", context))])
    error_message = "context keys must start with a lowercase letter and contain only lowercase letters, digits, or hyphens, with a maximum length of 48."
  }
}

variable "default_route_context" {
  description = "Context serving requests that do not match an explicit route prefix; null selects the first sorted context."
  type        = string
  default     = null

  validation {
    condition     = var.default_route_context == null ? true : trimspace(var.default_route_context) != ""
    error_message = "default_route_context must be a non-empty context key when set."
  }
}

variable "database_name" {
  description = "Database created by Aurora Serverless v2."
  type        = string
  default     = "app"
}

variable "master_username" {
  description = "Aurora master username."
  type        = string
  default     = "app_admin"
}

variable "schema_sql_path" {
  description = "Optional SQL file applied through the RDS Data API after the Aurora writer is ready."
  type        = string
  default     = null
}

variable "aurora_engine_version" {
  description = "Aurora PostgreSQL engine version."
  type        = string
  default     = "16.13"
}

variable "aurora_min_acu" {
  description = "Aurora Serverless v2 minimum capacity; zero permits auto-pause."
  type        = number
  default     = 0
}

variable "aurora_max_acu" {
  description = "Aurora Serverless v2 maximum capacity."
  type        = number
  default     = 1
}

variable "aurora_seconds_until_auto_pause" {
  description = "Idle seconds before a zero-ACU cluster pauses."
  type        = number
  default     = 600
}

variable "lambda_memory_mb" {
  description = "Memory allocated to each context Lambda."
  type        = number
  default     = 512
}

variable "log_retention_days" {
  description = "Retention for Lambda and HTTP API access log groups."
  type        = number
  default     = 3
}

variable "deployment_config_name" {
  description = "CodeDeploy Lambda deployment configuration."
  type        = string
  default     = "CodeDeployDefault.LambdaCanary10Percent5Minutes"
}

variable "alarm_5xx_rate_percent" {
  description = "HTTP API 5xx response rate that breaches the rate alarm."
  type        = number
  default     = 20
}

variable "probe_runtime_version" {
  description = "CloudWatch Synthetics Node runtime version."
  type        = string
  default     = "syn-nodejs-puppeteer-13.1"
}

variable "devin_webhook_url" {
  description = "Devin webhook URL; empty disables the page event rule."
  type        = string
  default     = ""
}

variable "devin_webhook_secret" {
  description = "X-Webhook-Secret header value; empty disables the page event rule."
  type        = string
  sensitive   = true
  default     = ""
}

variable "builder_role_name" {
  description = "Existing builder role receiving the run-scoped policy; empty skips attachment."
  type        = string
  default     = ""
}

variable "account_id" {
  description = "Optional AWS account ID override; null reads the caller identity."
  type        = string
  default     = null
}

variable "event_subscriptions" {
  description = "Event bus subscriptions, each with its own encrypted table, rule, and consumer."
  type = map(object({
    source       = string
    detail_types = list(string)
  }))
  default = {}

  validation {
    condition     = alltrue([for subscription in keys(var.event_subscriptions) : can(regex("^[a-z][a-z0-9-]{0,38}$", subscription))])
    error_message = "event subscription keys must start with a lowercase letter and contain only lowercase letters, digits, or hyphens, with a maximum length of 39."
  }
}

variable "probe_steps" {
  description = "Optional HTTP API GET probe steps; an empty list creates no canary or probe bucket."
  type = list(object({
    name = string
    path = string
  }))
  default = []
}
