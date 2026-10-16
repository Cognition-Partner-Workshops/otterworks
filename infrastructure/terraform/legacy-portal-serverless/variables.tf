variable "run_token" {
  description = "Run token, lp-<yyyymmdd>-<two lowercase letters or digits>. Used in every resource name and in the run_token tag."
  type        = string

  validation {
    condition     = can(regex("^lp-[0-9]{8}-[a-z0-9]{2}$", var.run_token))
    error_message = "run_token must look like lp-20261005-rh."
  }
}

variable "expires" {
  description = "Expiry date written to the Expires tag, set by lp-up at apply time."
  type        = string
  default     = "unset"
}

variable "region" {
  description = "AWS region of the otterworks-dev VPC."
  type        = string
  default     = "us-east-1"
}

variable "vpc_name" {
  description = "Name tag of the existing VPC whose private subnets carry the Aurora cluster."
  type        = string
  default     = "otterworks-dev"
}

variable "private_subnet_name_prefix" {
  description = "Name tag prefix of the existing private subnets."
  type        = string
  default     = "otterworks-private-"
}

variable "builder_role_name" {
  description = "Existing Devin builder role that receives the run-scoped policy."
  type        = string
  default     = "devin-cw-builder"
}

variable "contexts" {
  description = "Bounded contexts of services/legacy-portal. One Lambda function each, keyed by context name, with its Postgres schema and route prefix."
  type = map(object({
    schema       = string
    route_prefix = string
  }))
  default = {
    announcements = { schema = "announcements", route_prefix = "/api/announcements" }
    preferences   = { schema = "user_preferences", route_prefix = "/api/preferences" }
    feedback      = { schema = "feedback", route_prefix = "/api/feedback" }
  }
}

variable "default_route_context" {
  description = "Context whose function answers routes outside the three prefixes (/health, /actuator/*, unknown paths). These are the corpus's common cases."
  type        = string
  default     = "announcements"
}

variable "aurora_engine_version" {
  description = "Aurora PostgreSQL engine version. 16.3 or later supports a 0 ACU floor."
  type        = string
  default     = "16.13"
}

variable "aurora_min_acu" {
  description = "Aurora Serverless v2 minimum capacity in ACUs. 0 lets the cluster pause when idle."
  type        = number
  default     = 0
}

variable "aurora_max_acu" {
  description = "Aurora Serverless v2 maximum capacity in ACUs."
  type        = number
  default     = 1
}

variable "aurora_seconds_until_auto_pause" {
  description = "Idle seconds before a 0 ACU cluster pauses."
  type        = number
  default     = 600
}

variable "lambda_memory_mb" {
  description = "Memory for each context function. The child sessions raise it if the Java runtime needs more."
  type        = number
  default     = 512
}

variable "log_retention_days" {
  description = "Retention for the Lambda and API access log groups."
  type        = number
  default     = 3
}

variable "deployment_config_name" {
  description = "CodeDeploy configuration of each context's deployment group."
  type        = string
  default     = "CodeDeployDefault.LambdaCanary10Percent5Minutes"
}

variable "alarm_5xx_rate_percent" {
  description = "5xx share of HTTP API responses, in percent, above which a one-minute datapoint breaches."
  type        = number
  default     = 20
}

variable "probe_runtime_version" {
  description = "CloudWatch Synthetics Node runtime of the probe canary."
  type        = string
  default     = "syn-nodejs-puppeteer-13.1"
}

variable "devin_webhook_url" {
  description = "Devin automation webhook URL the EventBridge API destination posts to. Empty leaves the page rule disabled."
  type        = string
  default     = ""
}

variable "devin_webhook_secret" {
  description = "Value sent in the X-Webhook-Secret header to the Devin webhook. Empty leaves the page rule disabled."
  type        = string
  sensitive   = true
  default     = ""
}
